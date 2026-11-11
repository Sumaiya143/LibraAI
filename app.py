import sys
# Some setup helpers import ``app.db``. Alias the direct-script module so
# ``python app.py`` cannot execute the application a second time.
sys.modules.setdefault('app', sys.modules[__name__])

from flask import Flask, request, redirect, url_for, session, jsonify, render_template_string, render_template, flash, Response
import sqlite3, os, math, time, re, secrets, hmac, io, hashlib, logging, uuid, json
from commerce_engine import setup as setup_commerce, place_sandbox_order, CheckoutError
from werkzeug.security import generate_password_hash, check_password_hash
from flask import abort
from werkzeug.exceptions import HTTPException
from datetime import datetime, timedelta
from functools import wraps
from collections import Counter
from auth_protection import identity_key, blocked, failed, clear
from input_validation import validate_progress, validate_review, InputValidationError

from safe_redirect import safe_local_return_url
from session_lifecycle import start_authenticated_session, session_expired, touch_authenticated_session
app = Flask(__name__)
_IS_PRODUCTION = os.environ.get('LIBRAAI_ENV', '').strip().lower() == 'production'
_configured_secret = os.environ.get('SECRET_KEY', '')
if _IS_PRODUCTION and len(os.environ.get('SECRET_KEY', '')) < 32:
    raise RuntimeError('Production SECRET_KEY must be at least 32 characters and must be unique.')
if _IS_PRODUCTION:
    _placeholder_secret = any(
        marker in _configured_secret.lower()
        for marker in ('replace_with', 'change-me', 'changeme', 'development', 'placeholder')
    )
    if _placeholder_secret:
        raise RuntimeError('Production SECRET_KEY cannot be a template or placeholder value.')
app.secret_key = _configured_secret or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=_IS_PRODUCTION,
    SESSION_REFRESH_EACH_REQUEST=False,
    MAX_CONTENT_LENGTH=int(os.environ.get('LIBRAAI_MAX_CONTENT_LENGTH', str(2 * 1024 * 1024))),
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)
DB = os.environ.get("LIBRAAI_DB_PATH", os.path.join(os.path.dirname(__file__), "libraai.db"))
# SQLite sessions suit a single host. Redis sessions share authenticated state
# across workers/hosts; the primary application database remains SQLite in this
# release, so Redis sessions alone do not make the entire app multi-host safe.
_session_backend = os.environ.get('LIBRAAI_SESSION_BACKEND', 'sqlite').strip().lower()
_redis_url = os.environ.get('REDIS_URL', '').strip()
if _session_backend not in ('sqlite', 'redis'):
    raise RuntimeError('LIBRAAI_SESSION_BACKEND must be sqlite or redis.')
if _session_backend == 'redis' and not _redis_url:
    raise RuntimeError('LIBRAAI_SESSION_BACKEND=redis requires REDIS_URL.')
_multi_instance = os.environ.get('LIBRAAI_MULTI_INSTANCE', '').lower() in ('1','true','yes')
_rate_backend = os.environ.get('LIBRAAI_RATE_LIMIT_BACKEND', 'memory').strip().lower()
if _rate_backend not in ('memory', 'redis'):
    raise RuntimeError('LIBRAAI_RATE_LIMIT_BACKEND must be memory or redis.')
if _IS_PRODUCTION and (_session_backend == 'redis' or _rate_backend == 'redis') and not _redis_url.lower().startswith('rediss://'):
    raise RuntimeError('Production Redis sessions/rate limiting require a TLS rediss:// URL.')
if _IS_PRODUCTION and _multi_instance and (_session_backend != 'redis' or _rate_backend != 'redis'):
    raise RuntimeError('Multi-instance deployment requires Redis sessions and Redis rate limiting; the primary SQLite database still needs migration to PostgreSQL.')
if _IS_PRODUCTION and _rate_backend == 'redis' and not _redis_url:
    raise RuntimeError('LIBRAAI_RATE_LIMIT_BACKEND=redis requires REDIS_URL.')
# Create the configured database directory before opening SQLite. This prevents
# deployments with a fresh persistent volume from failing at first startup.
# SQLite URI/in-memory databases are intentionally left untouched.
if DB not in (':memory:', '') and not DB.startswith('file:'):
    _db_parent = os.path.dirname(os.path.abspath(DB))
    os.makedirs(_db_parent, mode=0o750, exist_ok=True)
    if _IS_PRODUCTION and not os.path.isabs(DB):
        raise RuntimeError('Production LIBRAAI_DB_PATH must be an absolute path on persistent storage.')

if _session_backend == 'redis':
    from redis_sessions import RedisSessionInterface
    app.session_interface = RedisSessionInterface(_redis_url)
else:
    from server_side_sessions import SQLiteSessionInterface
    app.session_interface = SQLiteSessionInterface(DB)

# --------------------------- Database ---------------------------
class _ClosingSQLiteConnection(sqlite3.Connection):
    """Commit/rollback on context exit and always release the connection."""
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()

def db():
    timeout_seconds = max(1, min(60, int(os.environ.get('LIBRAAI_DB_TIMEOUT_SECONDS', '15'))))
    conn = sqlite3.connect(DB, timeout=timeout_seconds, factory=_ClosingSQLiteConnection)
    conn.execute(f"PRAGMA busy_timeout={timeout_seconds * 1000}")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    c = db()
    # WAL improves concurrent reader/writer behaviour for the single-host
    # SQLite deployment. It is not a substitute for a managed DB at scale.
    if DB != ':memory:' and not str(DB).startswith('file:'):
        c.execute('PRAGMA journal_mode=WAL')
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT, username TEXT, email TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'reader', plan TEXT DEFAULT 'Free');
    CREATE TABLE IF NOT EXISTS librarian_branches(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, branch TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS merchant_profiles(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, store_name TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS books(id INTEGER PRIMARY KEY, title TEXT, author TEXT, genre TEXT, rating REAL, reads INTEGER, sales INTEGER, year INTEGER, format TEXT, price REAL, stock INTEGER, description TEXT, language TEXT DEFAULT 'English', isbn TEXT, branch TEXT DEFAULT 'Central', shelf TEXT DEFAULT 'A-01');
    CREATE TABLE IF NOT EXISTS catalog_products(id INTEGER PRIMARY KEY, book_id INTEGER UNIQUE REFERENCES books(id) ON DELETE CASCADE, product_type TEXT NOT NULL DEFAULT 'physical_book', sale_enabled INTEGER NOT NULL DEFAULT 1, digital_available INTEGER NOT NULL DEFAULT 0, inventory_quantity INTEGER NOT NULL DEFAULT 0, access_type TEXT NOT NULL DEFAULT 'purchase', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS manga_chapters(id INTEGER PRIMARY KEY, series_book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE, chapter_number REAL NOT NULL, title TEXT NOT NULL, content_url TEXT, release_at TEXT NOT NULL, early_access_at TEXT, membership_required INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'scheduled', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(series_book_id, chapter_number));
    CREATE TABLE IF NOT EXISTS subscription_entitlements(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, plan_code TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', starts_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, expires_at TEXT, UNIQUE(user_id, plan_code));
    CREATE TABLE IF NOT EXISTS progress(id INTEGER PRIMARY KEY, user_id INTEGER, book_id INTEGER, page INTEGER DEFAULT 1, percent REAL DEFAULT 0, updated TEXT, UNIQUE(user_id,book_id));
    CREATE TABLE IF NOT EXISTS ai_conversation_messages(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, role TEXT NOT NULL CHECK(role IN ('user','assistant')), content TEXT NOT NULL CHECK(length(content)<=4000), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS saved_study_sets(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, title TEXT NOT NULL CHECK(length(title)<=120), result_json TEXT NOT NULL CHECK(length(result_json)<=100000), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE INDEX IF NOT EXISTS idx_saved_study_sets_user_created ON saved_study_sets(user_id, id DESC);
    CREATE INDEX IF NOT EXISTS idx_ai_messages_user_created ON ai_conversation_messages(user_id, id);
    CREATE TABLE IF NOT EXISTS annotations(id INTEGER PRIMARY KEY, user_id INTEGER, book_id INTEGER, kind TEXT, content TEXT, color TEXT, page INTEGER, created TEXT);
    CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY, user_id INTEGER, book_id INTEGER, rating INTEGER, text TEXT, spoiler INTEGER DEFAULT 0, verified INTEGER DEFAULT 1, created TEXT);
    CREATE TABLE IF NOT EXISTS wishlist(id INTEGER PRIMARY KEY, user_id INTEGER, book_id INTEGER, UNIQUE(user_id,book_id));
    CREATE TABLE IF NOT EXISTS cart(id INTEGER PRIMARY KEY, user_id INTEGER, book_id INTEGER, qty INTEGER DEFAULT 1, format TEXT DEFAULT 'eBook', UNIQUE(user_id,book_id,format));
    CREATE TABLE IF NOT EXISTS loans(id INTEGER PRIMARY KEY, user_id INTEGER, book_id INTEGER, status TEXT, due TEXT, branch TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, user_id INTEGER, total REAL, status TEXT, address TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS clubs(id INTEGER PRIMARY KEY, name TEXT, topic TEXT, members INTEGER DEFAULT 0, next_event TEXT);
    CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY, user_id INTEGER, club_id INTEGER, body TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS flashcards(id INTEGER PRIMARY KEY, user_id INTEGER, book_id INTEGER, front TEXT, back TEXT, due TEXT, interval_days INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS rooms(id INTEGER PRIMARY KEY, name TEXT, branch TEXT, capacity INTEGER, status TEXT DEFAULT 'Available');
    CREATE TABLE IF NOT EXISTS automations(id INTEGER PRIMARY KEY, name TEXT, trigger_text TEXT, action_text TEXT, enabled INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY, name TEXT, contact TEXT, status TEXT DEFAULT 'Active');
    CREATE TABLE IF NOT EXISTS purchase_orders(id INTEGER PRIMARY KEY, supplier_id INTEGER, amount REAL, status TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS donations(id INTEGER PRIMARY KEY, title TEXT, donor TEXT, matched_to TEXT, status TEXT);
    CREATE TABLE IF NOT EXISTS resale(id INTEGER PRIMARY KEY, user_id INTEGER, book_id INTEGER, price REAL, condition_text TEXT, status TEXT DEFAULT 'Listed');
    CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, user_id INTEGER, action TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS audio_catalog(id INTEGER PRIMARY KEY, title TEXT NOT NULL, creator TEXT NOT NULL, kind TEXT NOT NULL, category TEXT NOT NULL, rating REAL NOT NULL DEFAULT 4.5, duration TEXT NOT NULL, description TEXT NOT NULL, accent TEXT NOT NULL DEFAULT 'violet', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS audio_bookmarks(user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, audio_id INTEGER NOT NULL REFERENCES audio_catalog(id) ON DELETE CASCADE, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id,audio_id));
    CREATE TABLE IF NOT EXISTS order_payment_choices(order_id INTEGER PRIMARY KEY REFERENCES orders(id) ON DELETE CASCADE, payment_method TEXT NOT NULL, fulfillment_mode TEXT NOT NULL DEFAULT 'standard', notes TEXT DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    ''')
    book_columns = {row['name'] for row in c.execute('PRAGMA table_info(books)').fetchall()}
    if 'original_price' not in book_columns: c.execute('ALTER TABLE books ADD COLUMN original_price REAL')
    if 'discount_percent' not in book_columns: c.execute('ALTER TABLE books ADD COLUMN discount_percent INTEGER NOT NULL DEFAULT 0')
    user_columns = {row['name'] for row in c.execute('PRAGMA table_info(users)').fetchall()}
    if 'username' not in user_columns:
        c.execute('ALTER TABLE users ADD COLUMN username TEXT')
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_unique ON users(lower(username)) WHERE username IS NOT NULL AND username != ''")
    # Enforce case-insensitive email uniqueness at the database layer. If a legacy
    # database already contains case-variant duplicates, preserve all accounts and
    # leave the index absent rather than deleting or rewriting user identities.
    duplicate_email = c.execute("SELECT 1 FROM users WHERE email IS NOT NULL GROUP BY lower(email) HAVING COUNT(*)>1 LIMIT 1").fetchone()
    if not duplicate_email:
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower_unique ON users(lower(email)) WHERE email IS NOT NULL AND email != ''")
    from database_performance import create_indexes
    create_indexes(c)
    if os.environ.get('LIBRAAI_ENV') != 'production' and c.execute("SELECT COUNT(*) n FROM users").fetchone()['n'] == 0:
        users=[('Reader Demo','reader@libra.ai',generate_password_hash('demo123'),'reader','Student'),('Library Admin','admin@libra.ai',generate_password_hash('demo123'),'admin','Institutional'),('Creator Demo','creator@libra.ai',generate_password_hash('demo123'),'creator','Creator')]
        c.executemany("INSERT INTO users(name,email,password,role,plan) VALUES(?,?,?,?,?)",users)
        c.execute("UPDATE users SET username='reader' WHERE lower(email)='reader@libra.ai' AND (username IS NULL OR username='')")
        c.execute("UPDATE users SET username='admin' WHERE lower(email)='admin@libra.ai' AND (username IS NULL OR username='')")
        c.execute("UPDATE users SET username='seller' WHERE lower(email)='creator@libra.ai' AND (username IS NULL OR username='')")
    if os.environ.get('LIBRAAI_ENV') != 'production':
        c.execute("UPDATE users SET username='reader' WHERE lower(email)='reader@libra.ai' AND (username IS NULL OR username='')")
        c.execute("UPDATE users SET username='admin' WHERE lower(email)='admin@libra.ai' AND (username IS NULL OR username='')")
        c.execute("UPDATE users SET username='seller' WHERE lower(email)='creator@libra.ai' AND (username IS NULL OR username='')")
    if os.environ.get('LIBRAAI_ENV') != 'production' and c.execute("SELECT COUNT(*) n FROM books").fetchone()['n'] == 0:
        books=[
        ('Atomic Habits','James Clear','Self Development',4.8,125400,52000,2018,'eBook · Print · Audio',499,34,'A practical guide to building better habits through small systems.','English','9780735211292','Central','A-12'),
        ('Deep Work','Cal Newport','Productivity',4.7,88200,34000,2016,'eBook · Print · Audio',420,18,'Strategies for focused success in a distracted world.','English','9781455586691','Central','A-14'),
        ('The Psychology of Money','Morgan Housel','Finance',4.8,102000,47000,2020,'eBook · Print · Audio',450,26,'Timeless lessons about wealth, greed and happiness.','English','9780857197689','North','F-08'),
        ('Clean Code','Robert C. Martin','Technology',4.6,73500,29000,2008,'eBook · Print',3400,12,'Principles and practices for writing maintainable software.','English','9780132350884','Central','T-04'),
        ('Sapiens','Yuval Noah Harari','History',4.6,150200,61000,2011,'eBook · Print · Audio',1450,20,'A broad exploration of humankind and civilization.','English','9780062316097','South','H-02'),
        ('The Alchemist','Paulo Coelho','Fiction',4.5,201500,85000,1988,'eBook · Print · Audio',899,41,'A fable about purpose, travel and personal legend.','English','9780061122415','Central','F-11'),
        ('Python Crash Course','Eric Matthes','Technology',4.7,55200,22000,2023,'eBook · Print',2999,16,'A hands-on introduction to Python projects.','English','9781718502703','North','T-07'),
        ('Bangla Literature Reader','LibraAI Editions','Literature',4.4,28400,7600,2025,'eBook · Print',699,50,'A demo bilingual reading collection for the LibraAI prototype.','Bangla','9780000000001','Central','B-01')]
        c.executemany("INSERT INTO books(title,author,genre,rating,reads,sales,year,format,price,stock,description,language,isbn,branch,shelf) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",books)
    if os.environ.get('LIBRAAI_ENV') != 'production':
        manga_defaults=[
          ('Solo Leveling','Chugong','Manga',4.9,98000,42000,2018,'Manga',399,25,'A dungeon hunter rises through a mysterious leveling system.','English','MANGA-001','Central','M-01'),
          ('One Piece','Eiichiro Oda','Manga',4.9,120000,56000,1997,'Manga',450,30,'A grand pirate adventure filled with friendship and discovery.','English','MANGA-002','Central','M-02'),
          ('Naruto','Masashi Kishimoto','Manga',4.8,115000,52000,1999,'Manga',420,28,'A young ninja works toward recognition and mastery.','English','MANGA-003','Central','M-03'),
          ('Demon Slayer','Koyoharu Gotouge','Manga',4.8,104000,47000,2016,'Manga',430,24,'A determined swordsman fights to protect his family.','English','MANGA-004','Central','M-04'),
          ('Attack on Titan','Hajime Isayama','Manga',4.8,110000,50000,2009,'Manga',460,22,'Humanity struggles to survive behind massive walls.','English','MANGA-005','North','M-05'),
          ('Jujutsu Kaisen','Gege Akutami','Manga',4.7,97000,43000,2018,'Manga',440,20,'A student enters a dangerous world of curses and sorcery.','English','MANGA-006','North','M-06'),
          ('My Hero Academia','Kohei Horikoshi','Manga',4.7,90000,39000,2014,'Manga',410,21,'A hopeful hero trains to make a difference in a superpowered world.','English','MANGA-007','South','M-07'),
          ('Haikyuu!!','Haruichi Furudate','Manga',4.8,76000,33000,2012,'Manga',390,18,'A volleyball team grows through practice, rivalry and teamwork.','English','MANGA-008','South','M-08'),
          ('Spy x Family','Tatsuya Endo','Manga',4.8,72000,31000,2019,'Manga',400,19,'A spy, an assassin and a telepath form an unusual family.','English','MANGA-009','Central','M-09'),
          ('Blue Lock','Muneyuki Kaneshiro','Manga',4.7,68000,29000,2018,'Manga',405,17,'Elite young strikers compete to become Japan’s ultimate forward.','English','MANGA-010','Central','M-10')
        ]
        for manga in manga_defaults:
            row=c.execute('SELECT id FROM books WHERE isbn=?',(manga[11],)).fetchone()
            if not row:
                c.execute("INSERT INTO books(title,author,genre,rating,reads,sales,year,format,price,stock,description,language,isbn,branch,shelf) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",manga)
                bid=c.lastrowid
            else: bid=row['id']
            c.execute('INSERT OR IGNORE INTO catalog_products(book_id,product_type,sale_enabled,digital_available,inventory_quantity,access_type) VALUES(?,?,?,?,?,?)',(bid,'manga',1,1,manga[9],'purchase'))
    if os.environ.get('LIBRAAI_ENV') != 'production':
        demo_products = [('The Midnight Library', 'Matt Haig', 'Fiction', 4.7, 85000, 32000, 2020, 'eBook · Print · Audio', 620, 25, 'A novel about second chances and the lives we might have lived.'), ('Educated', 'Tara Westover', 'Memoir', 4.7, 63000, 21000, 2018, 'eBook · Print', 780, 14, 'A memoir about education, family and self-invention.'), ('Think Again', 'Adam Grant', 'Psychology', 4.6, 44000, 16000, 2021, 'eBook · Print · Audio', 560, 19, 'Learn to rethink assumptions and stay curious.'), ('The Design of Everyday Things', 'Don Norman', 'Design', 4.6, 39000, 13000, 2013, 'eBook · Print', 1250, 11, 'A foundational guide to human-centred design.'), ('Start With Why', 'Simon Sinek', 'Business', 4.5, 55000, 22000, 2009, 'eBook · Print · Audio', 650, 17, 'A framework for purpose-led leadership.'), ('The Lean Startup', 'Eric Ries', 'Business', 4.5, 47000, 18000, 2011, 'eBook · Print', 720, 13, 'Build, measure and learn with disciplined experiments.'), ('The Hobbit', 'J.R.R. Tolkien', 'Fantasy', 4.8, 99000, 46000, 1937, 'eBook · Print · Audio', 850, 22, 'A classic adventure into Middle-earth.'), ('The Name of the Wind', 'Patrick Rothfuss', 'Fantasy', 4.6, 52000, 19000, 2007, 'eBook · Print', 990, 9, 'A lyrical fantasy about a gifted young musician.'), ('The Silent Patient', 'Alex Michaelides', 'Thriller', 4.5, 78000, 35000, 2019, 'eBook · Print · Audio', 590, 24, 'A psychological thriller built around a silent artist.'), ('Gone Girl', 'Gillian Flynn', 'Thriller', 4.4, 69000, 30000, 2012, 'eBook · Print', 650, 16, 'A twist-filled story of marriage and media.'), ('Ikigai', 'Héctor García', 'Self Development', 4.5, 102000, 51000, 2016, 'eBook · Print · Audio', 480, 31, 'Japanese ideas for a meaningful everyday life.'), ('The 5 AM Club', 'Robin Sharma', 'Self Development', 4.4, 59000, 26000, 2018, 'eBook · Print', 560, 18, 'A routine-focused approach to personal growth.'), ('Rich Dad Poor Dad', 'Robert Kiyosaki', 'Finance', 4.5, 145000, 72000, 1997, 'eBook · Print · Audio', 520, 37, 'Personal finance lessons about assets and mindset.'), ('The Intelligent Investor', 'Benjamin Graham', 'Finance', 4.6, 41000, 15000, 1949, 'eBook · Print', 1350, 8, 'A classic introduction to value investing principles.'), ('A Brief History of Time', 'Stephen Hawking', 'Science', 4.6, 61000, 24000, 1988, 'eBook · Print · Audio', 780, 12, 'A readable journey through cosmology and time.'), ('The Body', 'Bill Bryson', 'Science', 4.6, 37000, 12000, 2019, 'eBook · Print', 920, 10, 'An engaging tour of the human body.'), ('Pride and Prejudice', 'Jane Austen', 'Classic', 4.8, 83000, 42000, 1813, 'eBook · Print · Audio', 390, 28, 'A beloved classic of manners, family and romance.'), ('The Great Gatsby', 'F. Scott Fitzgerald', 'Classic', 4.4, 75000, 33000, 1925, 'eBook · Print', 420, 20, 'A portrait of ambition and the Jazz Age.'), ('The Art of War', 'Sun Tzu', 'Strategy', 4.5, 66000, 28000, -500, 'eBook · Print', 350, 23, 'An enduring text on strategy and leadership.'), ('Show Your Work!', 'Austin Kleon', 'Creativity', 4.5, 29000, 11000, 2014, 'eBook · Print', 540, 15, 'Practical encouragement for sharing creative work.'), ('Steal Like an Artist', 'Austin Kleon', 'Creativity', 4.6, 35000, 15000, 2012, 'eBook · Print', 490, 18, 'A short guide to creative influence and practice.'), ('The Pragmatic Programmer', 'David Thomas', 'Technology', 4.7, 46000, 17000, 1999, 'eBook · Print', 1850, 12, 'Timeless practices for effective software development.'), ('Designing Data-Intensive Applications', 'Martin Kleppmann', 'Technology', 4.8, 33000, 12000, 2017, 'eBook · Print', 2450, 7, 'A deep guide to modern data systems.'), ('JavaScript: The Good Parts', 'Douglas Crockford', 'Technology', 4.3, 28000, 10000, 2008, 'eBook · Print', 890, 13, 'A concise tour of JavaScript language patterns.'), ('The Little Prince', 'Antoine de Saint-Exupéry', 'Classic', 4.8, 90000, 47000, 1943, 'eBook · Print · Audio', 460, 29, 'A poetic fable about friendship and seeing clearly.'), ('Before the Coffee Gets Cold', 'Toshikazu Kawaguchi', 'Fiction', 4.4, 48000, 22000, 2015, 'eBook · Print', 610, 16, 'A café offers visitors a chance to revisit the past.'), ('Convenience Store Woman', 'Sayaka Murata', 'Fiction', 4.2, 25000, 9000, 2016, 'eBook · Print', 530, 10, 'A sharp, unconventional story about belonging.'), ('The Song of Achilles', 'Madeline Miller', 'Historical Fiction', 4.7, 72000, 36000, 2011, 'eBook · Print · Audio', 740, 19, 'A retelling of the myth of Achilles and Patroclus.')]
        for product in demo_products:
            if not c.execute('SELECT 1 FROM books WHERE title=?',(product[0],)).fetchone():
                c.execute('INSERT INTO books(title,author,genre,rating,reads,sales,year,format,price,stock,description,language,isbn,branch,shelf) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (*product,'English','', 'Central','S-01'))
        c.execute("UPDATE books SET discount_percent=CASE WHEN id % 4=0 THEN 15 WHEN id % 3=0 THEN 10 ELSE 5 END, original_price=ROUND(price/(1-(CASE WHEN id % 4=0 THEN 15 WHEN id % 3=0 THEN 10 ELSE 5 END)/100.0),2) WHERE original_price IS NULL AND price>0")
        store_items = [
            ('LibraAI Reading Journal','LibraAI Studio','Stationery & Gifts',4.8,12000,4300,2026,'Print',390,45,'A linen-finish journal for reading notes, reflections and favourite quotes.'),
            ('Premium Bookmark Set','LibraAI Studio','Stationery & Gifts',4.7,9800,3600,2026,'Print',180,120,'A set of four illustrated bookmarks with soft-touch finish.'),
            ('Weekly Study Planner','LibraAI Studio','Study Materials',4.6,8700,3100,2026,'Print',320,60,'A structured weekly planner for study sessions and reading goals.'),
            ('Canvas Book Tote','LibraAI Studio','Reader Accessories',4.8,7600,2800,2026,'Print',550,32,'A durable everyday tote sized for your current read and notebook.'),
        ]
        for product in store_items:
            if not c.execute('SELECT 1 FROM books WHERE title=?',(product[0],)).fetchone():
                c.execute('INSERT INTO books(title,author,genre,rating,reads,sales,year,format,price,stock,description,language,isbn,branch,shelf) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (*product,'English','', 'Central','S-02'))
        # Keep a browsable audio shelf in development; these are sample metadata, not licensed full recordings.
        audio_items = [(1, 'Atomic Habits', 'James Clear', 'Audiobook', 'Personal Growth', 4.9, '5h 35m', 'Small changes, remarkable results. A practical guide to building lasting habits.', 'violet'), (2, 'The Psychology of Money', 'Morgan Housel', 'Audiobook', 'Business', 4.8, '5h 48m', 'Timeless lessons about wealth, behaviour and long-term thinking.', 'gold'), (3, 'Ikigai', 'Héctor García & Francesc Miralles', 'Audiobook', 'Wellbeing', 4.7, '3h 12m', 'Explore the Japanese concept of purpose and everyday meaning.', 'mint'), (4, 'Deep Work', 'Cal Newport', 'Audiobook', 'Productivity', 4.8, '7h 44m', 'Build focus and do meaningful work in a distracted world.', 'blue'), (5, 'The Midnight Library', 'Matt Haig', 'Audiobook', 'Fiction', 4.7, '8h 50m', 'A moving story about choices, possibility and second chances.', 'rose'), (6, 'Sapiens', 'Yuval Noah Harari', 'Audiobook', 'History', 4.8, '15h 17m', 'A sweeping story of humankind and the ideas that shaped us.', 'gold'), (7, 'The Little Prince', 'Antoine de Saint-Exupéry', 'Audiobook', 'Classics', 4.9, '2h 10m', 'A timeless fable about friendship, imagination and love.', 'blue'), (8, 'Think Again', 'Adam Grant', 'Audiobook', 'Psychology', 4.6, '8h  rethink', 'Discover the power of knowing what you do not know.', 'mint'), (9, 'The Hobbit', 'J.R.R. Tolkien', 'Audiobook', 'Fantasy', 4.9, '11h 8m', 'Join Bilbo Baggins on an unexpected adventure.', 'violet'), (10, 'The Alchemist', 'Paulo Coelho', 'Audiobook', 'Fiction', 4.7, '4h 0m', 'A journey toward dreams, courage and personal legend.', 'rose'), (11, 'The Daily Stoic', 'Ryan Holiday', 'Audiobook', 'Philosophy', 4.6, '7h 8m', 'Short reflections on clarity, resilience and the good life.', 'gold'), (12, 'The Design of Everyday Things', 'Don Norman', 'Audiobook', 'Design', 4.7, '7h 20m', 'Understand why good design makes everyday life easier.', 'blue'), (13, 'The Creative Act', 'Rick Rubin', 'Audiobook', 'Creativity', 4.8, '5h 55m', 'A generous meditation on the creative process.', 'mint'), (14, 'Pride and Prejudice', 'Jane Austen', 'Audiobook', 'Classics', 4.8, '11h 35m', 'A witty classic of first impressions and lasting affection.', 'rose'), (15, 'A Brief History of Time', 'Stephen Hawking', 'Audiobook', 'Science', 4.6, '5h 0m', 'Big questions about the universe, explained with wonder.', 'violet'), (16, 'The Curious Reader', 'LibraAI Studio', 'Podcast', 'Culture', 4.8, '28 min', 'Weekly conversations about books, ideas and the people behind them.', 'gold'), (17, 'Pages & Perspectives', 'LibraAI Studio', 'Podcast', 'Interviews', 4.7, '34 min', 'Authors and readers share the stories that changed their thinking.', 'blue'), (18, 'The Learning Loop', 'LibraAI Studio', 'Podcast', 'Learning', 4.9, '22 min', 'Practical conversations on curiosity, memory and lifelong learning.', 'mint'), (19, 'Quiet Chapters', 'LibraAI Studio', 'Podcast', 'Wellbeing', 4.6, '19 min', 'A calm pause with reflections, reading rituals and mindful ideas.', 'rose'), (20, 'Future in Focus', 'LibraAI Studio', 'Podcast', 'Technology', 4.7, '31 min', 'Explore technology, creativity and the future of knowledge.', 'violet')]
        for item in audio_items:
            c.execute('INSERT OR IGNORE INTO audio_catalog(id,title,creator,kind,category,rating,duration,description,accent) VALUES(?,?,?,?,?,?,?,?,?)', item)
    if os.environ.get('LIBRAAI_ENV') != 'production' and c.execute("SELECT COUNT(*) n FROM clubs").fetchone()['n'] == 0:
        c.executemany("INSERT INTO clubs(name,topic,members,next_event) VALUES(?,?,?,?)",[
            ('Future Readers','Technology & AI',1280,'Friday 20:00'),('Mystery Circle','Mystery & Thriller',846,'Saturday 19:00'),('Bangla Book Club','Bangla Literature',620,'Sunday 18:30')])
    if os.environ.get('LIBRAAI_ENV') != 'production' and c.execute("SELECT COUNT(*) n FROM rooms").fetchone()['n'] == 0:
        c.executemany("INSERT INTO rooms(name,branch,capacity,status) VALUES(?,?,?,?)", [('Focus Pod 1','Central',4,'Available'),('Research Room','Central',8,'Available'),('Group Room','North',10,'Booked')])
    if os.environ.get('LIBRAAI_ENV') != 'production' and c.execute("SELECT COUNT(*) n FROM automations").fetchone()['n'] == 0:
        c.executemany("INSERT INTO automations(name,trigger_text,action_text) VALUES(?,?,?)",[
            ('Due-date reminder','Loan due in 2 days','Notify reader'),('Low inventory','Stock < 5','Alert acquisitions'),('Waitlist release','Copy returned','Offer to next reader'),('Demand signal','7-day demand spike','Create forecast alert')])
    if os.environ.get('LIBRAAI_ENV') != 'production' and c.execute("SELECT COUNT(*) n FROM suppliers").fetchone()['n'] == 0:
        c.executemany("INSERT INTO suppliers(name,contact,status) VALUES(?,?,?)", [('Global Books Ltd','orders@global.demo','Active'),('Dhaka Academic Supply','supply@dhaka.demo','Active')])
    # Upgrade legacy demo plaintext passwords when opening an existing project database.
    for row in c.execute("SELECT id,password FROM users").fetchall():
        if os.environ.get('LIBRAAI_ENV') != 'production' and not row['password'].startswith(('scrypt:', 'pbkdf2:')):
            c.execute("UPDATE users SET password=? WHERE id=?", (generate_password_hash(row['password']),row['id']))
    # Backfill shared catalog inventory from the existing books table; safe on every startup.
    c.execute("INSERT OR IGNORE INTO catalog_products(book_id,product_type,sale_enabled,digital_available,inventory_quantity,access_type) SELECT id, CASE WHEN lower(format) LIKE '%audio%' AND lower(format) NOT LIKE '%print%' THEN 'audiobook' WHEN lower(format) LIKE '%ebook%' THEN 'ebook' ELSE 'physical_book' END, 1, CASE WHEN lower(format) LIKE '%ebook%' OR lower(format) LIKE '%audio%' THEN 1 ELSE 0 END, MAX(COALESCE(stock,0),0), 'purchase' FROM books")
    setup_commerce(c)
    if os.environ.get('LIBRAAI_ENV') != 'production':
        c.execute("UPDATE books SET discount_percent=CASE WHEN id % 4=0 THEN 15 WHEN id % 3=0 THEN 10 ELSE 5 END, original_price=ROUND(price/(1-(CASE WHEN id % 4=0 THEN 15 WHEN id % 3=0 THEN 10 ELSE 5 END)/100.0),2) WHERE original_price IS NULL AND price>0")
        c.execute("UPDATE catalog_products SET product_type='stationery' WHERE book_id IN (SELECT id FROM books WHERE genre IN ('Stationery & Gifts','Reader Accessories'))")
        c.execute("UPDATE catalog_products SET product_type='study_material' WHERE book_id IN (SELECT id FROM books WHERE genre='Study Materials')")
    if os.environ.get('LIBRAAI_ENV') == 'production':
        from credential_integrity import require_secure_credentials
        try:
            require_secure_credentials(c)
        except Exception:
            c.rollback()
            c.close()
            raise
    c.commit(); c.close()

# --------------------------- Helpers ---------------------------
def credential_fingerprint(password_hash):
    """Opaque session binding: credential changes invalidate other signed-in sessions."""
    return hashlib.sha256(str(password_hash).encode('utf-8')).hexdigest()

def current_user():
    if not session.get('uid'): return None
    c=db()
    try:
        u=c.execute("SELECT * FROM users WHERE id=?",(session['uid'],)).fetchone()
    finally:
        c.close()
    # Suspended member records revoke existing sessions immediately.
    if u is not None:
        with db() as status_db:
            has_controls=status_db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='member_controls'").fetchone()
            status=status_db.execute("SELECT status FROM member_controls WHERE user_id=?",(u['id'],)).fetchone() if has_controls else None
        if status and status['status']=='suspended':
            session.clear(); return None
    # Requiring this binding invalidates legacy sessions and sessions issued
    # before a password change, without storing the password hash in the cookie.
    issued_fingerprint=session.get('_credential_fingerprint')
    if u is None or not issued_fingerprint or not hmac.compare_digest(
            issued_fingerprint, credential_fingerprint(u['password'])):
        session.clear()
        return None
    return u

def login_required(fn):
    @wraps(fn)
    def w(*a,**k):
        if not current_user(): flash('Please sign in to use this feature.'); return redirect(url_for('login'))
        return fn(*a,**k)
    return w

def audit(action):
    if session.get('uid'):
        c=db(); c.execute("INSERT INTO audit(user_id,action,created) VALUES(?,?,?)",(session['uid'],action,datetime.now().isoformat(timespec='seconds'))); c.commit(); c.close()

def score_book(b, mode='trending'):
    # Transparent demo metric: normalized reads + sales + rating + recency; replace with fraud-filtered qualified sessions in production.
    recency=max(0, 1-(datetime.now().year-b['year'])/25)
    if mode=='rated': return b['rating']
    if mode=='bestseller': return b['sales']
    if mode=='new': return b['year']
    return math.log10(b['reads']+1)*.45 + math.log10(b['sales']+1)*.25 + b['rating']*.2 + recency*.1

def book_rows(order='trending', genre=None, q=None):
    c=db(); rows=[dict(x) for x in c.execute("SELECT b.*, COALESCE(cp.product_type,'physical_book') AS product_type, COALESCE(cp.sale_enabled,1) AS sale_enabled, COALESCE(cp.digital_available,0) AS digital_available, COALESCE(cp.inventory_quantity,b.stock,0) AS inventory_quantity, COALESCE(cp.access_type,'purchase') AS access_type, CASE WHEN COALESCE(cp.sale_enabled,1)=0 THEN 'Unavailable' WHEN COALESCE(cp.digital_available,0)=1 THEN 'Available Online' WHEN COALESCE(cp.inventory_quantity,b.stock,0)>0 THEN 'In Stock' ELSE 'Out of Stock' END AS availability_status FROM books b LEFT JOIN catalog_products cp ON cp.book_id=b.id").fetchall()]; c.close()
    if genre and genre!='All': rows=[b for b in rows if b['genre']==genre]
    if q:
        q=q.lower(); rows=[b for b in rows if q in (b['title']+' '+b['author']+' '+b['genre']+' '+b['isbn']).lower()]
    rows.sort(key=lambda b: score_book(b, order), reverse=True)
    return rows

BASE='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{title}} · LibraAI</title><style>
:root{--bg:#f6f8fc;--card:#fff;--ink:#17223b;--muted:#6b7894;--primary:#5b5bd6;--line:#e6eaf2;--green:#12a67a;--shadow:0 16px 40px rgba(35,48,90,.08)}*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;background:var(--bg);color:var(--ink)}a{text-decoration:none;color:inherit}.shell{display:grid;grid-template-columns:250px 1fr;min-height:100vh}.side{padding:24px 16px;background:#fff;border-right:1px solid var(--line);position:sticky;top:0;height:100vh;overflow:auto}.brand{font-weight:900;font-size:23px;color:var(--primary);padding:4px 10px 22px}.nav a{display:block;padding:10px 12px;margin:3px 0;border-radius:11px;color:#52617e;font-size:14px}.nav a:hover{background:#f0f1ff;color:var(--primary)}main{padding:26px 32px 60px;max-width:1500px;width:100%}.top{display:flex;gap:12px;justify-content:space-between;align-items:center;margin-bottom:24px}.search{background:#fff;border:1px solid var(--line);border-radius:14px;padding:12px 16px;min-width:300px}.btn{display:inline-block;border:0;border-radius:11px;padding:10px 14px;background:var(--primary);color:#fff;cursor:pointer;font-weight:700}.btn.ghost{background:#eef0ff;color:var(--primary)}.btn.green{background:var(--green)}h1{font-size:30px;margin:0 0 8px}h2{font-size:20px;margin:28px 0 12px}.muted{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px}.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:var(--shadow)}.book{min-height:260px}.cover{height:130px;border-radius:13px;background:linear-gradient(135deg,#dfe3ff,#f7e9ff);display:flex;align-items:center;justify-content:center;font-size:42px;margin-bottom:14px}.pill{display:inline-block;background:#eef0ff;color:#4e55bd;padding:5px 9px;border-radius:999px;font-size:12px;margin:2px}.kpi{font-size:29px;font-weight:900}.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.between{justify-content:space-between}.flash{background:#fff4cf;border:1px solid #f0d879;padding:10px 14px;border-radius:10px;margin-bottom:14px}.table{width:100%;border-collapse:collapse;background:#fff;border-radius:14px;overflow:hidden}.table th,.table td{padding:12px;border-bottom:1px solid var(--line);text-align:left;font-size:14px}.reader{background:#fffdf8;min-height:560px;padding:36px;border-radius:18px;box-shadow:var(--shadow);line-height:1.8;font-family:Georgia,serif}.reader.two{columns:2;column-gap:60px}.input,select,textarea{width:100%;padding:11px 12px;border:1px solid #dfe4ee;border-radius:10px;background:#fff;margin:5px 0 10px}.tabs a{margin-right:7px}.hero{padding:30px;background:linear-gradient(120deg,#ffffff,#eef0ff);border:1px solid var(--line);border-radius:22px}.bar{height:9px;background:#edf0f6;border-radius:9px;overflow:hidden}.bar i{display:block;height:100%;background:var(--primary)}.chat{max-width:850px}.msg{padding:12px 14px;border-radius:14px;margin:8px 0;background:#fff;border:1px solid var(--line)}.msg.ai{background:#f0f1ff}.small{font-size:12px}.footer{margin-top:40px;color:var(--muted);font-size:12px}.mobile{display:none}@media(max-width:850px){.shell{display:block}.side{position:relative;height:auto;border-right:0}.nav{display:flex;overflow:auto}.nav a{white-space:nowrap}.side .brand{padding-bottom:8px}main{padding:18px}.search{min-width:0;width:100%}.top{align-items:stretch;flex-direction:column}.reader.two{columns:1}}

/* Premium midnight dashboard option inspired by PDF concept screen 13. */
body.midnight{--bg:#090f26;--card:#101a36;--ink:#eaf0ff;--muted:#a6b4d2;--primary:#8570ff;--line:#27355b;--green:#29c7a3;--shadow:0 18px 45px rgba(0,0,0,.24);background:var(--bg);color:var(--ink)}
body.midnight .side,body.midnight .card,body.midnight .table,body.midnight .search,body.midnight .input,body.midnight select,body.midnight textarea,body.midnight .msg{background:var(--card);color:var(--ink);border-color:var(--line)}
body.midnight .hero{background:linear-gradient(115deg,#20265d,#111a38 65%,#302257);border-color:var(--line)}
body.midnight .cover{background:linear-gradient(140deg,#293e80,#5c357f);color:#f4efff}
body.midnight .nav a{color:#b7c6e5}body.midnight .nav a:hover{background:#24315c;color:#fff}
body.midnight .pill,body.midnight .btn.ghost{background:#282957;color:#d9d1ff}
body.midnight .reader{background:#f7f0df;color:#27243a}body.midnight .table th,body.midnight .table td{border-color:var(--line)}
.theme-toggle{border:1px solid var(--line);background:var(--card);color:var(--ink);padding:9px 12px;border-radius:12px;cursor:pointer;font-weight:700}
:focus-visible{outline:3px solid #a594ff;outline-offset:3px}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important;scroll-behavior:auto!important}}
</style><link rel="stylesheet" href="/assets/premium_ui.css"><link rel="manifest" href="/manifest.webmanifest"><meta name="theme-color" content="#101a36"></head><body><a class="skip-link" href="#main-content">Skip to main content</a><div class="shell"><aside class="side"><div class="brand">LibraAI</div><nav class="nav" aria-label="Main navigation">
<a href="/">⌂ Dashboard</a><a href="/discover">⌕ Discover</a><a href="/library">▣ My Library</a><a href="/reader/1">☰ Reader</a><a href="/reader-plus/1">◫ Licensed Reader</a><a href="/ai">✦ AI Tutor</a><a href="/marketplace">🛒 Marketplace</a><a href="/community">◎ Community</a><a href="/study">▤ Study Tools</a><a href="/learning/">◈ Learning Studio</a><a href="/learning/planner">🎯 Planner</a><a href="/saved-searches">⌕ Saved Searches</a><a href="/my/waitlist">☷ My Waitlist</a><a href="/verified-reading">🏆 Rankings</a><a href="/refunds">↩ Refunds</a><a href="/analytics">↗ Analytics</a>{% if user and user['role']=='admin' %}<a href="/admin/dashboard">⚙ Library Admin</a>{% endif %}{% if user and user['role'] in ('creator','admin') %}<a href="/creator">✎ Creator Portal</a>{% endif %}{% if user and user['role'] in ('librarian','admin') %}<a href="/librarian">▣ Circulation Desk</a>{% endif %}{% if user and user['role'] in ('creator','admin') %}<a href="/creator/royalties">৳ Royalties</a>{% endif %}{% if user and user['role']=='admin' %}<a href="/admin/waitlist">⚙ Waitlist Ops</a><a href="/admin/refunds">↩ Refund Review</a><a href="/admin/royalty-contracts">৳ Royalty Contracts</a><a href="/admin/royalty-payouts">৳ Creator Payouts</a><a href="/admin/licensed-content">▣ Licensed Content</a><a href="/admin/audiobook-library">♫ Audiobook Hosting</a>{% endif %}<a href="/research/">⌁ Research Lab</a><a href="/my-alerts">♧ My Alerts</a><a href="/privacy">♧ Privacy</a><a href="/account">♙ My Account</a><a href="/support">☏ Support</a><a href="/features">✓ Feature Map</a></nav></aside><main id="main-content" tabindex="-1">
<div class="top"><button class="theme-toggle" type="button" id="themeToggle" aria-label="Switch color theme">☾ Theme</button><form action="/discover"><input class="search" name="q" aria-label="Search books, authors, ISBN and topics" placeholder="Search books, authors, ISBN, topics…"></form><div>{% if user %}<span class="pill">{{user['plan']}}</span> {{user['name']}} · <form method="post" action="/logout" style="display:inline"><button class="btn ghost" type="submit">Sign out</button></form>{% else %}<a class="btn" href="/login">Sign in</a>{% endif %}</div></div>
{% with ms=get_flashed_messages() %}{% for m in ms %}<div class="flash">{{m}}</div>{% endfor %}{% endwith %}{{body|safe}}<div class="footer">LibraAI development build · Python/Flask + SQLite · Light-mode-first responsive SaaS UI · Bangla/English-ready · PWA/integration-ready architecture</div></main></div><script>
(function(){const key='libraai-theme';const toggle=document.getElementById('themeToggle');let mode='light';try{mode=localStorage.getItem(key)||'light'}catch(e){}document.body.classList.toggle('light-ui',mode==='light');document.body.classList.toggle('midnight',mode==='midnight');if(toggle){toggle.setAttribute('aria-pressed',String(mode==='midnight'));toggle.addEventListener('click',function(){const on=document.body.classList.toggle('midnight');document.body.classList.toggle('light-ui',!on);toggle.setAttribute('aria-pressed',String(on));try{localStorage.setItem(key,on?'midnight':'light')}catch(e){}})}if('serviceWorker' in navigator){window.addEventListener('load',()=>navigator.serviceWorker.register('/service-worker.js').catch(()=>{}))}})();
</script></body></html>'''

def page(title, body, **ctx):
    html = render_template_string(BASE, title=title, body=render_template_string(body, **ctx), user=current_user())
    # Inject CSRF into HTML forms, including forms generated by extension modules.
    if '<form' in html.lower():
        import re as _re
        token = session.setdefault('_csrf', secrets.token_urlsafe(32))
        html = _re.sub(r'(<form\b[^>]*>)',lambda m: m.group(1)+'<input type="hidden" name="_csrf" value="'+token+'">',html,flags=_re.I)
    return html

# --------------------------- Auth ---------------------------
@app.get('/api/csrf')
def frontend_csrf_token():
    # Same-origin Next.js proxy clients fetch a session-bound token before POSTing.
    token = session.setdefault('_csrf', secrets.token_urlsafe(32))
    response = jsonify({'csrfToken': token})
    response.headers['Cache-Control'] = 'no-store'
    return response

def _auth_json_error(message, status=400):
    return jsonify({'ok': False, 'error': message, 'message': message}), status


def _auth_json_user(user):
    if not user:
        return None
    return {
        'id': int(user['id']), 'name': user['name'], 'username': user['username'],
        'email': user['email'], 'role': user['role'], 'plan': user['plan'],
        'account_type': {'reader': 'customer', 'creator': 'merchant', 'admin': 'admin', 'librarian': 'librarian'}.get(user['role'], user['role']),
    }


def _workspace_for_role(user):
    role = str(user['role'] or 'reader').lower()
    return {'creator': '/creator', 'admin': '/admin/dashboard', 'librarian': '/librarian'}.get(role, '/')


@app.get('/api/me')
@app.get('/api/auth/me')
def api_current_user():
    user = current_user()
    payload = _auth_json_user(user)
    if payload:
        payload['redirect'] = _workspace_for_role(user)
    response = jsonify(payload)
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@app.post('/api/signup')
@app.post('/api/auth/signup')
def api_signup():
    if not request.is_json:
        return _auth_json_error('Send registration details as JSON.', 415)
    data = request.get_json(silent=True) or {}
    from account_registration import PUBLIC_ACCOUNT_TYPES, AccountRegistrationError, create_account
    name = data.get('name', '')
    email = data.get('email', '')
    password = data.get('password', '')
    account_type = data.get('role', data.get('account_type', 'customer'))
    if isinstance(account_type, str) and account_type in ('reader', 'buyer'):
        account_type = 'customer'
    if isinstance(account_type, str) and account_type in ('seller', 'creator'):
        account_type = 'merchant'
    if not isinstance(account_type, str) or account_type not in PUBLIC_ACCOUNT_TYPES:
        return _auth_json_error('Choose a customer or seller account.', 400)
    key = identity_key('signup', request.remote_addr or 'unknown', app.secret_key)
    conn = db()
    try:
        if blocked(conn, key):
            return _auth_json_error('Too many signup attempts. Please try again in 15 minutes.', 429)
        role, plan = PUBLIC_ACCOUNT_TYPES[account_type]
        try:
            user_id, password_hash = create_account(
                conn, name, email, password, role, plan, generate_password_hash,
                data.get('store_name') if account_type == 'merchant' else None,
                data.get('username'),
            )
        except AccountRegistrationError as exc:
            failed(conn, key)
            message = str(exc)
            status = 409 if ('already registered' in message.lower() or 'username is already taken' in message.lower()) else 400
            return _auth_json_error(message, status)
        except sqlite3.IntegrityError:
            failed(conn, key)
            return _auth_json_error('This email or username is already registered.', 409)
        clear(conn, key)
        user = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        session.clear()
        session['uid'] = user_id
        session['_credential_fingerprint'] = credential_fingerprint(password_hash)
        start_authenticated_session(session)
        session['_csrf'] = secrets.token_urlsafe(32)
        audit('Created ' + account_type + ' account')
        response = jsonify({'ok': True, 'user': _auth_json_user(user), 'redirect': _workspace_for_role(user)})
        response.status_code = 201
        response.headers['Cache-Control'] = 'private, no-store'
        return response
    finally:
        conn.close()


@app.post('/api/login')
@app.post('/api/auth/login')
def api_login():
    if not request.is_json:
        return _auth_json_error('Send sign-in details as JSON.', 415)
    data = request.get_json(silent=True) or {}
    identifier = str(data.get('identifier') or data.get('email') or data.get('username') or '').strip()[:254]
    supplied_password = data.get('password', '')
    if not identifier or not isinstance(supplied_password, str) or not supplied_password or len(supplied_password) > 128:
        return _auth_json_error('Enter your username or email and a valid password.', 400)
    key = identity_key(identifier, request.remote_addr or '', app.secret_key)
    conn = db()
    try:
        if blocked(conn, key):
            return _auth_json_error('Too many sign-in attempts. Please try again in 15 minutes.', 429)
        if '@' in identifier:
            user = conn.execute('SELECT * FROM users WHERE lower(email)=?', (identifier.lower(),)).fetchone()
        else:
            matches = conn.execute(
                'SELECT * FROM users WHERE lower(username)=? ORDER BY id DESC LIMIT 2',
                (identifier.lower(),),
            ).fetchall()
            # Legacy accounts without usernames may still sign in by their exact name
            # only when that name maps to one account.
            if not matches:
                matches = conn.execute(
                    'SELECT * FROM users WHERE username IS NULL AND lower(name)=? ORDER BY id DESC LIMIT 2',
                    (identifier.lower(),),
                ).fetchall()
            user = matches[0] if len(matches) == 1 else None
        if not user or not check_password_hash(user['password'], supplied_password):
            failed(conn, key)
            return _auth_json_error('Username/email or password is incorrect. Please try again.', 401)
        clear(conn, key)
        session.clear()
        session['uid'] = int(user['id'])
        session['_credential_fingerprint'] = credential_fingerprint(user['password'])
        start_authenticated_session(session)
        session['_csrf'] = secrets.token_urlsafe(32)
        audit('Signed in')
        response = jsonify({'ok': True, 'user': _auth_json_user(user), 'redirect': _workspace_for_role(user)})
        response.headers['Cache-Control'] = 'private, no-store'
        return response
    finally:
        conn.close()


@app.post('/api/logout')
@app.post('/api/auth/logout')
def api_logout():
    if not current_user():
        session.clear()
        return jsonify({'ok': True, 'redirect': '/'}), 200
    session.clear()
    response = jsonify({'ok': True, 'redirect': '/'})
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@app.get('/dashboard')
@app.get('/dashboard.html')
def dashboard_compatibility_redirect():
    if not current_user():
        return redirect(url_for('login'))
    return redirect(_workspace_for_role(current_user()))


@app.route('/login',methods=['GET','POST'])
def login():
    frontend_json = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if request.method=='POST':
        identifier=(request.form.get('identifier') or request.form.get('email','')).strip()[:254]
        email=identifier.lower()
        key=identity_key(email,request.remote_addr or '',app.secret_key)
        c=db()
        try:
            if blocked(c,key):
                if frontend_json: return jsonify({'ok':False,'message':'Too many sign-in attempts. Please try again in 15 minutes.'}), 429
                flash('Too many sign-in attempts. Please try again in 15 minutes.')
            else:
                if '@' in identifier:
                    u=c.execute("SELECT * FROM users WHERE lower(email)=?",(email,)).fetchone()
                else:
                    matches=c.execute("SELECT * FROM users WHERE lower(username)=? OR (username IS NULL AND lower(name)=?) ORDER BY id DESC LIMIT 2",(identifier.lower(),identifier.lower())).fetchall()
                    u=matches[0] if len(matches)==1 else None
                if u and check_password_hash(u['password'],request.form.get('password','')) and not (c.execute("SELECT 1 FROM member_controls WHERE user_id=? AND status='suspended'",(u['id'],)).fetchone() if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='member_controls'").fetchone() else False):
                    clear(c,key)
                    session.clear(); session['uid']=u['id']
                    session['_credential_fingerprint'] = credential_fingerprint(u['password'])
                    start_authenticated_session(session)
                    session['_csrf'] = secrets.token_urlsafe(32)
                    audit('Signed in')
                    if frontend_json: return jsonify({'ok':True,'redirect':_workspace_for_role(u)})
                    return redirect(_workspace_for_role(u))
                failed(c,key)
                if frontend_json: return jsonify({'ok':False,'message':'Username/email or password is incorrect. Please try again.'}), 401
                flash('Invalid email or password.')
        finally:
            c.close()
    demo = os.environ.get('LIBRAAI_ENV') != 'production'
    return page('Sign in','''<div class="card" style="max-width:480px;margin:auto"><h1>Welcome back</h1><p class="muted">Sign in to your LibraAI account.</p><form method="post"><label>Username or email</label><input class="input" type="text" name="identifier" autocomplete="username" required><label>Password</label><input class="input" type="password" name="password" autocomplete="current-password" maxlength="128" required><button class="btn">Sign in</button></form><p class="muted small">New to LibraAI? <a href="/register" style="color:#6953d9">Create an account</a></p>{% if demo %}<p class="small muted">Local development demo: reader@libra.ai / demo123</p>{% endif %}</div>''',demo=demo)

@app.route('/logout',methods=['POST'])
@login_required
def logout():
    session.clear()
    return redirect('/welcome')

# --------------------------- Dashboard & discovery ---------------------------
@app.route('/')
def home():
    if not current_user():
        from flask import send_from_directory
        return send_from_directory(os.path.dirname(__file__), 'landing_home.html')
    books=book_rows()[:4]; u=current_user(); prog=[]; stats=dict(started=0,annotations=0,completed=0,flashcards=0)
    if u:
        c=db(); prog=c.execute("SELECT p.*,b.title FROM progress p JOIN books b ON b.id=p.book_id WHERE p.user_id=? ORDER BY p.updated DESC LIMIT 3",(u['id'],)).fetchall(); stats=dict(started=c.execute('SELECT COUNT(*) FROM progress WHERE user_id=?',(u['id'],)).fetchone()[0],completed=c.execute('SELECT COUNT(*) FROM progress WHERE user_id=? AND percent>=100',(u['id'],)).fetchone()[0],annotations=c.execute('SELECT COUNT(*) FROM annotations WHERE user_id=?',(u['id'],)).fetchone()[0],flashcards=c.execute('SELECT COUNT(*) FROM flashcards WHERE user_id=?',(u['id'],)).fetchone()[0]); c.close()
    return page('Dashboard','''<section class="hero"><span class="pill">AI-powered reading ecosystem</span><h1>Your library, bookstore & knowledge space</h1><p class="muted">Discover, read, annotate, learn, borrow, buy and collaborate — in one responsive workspace.</p><div class="row"><a class="btn" href="/discover">Explore books</a><a class="btn ghost" href="/ai">Ask LibraAI</a></div></section><h2>Today at a glance</h2><div class="grid"><div class="card"><div class="muted">Books started</div><div class="kpi">{{stats.started}}</div></div><div class="card"><div class="muted">Saved annotations</div><div class="kpi">{{stats.annotations}}</div></div><div class="card"><div class="muted">Books completed</div><div class="kpi">{{stats.completed}}</div></div><div class="card"><div class="muted">Flashcards created</div><div class="kpi">{{stats.flashcards}}</div></div></div>{% if prog %}<h2>Continue reading</h2><div class="grid">{% for p in prog %}<div class="card"><b>{{p['title']}}</b><p class="muted">Page {{p['page']}} · {{p['percent']|round|int}}%</p><div class="bar"><i style="width:{{p['percent']}}%"></i></div><br><a class="btn ghost" href="/reader/{{p['book_id']}}">Resume</a></div>{% endfor %}</div>{% endif %}<h2>Trending now</h2><div class="grid">{% for b in books %}<div class="card book"><div class="cover">📘</div><span class="pill">{{b.genre}}</span><h3>{{b.title}}</h3><div class="muted">{{b.author}} · ★ {{b.rating}}</div><p><a class="btn ghost" href="/book/{{b.id}}">View book</a></p></div>{% endfor %}</div>''',books=books,prog=prog,stats=stats)

@app.route('/discover')
def discover():
    order=request.args.get('sort','trending'); genre=request.args.get('genre','All'); q=request.args.get('q',''); books=book_rows(order,genre,q); genres=['All']+sorted(set(b['genre'] for b in book_rows()))
    return page('Discover','''<h1>Discover & rank books</h1><p class="muted">Transparent demo ranking combines reading activity, sales, ratings and recency. Production should add qualified-session and fraud/bot filtering.</p><form class="card row"><input class="input" style="flex:2" name="q" value="{{q}}" placeholder="Search title, author, ISBN, topic"><select name="genre" style="flex:1">{% for g in genres %}<option {% if g==genre %}selected{% endif %}>{{g}}</option>{% endfor %}</select><select name="sort" style="flex:1"><option value="trending">Fast rising / Trending</option><option value="rated" {% if order=='rated' %}selected{% endif %}>Highest rated</option><option value="bestseller" {% if order=='bestseller' %}selected{% endif %}>Bestsellers</option><option value="new" {% if order=='new' %}selected{% endif %}>New arrivals</option></select><button class="btn">Apply</button></form><div class="tabs"><span class="pill">Most Read</span><span class="pill">Highest Rated</span><span class="pill">Bestsellers</span><span class="pill">New Releases</span><span class="pill">Book of the Day</span><span class="pill">For You</span></div><h2>{{books|length}} results</h2><div class="grid">{% for b in books %}<div class="card book"><div class="cover">📚</div><span class="pill">#{{loop.index}} {{b.genre}}</span><h3>{{b.title}}</h3><div class="muted">{{b.author}}</div><p>★ {{b.rating}} · {{'{:,}'.format(b.reads)}} reads</p><a class="btn ghost" href="/book/{{b.id}}">Details</a></div>{% endfor %}</div>''',books=books,genres=genres,genre=genre,order=order,q=q)

@app.route('/book/<int:bid>')
def book(bid):
    c=db(); b=c.execute("SELECT * FROM books WHERE id=?",(bid,)).fetchone(); reviews=c.execute("SELECT r.*,u.name FROM reviews r JOIN users u ON u.id=r.user_id WHERE book_id=? ORDER BY created DESC",(bid,)).fetchall(); c.close()
    if not b:return ('Not found',404)
    return page(b['title'],'''<div class="hero"><div class="row"><div class="cover" style="width:160px;height:210px">📖</div><div style="flex:1"><span class="pill">{{b['genre']}}</span><h1>{{b['title']}}</h1><h3 class="muted">{{b['author']}}</h3><p>★ {{b['rating']}} · {{'{:,}'.format(b['reads'])}} qualified demo reads · ISBN {{b['isbn']}}</p><p>{{b['description']}}</p><div class="row"><a class="btn" href="/reader/{{b['id']}}">Read sample</a><form method="post" action="/action/wishlist/{{b['id']}}"><button class="btn ghost">♡ Wishlist</button></form><form method="post" action="/action/cart/{{b['id']}}" data-cart-auth-guard><select name="format" aria-label="Choose book format"><option value="eBook">eBook</option><option value="Print">Print</option></select><label>Quantity <input name="qty" type="number" min="1" max="99" value="1"></label><button class="btn green" type="submit">Add to cart · ৳{{b['price']}}</button><button class="btn" type="submit" name="buy_now" value="1">Buy now</button></form><form method="post" action="/action/borrow/{{b['id']}}"><button class="btn ghost">Borrow / Reserve</button></form></div></div></div></div><h2>Formats & access</h2><div class="card"><span class="pill">{{b['format']}}</span><span class="pill">Pay-per-read</span><span class="pill">Subscription eligible</span><span class="pill">Gift</span><span class="pill">Library lending</span><p class="muted">Shelf locator: {{b['branch']}} · {{b['shelf']}} · Stock {{b['stock']}}</p></div><h2>Spoiler-aware reader reviews</h2><form class="card" method="post" action="/review/{{b['id']}}"><div class="row"><select name="rating" style="max-width:140px"><option>5</option><option>4</option><option>3</option><option>2</option><option>1</option></select><label><input type="checkbox" name="spoiler"> Contains spoiler</label></div><textarea name="text" placeholder="Write a review"></textarea><button class="btn">Post review</button></form>{% for r in reviews %}<div class="card"><b>{{r['name']}}</b> · ★{{r['rating']}} {% if r['verified'] %}<span class="pill">Verified reader</span>{% endif %}{% if r['spoiler'] %}<details><summary>Show spoiler review</summary><p>{{r['text']}}</p></details>{% else %}<p>{{r['text']}}</p>{% endif %}</div>{% endfor %}<div id="detail-signup-notice" role="status" style="display:none;position:fixed;z-index:9999;right:22px;bottom:22px;max-width:340px;padding:18px;border:1px solid #e6e0f8;border-radius:16px;background:#fff;box-shadow:0 18px 50px #24204a25"><b>Please sign up before you want a book.</b><p>Create an account to add books to your cart or buy now.</p><a href="/register">Sign up ↗</a></div><script>fetch('/api/auth-status').then(r=>r.json()).then(s=>{document.querySelectorAll('[data-cart-auth-guard]').forEach(f=>f.addEventListener('submit',e=>{if(!s.authenticated){e.preventDefault();document.getElementById('detail-signup-notice').style.display='block'}}))}).catch(()=>{});</script>''',b=b,reviews=reviews)

# --------------------------- Reader ---------------------------
@app.route('/reader/<int:bid>',methods=['GET','POST'])
def reader(bid):
    c=db(); b=c.execute("SELECT * FROM books WHERE id=?",(bid,)).fetchone(); anns=[]
    if not b:
        c.close()
        abort(404)
    saved_progress = {'page': 1, 'percent': 0}
    if current_user():
        anns=c.execute("SELECT * FROM annotations WHERE user_id=? AND book_id=? ORDER BY created DESC",(current_user()['id'],bid)).fetchall()
        row=c.execute("SELECT page,percent FROM progress WHERE user_id=? AND book_id=?",(current_user()['id'],bid)).fetchone()
        if row: saved_progress=dict(row)
    c.close()
    sample=(f"{b['title']} — licensed sample reader\n\nThis prototype demonstrates the reading interface rather than distributing copyrighted book text. "
            "A production deployment would load licensed pages or publisher-provided samples. Use the toolbar to switch two-page/scroll presentation, adjust font and theme, save highlights, notes, bookmarks and quotes, and synchronize reading progress.\n\n"
            "Dictionary, translation, audio reading, auto-scroll, accessibility controls, manga/comics mode and offline entitlement are represented as reader controls and integration points. "
            "The application stores reading position and annotations locally in SQLite for the signed-in demo user.")
    return page('Reader','''<div class="row between"><div><h1>{{b['title']}}</h1><div class="muted">{{b['author']}}</div></div><div class="row"><button type="button" class="btn ghost" onclick="togglePages()" aria-pressed="true" id="layoutToggle">Two-page / Scroll</button><button type="button" class="btn ghost" onclick="toggleTheme()" aria-pressed="false" id="readerThemeToggle">Reader theme</button><button type="button" class="btn ghost" onclick="speakReader()">🔊 Read aloud</button><button type="button" class="btn ghost" onclick="stopReaderAudio()">■ Stop audio</button></div></div><section class="card" aria-label="Reading accessibility controls"><div class="row"><button type="button" class="btn ghost" onclick="changeReaderFont(-1)" aria-label="Decrease text size">A−</button><button type="button" class="btn ghost" onclick="changeReaderFont(1)" aria-label="Increase text size">A+</button><button type="button" class="btn ghost" onclick="toggleReaderSpacing()" id="spacingToggle" aria-pressed="false">Comfortable spacing</button><button type="button" class="btn ghost" onclick="toggleReaderContrast()" id="contrastToggle" aria-pressed="false">High contrast</button><button type="button" class="btn ghost" onclick="toggleAutoScroll()" id="autoScrollToggle" aria-pressed="false">▶ Auto-scroll</button><label for="scrollSpeed">Scroll speed</label><input id="scrollSpeed" type="range" min="1" max="8" value="2" aria-label="Auto-scroll speed"></div><p class="muted" id="readerStatus" role="status" aria-live="polite">Reading controls ready. Audio uses voices available in this browser.</p></section><article id="text" class="reader two" tabindex="0" aria-label="Book text" data-book-id="{{b['id']}}" data-saved-page="{{saved_progress.page}}" data-saved-percent="{{saved_progress.percent}}">{{sample}}</article><br><div class="grid"><form class="card" method="post" action="/annotation/{{b['id']}}"><h3>Annotate</h3><select name="kind"><option>Highlight</option><option>Private note</option><option>Quote</option><option>Bookmark</option></select><input class="input" name="page" type="number" value="1"><select name="color"><option>Yellow</option><option>Green</option><option>Blue</option><option>Pink</option></select><textarea name="content" placeholder="Selected text or private note"></textarea><button class="btn">Save annotation</button></form><form class="card" method="post" action="/progress/{{b['id']}}"><h3>Reading position sync</h3><label>Page</label><input class="input" name="page" type="number" value="12"><label>Progress %</label><input class="input" name="percent" type="number" min="0" max="100" value="25"><button class="btn">Sync progress</button></form></div><h2>Your annotations</h2>{% for a in anns %}<div class="card"><span class="pill">{{a['kind']}}</span> page {{a['page']}} · {{a['color']}}<p>{{a['content']}}</p></div>{% else %}<p class="muted">No saved annotations yet.</p>{% endfor %}<style>.reader{font-size:18px;line-height:1.8;max-width:860px;margin:24px auto;padding:clamp(20px,5vw,56px);background:#fff;color:#20263a;border-radius:18px;white-space:pre-wrap;overflow-wrap:anywhere}.reader.two{column-count:2;column-gap:48px}.reader.comfortable{line-height:2.15;letter-spacing:.025em}.reader.high-contrast{background:#000!important;color:#fff!important;outline:2px solid currentColor}.reader:focus-visible{outline:3px solid #6953d9;outline-offset:3px}@media(max-width:700px){.reader.two{column-count:1}.reader{padding:20px}}</style><script>
let readerFontSize=18, autoScrollTimer=null, readerThemeDark=false;
const READER_PREFS_KEY='libraai-reader-preferences-v1';
function readerStatus(message){const el=document.getElementById('readerStatus');if(el)el.textContent=message;}
function saveReaderPreferences(){try{const article=document.getElementById('text');localStorage.setItem(READER_PREFS_KEY,JSON.stringify({fontSize:readerFontSize,twoColumn:article.classList.contains('two'),dark:readerThemeDark,comfortable:article.classList.contains('comfortable'),highContrast:article.classList.contains('high-contrast'),scrollSpeed:Number(document.getElementById('scrollSpeed').value)||2}));}catch(_error){/* Private browsing or blocked storage must not break reading. */}}
function applyReaderPreferences(){let prefs={};try{prefs=JSON.parse(localStorage.getItem(READER_PREFS_KEY)||'{}');}catch(_error){prefs={};}const article=document.getElementById('text');
 if(Number.isFinite(prefs.fontSize))readerFontSize=Math.max(14,Math.min(32,prefs.fontSize));article.style.fontSize=readerFontSize+'px';
 if(prefs.twoColumn===false)article.classList.remove('two');else if(prefs.twoColumn===true)article.classList.add('two');document.getElementById('layoutToggle').setAttribute('aria-pressed',String(article.classList.contains('two')));
 if(prefs.dark===true){readerThemeDark=true;article.style.background='#171923';article.style.color='#f7f7fb';document.getElementById('readerThemeToggle').setAttribute('aria-pressed','true');}
 if(prefs.comfortable===true){article.classList.add('comfortable');document.getElementById('spacingToggle').setAttribute('aria-pressed','true');}
 if(prefs.highContrast===true){article.classList.add('high-contrast');document.getElementById('contrastToggle').setAttribute('aria-pressed','true');}
 if(Number.isFinite(prefs.scrollSpeed))document.getElementById('scrollSpeed').value=Math.max(1,Math.min(8,prefs.scrollSpeed));}
function togglePages(){const article=document.getElementById('text');const enabled=article.classList.toggle('two');document.getElementById('layoutToggle').setAttribute('aria-pressed',String(enabled));saveReaderPreferences();readerStatus(enabled?'Two-column reading layout enabled.':'Continuous single-column reading enabled.');}
function toggleTheme(){readerThemeDark=!readerThemeDark;const article=document.getElementById('text');article.style.background=readerThemeDark?'#171923':'#fff';article.style.color=readerThemeDark?'#f7f7fb':'#20263a';document.getElementById('readerThemeToggle').setAttribute('aria-pressed',String(readerThemeDark));saveReaderPreferences();readerStatus(readerThemeDark?'Dark reading theme enabled.':'Light reading theme enabled.');}
function changeReaderFont(delta){readerFontSize=Math.max(14,Math.min(32,readerFontSize+delta*2));document.getElementById('text').style.fontSize=readerFontSize+'px';saveReaderPreferences();readerStatus('Text size: '+readerFontSize+' pixels.');}
function toggleReaderSpacing(){const article=document.getElementById('text');const enabled=article.classList.toggle('comfortable');document.getElementById('spacingToggle').setAttribute('aria-pressed',String(enabled));saveReaderPreferences();readerStatus(enabled?'Comfortable line spacing enabled.':'Standard line spacing enabled.');}
function toggleReaderContrast(){const article=document.getElementById('text');const enabled=article.classList.toggle('high-contrast');document.getElementById('contrastToggle').setAttribute('aria-pressed',String(enabled));saveReaderPreferences();readerStatus(enabled?'High contrast enabled.':'High contrast disabled.');}
function stopAutoScroll(message='Auto-scroll stopped.'){if(autoScrollTimer){clearInterval(autoScrollTimer);autoScrollTimer=null;}const button=document.getElementById('autoScrollToggle');if(button){button.textContent='▶ Auto-scroll';button.setAttribute('aria-pressed','false');}if(message)readerStatus(message);}
function toggleAutoScroll(){if(autoScrollTimer){stopAutoScroll();return;}const button=document.getElementById('autoScrollToggle');autoScrollTimer=setInterval(()=>{const speed=Number(document.getElementById('scrollSpeed').value)||2;window.scrollBy({top:speed,behavior:'auto'});if(window.innerHeight+window.scrollY>=document.documentElement.scrollHeight-2)stopAutoScroll('End of page reached.');},80);button.textContent='Ⅱ Stop scroll';button.setAttribute('aria-pressed','true');readerStatus('Auto-scroll started. Adjust speed with the slider.');}
function speakReader(){if(!('speechSynthesis' in window)){readerStatus('Text-to-speech is not supported by this browser.');return;}window.speechSynthesis.cancel();const utterance=new SpeechSynthesisUtterance(document.getElementById('text').innerText);utterance.onstart=()=>readerStatus('Read-aloud started.');utterance.onend=()=>readerStatus('Read-aloud finished.');utterance.onerror=()=>readerStatus('Read-aloud could not start in this browser.');window.speechSynthesis.speak(utterance);}
function stopReaderAudio(){if('speechSynthesis' in window)window.speechSynthesis.cancel();readerStatus('Read-aloud stopped.');}
document.getElementById('scrollSpeed').addEventListener('change',saveReaderPreferences);
// Restore and automatically sync reading position. Server sync is account-scoped;
// local storage is a best-effort fallback for guests/offline sessions.
const progressArticle=document.getElementById('text');
const progressBookId=progressArticle.dataset.bookId;
const progressLocalKey='libraai-reading-progress-v1:'+progressBookId;
let progressSyncTimer=null, progressCsrfToken=null, lastProgressSignature='';
function currentReadingProgress(){const max=Math.max(1,document.documentElement.scrollHeight-window.innerHeight);const percent=Math.max(0,Math.min(100,Math.round(window.scrollY/max*100)));return {page:Math.max(1,Math.min(1000000,Math.round(percent/100*100)||1)),percent};}
async function syncReadingProgress(){const progress=currentReadingProgress();const signature=progress.page+':'+progress.percent;if(signature===lastProgressSignature)return;lastProgressSignature=signature;try{localStorage.setItem(progressLocalKey,JSON.stringify({...progress,savedAt:Date.now()}));}catch(_error){}
 try{if(!progressCsrfToken){const tokenResponse=await fetch('/api/csrf',{credentials:'same-origin',cache:'no-store'});if(!tokenResponse.ok)return;progressCsrfToken=(await tokenResponse.json()).csrfToken;}const response=await fetch('/api/reader/'+encodeURIComponent(progressBookId)+'/progress',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':progressCsrfToken},body:JSON.stringify(progress)});if(response.status===401){readerStatus('Progress saved on this device. Sign in to sync across devices.');return;}if(response.ok)readerStatus('Reading progress synced · '+progress.percent+'%.');}catch(_error){readerStatus('Progress saved locally. Server sync will retry when connected.');}}
function scheduleProgressSync(){if(progressSyncTimer)clearTimeout(progressSyncTimer);progressSyncTimer=setTimeout(syncReadingProgress,700);}
async function restoreReadingProgress(){let local=null;try{local=JSON.parse(localStorage.getItem(progressLocalKey)||'null');}catch(_error){}let server=null;try{const response=await fetch('/api/reader/'+encodeURIComponent(progressBookId)+'/progress',{credentials:'same-origin',cache:'no-store'});if(response.ok){const data=await response.json();server=data.progress;}}catch(_error){}
 const saved=server&&server.updated?server:local;if(saved&&Number.isFinite(Number(saved.percent))&&Number(saved.percent)>0){const max=Math.max(1,document.documentElement.scrollHeight-window.innerHeight);window.scrollTo(0,max*Math.min(100,Math.max(0,Number(saved.percent)))/100);readerStatus('Reading position restored · '+Math.round(Number(saved.percent))+'%.');}}
window.addEventListener('scroll',scheduleProgressSync,{passive:true});window.addEventListener('pagehide',()=>{if(progressSyncTimer){clearTimeout(progressSyncTimer);progressSyncTimer=null;}syncReadingProgress();});document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')syncReadingProgress();});
document.addEventListener('keydown',(event)=>{if(event.altKey&&['+','='].includes(event.key)){event.preventDefault();changeReaderFont(1);}else if(event.altKey&&event.key==='-'){event.preventDefault();changeReaderFont(-1);}else if(event.altKey&&event.key.toLowerCase()==='t'){event.preventDefault();toggleTheme();}else if(event.key==='Escape'){stopAutoScroll(null);stopReaderAudio();}});
applyReaderPreferences();
restoreReadingProgress();
window.addEventListener('pagehide',()=>{if(autoScrollTimer)clearInterval(autoScrollTimer);if('speechSynthesis' in window)window.speechSynthesis.cancel();});
</script>''',b=b,sample=sample,anns=anns,saved_progress=saved_progress)

@app.post('/annotation/<int:bid>')
@login_required
def annotation(bid):
    # Validate enumerated fields and bounds before persistence; never trust form values.
    kind = request.form.get('kind', '').strip()
    color = request.form.get('color', '').strip()
    content = request.form.get('content', '').strip()
    try:
        page_number = int(request.form.get('page', '1'))
    except (TypeError, ValueError):
        abort(400, 'Page must be a positive integer.')
    if kind not in {'Highlight', 'Private note', 'Quote', 'Bookmark'}:
        abort(400, 'Unsupported annotation type.')
    if color not in {'Yellow', 'Green', 'Blue', 'Pink'}:
        abort(400, 'Unsupported annotation color.')
    if not content or len(content) > 4000:
        abort(400, 'Annotation content must be between 1 and 4000 characters.')
    if not 1 <= page_number <= 1000000:
        abort(400, 'Page must be between 1 and 1000000.')
    c = db()
    try:
        if not c.execute('SELECT 1 FROM books WHERE id=?', (bid,)).fetchone():
            abort(404)
        c.execute("INSERT INTO annotations(user_id,book_id,kind,content,color,page,created) VALUES(?,?,?,?,?,?,?)", (current_user()['id'], bid, kind, content, color, page_number, datetime.now().isoformat(timespec='seconds')))
        c.commit()
    finally:
        c.close()
    audit('Created annotation')
    return redirect(url_for('reader', bid=bid))
@app.route('/api/reader/<int:bid>/progress', methods=['GET', 'POST'])
def api_reader_progress(bid):
    """Account-scoped reader progress API for automatic same-account sync."""
    user = current_user()
    if not user:
        return jsonify({'error': 'Sign in required', 'code': 'authentication_required'}), 401
    with db() as conn:
        if not conn.execute('SELECT 1 FROM books WHERE id=?', (bid,)).fetchone():
            return jsonify({'error': 'Book not found'}), 404
        if request.method == 'GET':
            row = conn.execute(
                'SELECT page, percent, updated FROM progress WHERE user_id=? AND book_id=?',
                (int(user['id']), bid),
            ).fetchone()
            return jsonify({'progress': dict(row) if row else {'page': 1, 'percent': 0, 'updated': None}})
        data = request.get_json(silent=True) or {}
        try:
            page_number, percent = validate_progress(data.get('page'), data.get('percent'))
        except InputValidationError as exc:
            return jsonify({'error': str(exc)}), 400
        updated = datetime.now().isoformat(timespec='seconds')
        conn.execute(
            'INSERT INTO progress(user_id,book_id,page,percent,updated) VALUES(?,?,?,?,?) '
            'ON CONFLICT(user_id,book_id) DO UPDATE SET page=excluded.page, '
            'percent=excluded.percent, updated=excluded.updated',
            (int(user['id']), bid, page_number, percent, updated),
        )
    return jsonify({'ok': True, 'progress': {'page': page_number, 'percent': percent, 'updated': updated}})


@app.post('/progress/<int:bid>')
@login_required
def progress(bid):
    try:
        page_number, percent = validate_progress(request.form.get('page'), request.form.get('percent'))
    except InputValidationError as exc:
        abort(400, str(exc))
    with db() as c:
        if not c.execute('SELECT 1 FROM books WHERE id=?', (bid,)).fetchone():
            abort(404)
        c.execute("INSERT INTO progress(user_id,book_id,page,percent,updated) VALUES(?,?,?,?,?) ON CONFLICT(user_id,book_id) DO UPDATE SET page=excluded.page,percent=excluded.percent,updated=excluded.updated", (current_user()['id'],bid,page_number,percent,datetime.now().isoformat(timespec='seconds')))
    return redirect(url_for('reader',bid=bid))

# --------------------------- Library / commerce ---------------------------
@app.route('/action/<kind>/<int:bid>',methods=['POST'])
@login_required
def action(kind,bid):
    c=db(); uid=current_user()['id']
    if not c.execute('SELECT 1 FROM books WHERE id=?',(bid,)).fetchone(): c.close(); abort(404)
    if kind=='wishlist': c.execute("INSERT OR IGNORE INTO wishlist(user_id,book_id) VALUES(?,?)",(uid,bid)); flash('Added to wishlist.')
    elif kind=='cart':
        from mixed_format_catalog import select_format, FormatUnavailable
        catalog_format = c.execute('SELECT format FROM books WHERE id=?',(bid,)).fetchone()['format']
        try:
            selected_format = select_format(catalog_format, request.form.get('format', 'eBook'))
        except FormatUnavailable as exc:
            c.close()
            abort(400, str(exc))
        inventory = c.execute('SELECT COALESCE(cp.sale_enabled,1) sale_enabled, COALESCE(cp.digital_available,0) digital_available, COALESCE(cp.inventory_quantity,b.stock,0) inventory_quantity FROM books b LEFT JOIN catalog_products cp ON cp.book_id=b.id WHERE b.id=?',(bid,)).fetchone()
        if not inventory['sale_enabled']:
            c.close(); abort(409, 'This item is currently unavailable for sale.')
        digital_format = selected_format.lower() in ('ebook','audio','audiobook','digital')
        if digital_format and not inventory['digital_available']:
            c.close(); abort(409, 'This digital format is not enabled for this listing.')
        if not digital_format and inventory['inventory_quantity'] <= 0:
            c.close(); abort(409, 'Out of stock. Please join the waitlist or choose an available digital format.')
        try:
            quantity=int(request.form.get('qty','1'))
        except (TypeError,ValueError):
            c.close(); abort(400,'Quantity must be a whole number')
        if quantity < 1 or quantity > 99:
            c.close(); abort(400,'Quantity must be between 1 and 99')
        c.execute('INSERT INTO cart(user_id,book_id,qty,format) VALUES(?,?,?,?) ON CONFLICT(user_id,book_id,format) DO UPDATE SET qty=MIN(99,cart.qty+excluded.qty)',(uid,bid,quantity,selected_format))
        flash('Added '+str(quantity)+' × '+selected_format+' to cart.')
    elif kind=='borrow' and os.environ.get('LIBRAAI_ENV') == 'production': c.close(); abort(503, 'Borrowing requires a verified inventory and lending integration')
    elif kind=='borrow': c.execute("INSERT INTO loans(user_id,book_id,status,due,branch,created) VALUES(?,?, 'Borrowed',?,?,?)",(uid,bid,(datetime.now()+timedelta(days=14)).date().isoformat(),'Central',datetime.now().isoformat(timespec='seconds'))); flash('Demo loan created. If unavailable, production logic would create reservation/waitlist/inter-library request.')
    else: c.close(); abort(400, 'Unknown action')
    c.commit(); c.close(); audit(kind+' book'); return redirect('/checkout' if kind=='cart' and request.form.get('buy_now')=='1' else safe_local_return_url(request.referrer, request.host, request.scheme))

@app.post('/action/wishlist/<int:bid>/remove')
@login_required
def remove_wishlist_item(bid):
    conn = db()
    try:
        if not conn.execute('SELECT 1 FROM books WHERE id=?', (bid,)).fetchone():
            abort(404)
        conn.execute('DELETE FROM wishlist WHERE user_id=? AND book_id=?', (current_user()['id'], bid))
        conn.commit()
    finally:
        conn.close()
    audit('Removed book from wishlist')
    return redirect(safe_local_return_url(request.referrer, request.host, request.scheme))

@app.route('/library')
@login_required
def library():
    c=db(); uid=current_user()['id']; wish=c.execute("SELECT b.* FROM wishlist w JOIN books b ON b.id=w.book_id WHERE w.user_id=?",(uid,)).fetchall(); loans=c.execute("SELECT l.*,b.title FROM loans l JOIN books b ON b.id=l.book_id WHERE l.user_id=? ORDER BY l.created DESC",(uid,)).fetchall(); prog=c.execute("SELECT p.*,b.title FROM progress p JOIN books b ON b.id=p.book_id WHERE p.user_id=?",(uid,)).fetchall(); c.close()
    return page('My Library','''<h1>My Library</h1><div class="tabs"><span class="pill">Owned</span><span class="pill">Borrowed</span><span class="pill">Wishlist</span><span class="pill">Downloads</span><span class="pill">History</span></div><h2>Borrowing, renewals & reservations</h2><table class="table"><tr><th>Book</th><th>Status</th><th>Due</th><th>Action</th></tr>{% for x in loans %}<tr><td>{{x['title']}}</td><td>{{x['status']}}</td><td>{{x['due']}}</td><td>{% if x['status'] != 'Returned' %}<form method="post" action="/loan/{{x['id']}}/renew" style="display:inline"><button class="btn ghost">Renew</button></form> <form method="post" action="/loan/{{x['id']}}/return" style="display:inline" onsubmit="return confirm('Confirm return?')"><button class="btn ghost">Return</button></form>{% else %}<span class="muted">Completed</span>{% endif %}</td></tr>{% endfor %}</table><h2>Reading progress</h2><div class="grid">{% for p in prog %}<div class="card"><b>{{p['title']}}</b><p>{{p['percent']}}%</p><div class="bar"><i style="width:{{p['percent']}}%"></i></div></div>{% endfor %}</div><h2>Wishlist</h2><div class="grid">{% for b in wish %}<div class="card"><b>{{b['title']}}</b><p class="muted">{{b['author']}}</p><a href="/book/{{b['id']}}">Open</a></div>{% endfor %}</div>''',wish=wish,loans=loans,prog=prog)

@app.route('/loan/<int:lid>/<op>',methods=['POST'])
@login_required
def loanop(lid,op):
    if op not in ('renew','return'): abort(400)
    c=db()
    try:
        loan=c.execute("SELECT status FROM loans WHERE id=? AND user_id=?",(lid,current_user()['id'])).fetchone()
        if loan is None: abort(404)
        if loan['status']=='Returned': abort(409,'Loan already returned')
        if op=='renew':
            c.execute("UPDATE loans SET due=date(COALESCE(due,date('now')),'+14 day'),status='Renewed' WHERE id=? AND user_id=? AND status!='Returned'",(lid,current_user()['id']))
        else:
            c.execute("UPDATE loans SET status='Returned' WHERE id=? AND user_id=? AND status!='Returned'",(lid,current_user()['id']))
        c.commit()
    finally:
        c.close()
    audit('Customer '+op+' loan #'+str(lid))
    return redirect('/library')


@app.get('/librarian')
@login_required
def librarian_desk():
    user = current_user()
    if user['role'] not in ('librarian', 'admin'):
        abort(403)
    conn = db()
    try:
        if user['role'] == 'admin':
            branch = (request.args.get('branch') or 'Central').strip()[:80]
        else:
            row = conn.execute('SELECT branch FROM librarian_branches WHERE user_id=?',(user['id'],)).fetchone()
            if row is None: abort(403, 'Librarian branch assignment required')
            branch = row['branch']
        loans = conn.execute("SELECT l.id,l.status,l.due,l.branch,b.title,u.name FROM loans l JOIN books b ON b.id=l.book_id JOIN users u ON u.id=l.user_id WHERE l.branch=? ORDER BY l.created DESC LIMIT 100",(branch,)).fetchall()
    finally:
        conn.close()
    return page('Circulation Desk', '''<h1>Circulation Desk</h1><p class="muted">Branch: {{branch}} · Loan renewals and returns</p><p class="muted" role="status">Showing up to 100 most recent loans for this branch. Changes are recorded in the audit log.</p><div style="max-width:100%;overflow-x:auto" role="region" aria-label="Branch loans" tabindex="0"><table class="table"><thead><tr><th>Book</th><th>Borrower</th><th>Status</th><th>Due</th><th>Action</th></tr></thead><tbody>{% for loan in loans %}<tr><td>{{loan['title']}}</td><td>{{loan['name']}}</td><td>{{loan['status']}}</td><td>{{loan['due']}}</td><td>{% if loan['status'] != 'Returned' %}<form method="post" action="/librarian/loans/{{loan['id']}}/renew"><button class="btn ghost">Renew</button></form><form method="post" action="/librarian/loans/{{loan['id']}}/return" onsubmit="return confirm('Confirm check-in of this loan?')"><button class="btn ghost">Check in</button></form>{% endif %}</td></tr>{% else %}<tr><td colspan="5">No loans at this branch.</td></tr>{% endfor %}</tbody></table></div>''',branch=branch,loans=loans)

@app.post('/librarian/loans/<int:loan_id>/<action>')
@login_required
def librarian_loan_action(loan_id,action):
    user=current_user()
    if user['role'] not in ('librarian','admin'): abort(403)
    if action not in ('renew','return'): abort(404)
    conn=db()
    try:
        loan=conn.execute('SELECT branch,status FROM loans WHERE id=?',(loan_id,)).fetchone()
        if loan is None: abort(404)
        if user['role']=='librarian':
            assignment=conn.execute('SELECT branch FROM librarian_branches WHERE user_id=?',(user['id'],)).fetchone()
            if assignment is None or assignment['branch'] != loan['branch']: abort(403)
        if loan['status']=='Returned': abort(409,'Loan already returned')
        if action=='renew':
            conn.execute("UPDATE loans SET due=date(COALESCE(due,date('now')),'+14 day'),status='Renewed' WHERE id=? AND status!='Returned'",(loan_id,))
        else:
            conn.execute("UPDATE loans SET status='Returned' WHERE id=? AND status!='Returned'",(loan_id,))
        conn.commit()
    finally:
        conn.close()
    audit('Librarian '+action+' loan #'+str(loan_id))
    return redirect(url_for('librarian_desk', branch=loan['branch']))

@app.get('/marketplace')
def marketplace():
    books=book_rows();
    from mixed_format_catalog import available_formats
    c=db(); cart=[]; resale=c.execute("SELECT r.*,b.title,u.name FROM resale r JOIN books b ON b.id=r.book_id JOIN users u ON u.id=r.user_id WHERE r.status='Listed'").fetchall()
    if current_user(): cart=c.execute("SELECT c.*,b.title,b.price FROM cart c JOIN books b ON b.id=c.book_id WHERE c.user_id=?",(current_user()['id'],)).fetchall()
    c.close(); total=sum(x['price']*x['qty'] for x in cart)
    return page('Marketplace', render_template('marketplace.html', books=books, cart=cart, total=total, resale=resale, checkout_key=secrets.token_urlsafe(24), available_formats=available_formats))

@app.get('/api/auth-status')
def auth_status():
    u=current_user()
    return jsonify({'authenticated':bool(u),'user':({'name':u['name']} if u else None)})

@app.get('/audio-library')
def audio_library():
    with db() as conn:
        rows=[dict(r) for r in conn.execute("SELECT * FROM audio_catalog ORDER BY CASE kind WHEN 'Audiobook' THEN 0 ELSE 1 END, rating DESC, id")]
        saved=set()
        if current_user():
            saved={r['audio_id'] for r in conn.execute('SELECT audio_id FROM audio_bookmarks WHERE user_id=?',(current_user()['id'],))}
    return render_template('audio_library.html', items=rows, saved=saved, user=current_user())

@app.post('/audio-library/bookmark/<int:audio_id>')
@login_required
def audio_bookmark(audio_id):
    with db() as conn:
        if not conn.execute('SELECT 1 FROM audio_catalog WHERE id=?',(audio_id,)).fetchone(): abort(404)
        exists=conn.execute('SELECT 1 FROM audio_bookmarks WHERE user_id=? AND audio_id=?',(current_user()['id'],audio_id)).fetchone()
        if exists:
            conn.execute('DELETE FROM audio_bookmarks WHERE user_id=? AND audio_id=?',(current_user()['id'],audio_id)); saved=False
        else:
            conn.execute('INSERT INTO audio_bookmarks(user_id,audio_id) VALUES(?,?)',(current_user()['id'],audio_id)); saved=True
    return jsonify({'ok':True,'saved':saved})

@app.get('/shop')
def shop_alias():
    return redirect('/marketplace')

@app.post('/cart/<int:cart_id>/update')
@login_required
def update_cart_item(cart_id):
    raw_qty = request.form.get('qty', '1')
    try:
        qty = int(raw_qty)
    except (TypeError, ValueError):
        abort(400, 'Quantity must be a whole number')
    if qty < 1 or qty > 99:
        abort(400, 'Quantity must be between 1 and 99')
    conn = db()
    try:
        result = conn.execute('UPDATE cart SET qty=? WHERE id=? AND user_id=?',
                              (qty, cart_id, current_user()['id']))
        if result.rowcount == 0:
            abort(404)
        conn.commit()
    finally:
        conn.close()
    flash('Cart quantity updated.')
    return redirect('/marketplace')

@app.post('/cart/<int:cart_id>/remove')
@login_required
def remove_cart_item(cart_id):
    conn = db()
    try:
        result = conn.execute('DELETE FROM cart WHERE id=? AND user_id=?',
                              (cart_id, current_user()['id']))
        if result.rowcount == 0:
            abort(404)
        conn.commit()
    finally:
        conn.close()
    flash('Item removed from your cart.')
    return redirect('/marketplace')

@app.get('/checkout')
@login_required
def checkout_page():
    # Render a review step before creating an order; no payment is initiated here.
    if os.environ.get('LIBRAAI_ENV') == 'production':
        from commercial_readiness import inspect
        if not inspect()['ready']:
            abort(503, 'Checkout disabled until commercial launch checks pass')
    uid = current_user()['id']
    conn = db()
    try:
        items = [dict(row) for row in conn.execute(
            'SELECT c.id cart_id,c.qty,c.format,b.id book_id,b.title,b.author,b.price '
            'FROM cart c JOIN books b ON b.id=c.book_id WHERE c.user_id=? ORDER BY c.id',
            (uid,))]
    finally:
        conn.close()
    if not items:
        flash('Your cart is empty. Add a book before checking out.')
        return redirect('/marketplace')
    total = sum(float(item['price']) * int(item['qty']) for item in items)
    request_key = request.args.get('request_key', '')
    if not request_key or len(request_key) > 200:
        request_key = secrets.token_urlsafe(24)
    return page('Checkout', render_template('checkout.html', items=items, total=total,
                request_key=request_key, coupon='', address=''))

@app.post('/checkout')
@login_required
def checkout():
    if os.environ.get('LIBRAAI_ENV') == 'production':
        from commercial_readiness import inspect
        if not inspect()['ready']:
            abort(503, 'Checkout disabled until commercial launch checks pass')
    c=db()
    try:
        cart_rows=c.execute('SELECT c.format,c.qty,b.title,COALESCE(cp.sale_enabled,1) sale_enabled,COALESCE(cp.digital_available,0) digital_available,COALESCE(cp.inventory_quantity,b.stock,0) inventory_quantity FROM cart c JOIN books b ON b.id=c.book_id LEFT JOIN catalog_products cp ON cp.book_id=b.id WHERE c.user_id=?',(current_user()['id'],)).fetchall()
        for item in cart_rows:
            fmt=str(item['format'] or '').lower()
            digital=fmt in ('ebook','audio','audiobook','digital')
            if not item['sale_enabled']:
                raise CheckoutError(f"{item['title']} is currently unavailable for sale. Remove it from your cart.")
            if digital and not item['digital_available']:
                raise CheckoutError(f"The selected digital format for {item['title']} is unavailable. Remove it from your cart.")
            if not digital and item['inventory_quantity'] < int(item['qty']):
                raise CheckoutError(f"Not enough stock for {item['title']}. Please update your cart.")
        payment_method=request.form.get('payment_method','cash_on_delivery')
        fulfillment_mode=request.form.get('fulfillment_mode','standard')
        if payment_method not in ('online','cash_on_delivery','bank_transfer') or fulfillment_mode not in ('standard','preorder'):
            raise CheckoutError('Choose a valid payment and fulfilment option')
        order_id, created = place_sandbox_order(c, current_user()['id'], request.form.get('request_key',''),request.form.get('coupon',''),request.form.get('address',''))
        c.execute('INSERT INTO order_payment_choices(order_id,payment_method,fulfillment_mode,notes) VALUES(?,?,?,?) ON CONFLICT(order_id) DO UPDATE SET payment_method=excluded.payment_method,fulfillment_mode=excluded.fulfillment_mode,notes=excluded.notes',(order_id,payment_method,fulfillment_mode,request.form.get('payment_notes','')[:300]))
        c.commit()
    except CheckoutError as exc:
        flash(str(exc))
        return redirect('/marketplace')
    finally:
        c.close()
    if created:
        audit('Created unpaid order '+str(order_id))
    flash('Order #'+str(order_id)+' created. No payment charged; choose a gateway to continue.')
    return redirect('/my/orders')

@app.get('/my/orders')
@login_required
def my_orders():
    from commercial_readiness import inspect
    with db() as conn:
        orders = [dict(x) for x in conn.execute("SELECT o.id,o.total,o.status,o.created,COALESCE(pc.payment_method,'Not selected') payment_method,COALESCE(pc.fulfillment_mode,'standard') fulfillment_mode FROM orders o LEFT JOIN order_payment_choices pc ON pc.order_id=o.id WHERE o.user_id=? ORDER BY o.id DESC LIMIT 100",(current_user()['id'],))]
    ready = inspect()['ready']
    return page('My orders', render_template('orders.html', orders=orders, ready=ready))

@app.post('/review/<int:bid>')
@login_required
def review(bid):
    try:
        rating, review_text = validate_review(request.form.get('rating'), request.form.get('text'))
    except InputValidationError as exc:
        abort(400, str(exc))
    with db() as c:
        if not c.execute('SELECT 1 FROM books WHERE id=?', (bid,)).fetchone():
            abort(404)
        # A review is not a verified purchase unless confirmed by the payment/loan system.
        c.execute("INSERT INTO reviews(user_id,book_id,rating,text,spoiler,verified,created) VALUES(?,?,?,?,?,?,?)", (current_user()['id'],bid,rating,review_text,1 if request.form.get('spoiler') else 0,0,datetime.now().isoformat(timespec='seconds')))
    return redirect(url_for('book',bid=bid))

# --------------------------- AI & study ---------------------------
def local_ai_answer(q, book=None):
    q=q.strip(); lower=q.lower()
    if not q:return 'Ask a question about a book, concept, vocabulary item or study goal.'
    if 'compare' in lower:return 'Comparison workspace: choose two or more titles and compare themes, arguments, difficulty, evidence and reader fit. In production, RAG should ground every claim in licensed/indexed passages and return citations.'
    if 'summary' in lower:return 'Demo summary mode is active. For copyrighted titles, this prototype does not reproduce the book; connect a licensed RAG index to create grounded, appropriately scoped summaries.'
    if 'citation' in lower:return 'Citation generator can output APA/MLA/Chicago from catalog metadata. Verify publisher, edition, DOI/ISBN and page details before academic submission.'
    return f'LibraAI Tutor demo: I can help break down “{q}” into key ideas, examples, recall questions and a study plan. Production mode should retrieve authorized passages first, then answer with passage-level citations.'

@app.route('/ai',methods=['GET','POST'])
@login_required
def ai():
    q=request.form.get('q','') if request.method=='POST' else ''
    result=None
    if q:
        if len(q)>2000:
            abort(400, 'Question is too long')
        from ai_tutor_provider import answer_question
        result=answer_question(q, int(current_user()['id']))
    return page('AI Tutor','''<h1>LibraAI Tutor & Research</h1><p class="muted">Answers are grounded in authorized, rights-asserted library passages. AI-generated answers require an explicitly configured provider.</p><div class="grid"><div class="card"><b>Cross-book search</b><p class="muted">Search concepts across authorized source material.</p></div><div class="card"><b>Knowledge graph</b><p class="muted">Explore book, author and concept relationships.</p></div><div class="card"><b>OCR / ISBN scan</b><p class="muted">External OCR and catalog provider setup is still required.</p></div><div class="card"><b>Book recall assistant</b><p class="muted">Use source-backed passages to revisit key ideas.</p></div></div><h2>Ask the tutor</h2><div class="chat"><form class="card" method="post"><textarea name="q" maxlength="2000" required placeholder="Ask a question about authorized library content…">{{q}}</textarea><button class="btn">Ask LibraAI</button></form>{% if result %}<div class="msg"><b>You</b><br>{{q}}</div><div class="msg ai"><b>LibraAI · {{result.status}}</b><br>{{result.answer}}</div>{% if result.citations %}<h3>Sources</h3>{% for source in result.citations %}<div class="card"><b>{{source.title}}</b> · chunk {{source.chunk}}<p>{{source.excerpt}}</p><small>Document {{source.document_id}} · relevance {{source.score}}</small></div>{% endfor %}{% endif %}{% endif %}</div>''',q=q,result=result)

@app.route('/study',methods=['GET','POST'])
def study():
    cards=[]
    if current_user():
        c=db(); cards=c.execute("SELECT f.*,b.title FROM flashcards f JOIN books b ON b.id=f.book_id WHERE f.user_id=? ORDER BY due",(current_user()['id'],)).fetchall(); c.close()
    mins=35; pages=20
    return page('Study Tools','''<h1>Study & language tools</h1><div class="grid"><div class="card"><b>Flashcards + spaced repetition</b><p>Create cards from notes and vocabulary.</p></div><div class="card"><b>Quiz generator</b><p>Active-recall questions with answer checks.</p></div><div class="card"><b>Study plans</b><p>Turn reading goals into daily sessions.</p></div><div class="card"><b>Reading-time estimator</b><p>{{pages}} pages ≈ {{mins}} minutes at demo pace.</p></div><div class="card"><b>Citation generator</b><p>APA · MLA · Chicago metadata templates.</p></div><div class="card"><b>Vocabulary & language learning</b><p>Definitions, translation and review queue.</p></div></div><h2>Create flashcard</h2><form class="card" method="post" action="/flashcard"><select name="book_id">{% for b in books %}<option value="{{b.id}}">{{b.title}}</option>{% endfor %}</select><input class="input" name="front" placeholder="Question / word"><input class="input" name="back" placeholder="Answer / definition"><button class="btn">Add card</button></form><h2>Review queue</h2>{% for c in cards %}<div class="card"><b>{{c['front']}}</b><p>{{c['back']}}</p><span class="pill">Due {{c['due']}}</span></div>{% endfor %}''',cards=cards,books=book_rows(),mins=mins,pages=pages)
@app.post('/flashcard')
@login_required
def flashcard():
    c=db(); c.execute("INSERT INTO flashcards(user_id,book_id,front,back,due,interval_days) VALUES(?,?,?,?,?,1)",(current_user()['id'],request.form['book_id'],request.form['front'],request.form['back'],datetime.now().date().isoformat())); c.commit(); c.close(); return redirect('/study')

# --------------------------- Community / creator ---------------------------
@app.get('/community')
def community():
    c=db()
    clubs=c.execute("SELECT * FROM clubs ORDER BY name").fetchall()
    posts=c.execute("SELECT p.*,u.name,c.name club FROM posts p JOIN users u ON u.id=p.user_id LEFT JOIN clubs c ON c.id=p.club_id ORDER BY p.created DESC LIMIT 20").fetchall()
    stats = {
        'clubs': c.execute('SELECT COUNT(*) n FROM clubs').fetchone()['n'],
        'posts': c.execute('SELECT COUNT(*) n FROM posts').fetchone()['n'],
        'creators': c.execute("SELECT COUNT(*) n FROM users WHERE role IN ('creator','admin')").fetchone()['n'],
        'reviews': c.execute('SELECT COUNT(*) n FROM reviews').fetchone()['n'],
    }
    c.close()
    return page('Community', render_template('community.html', clubs=clubs, posts=posts, user=current_user(), stats=stats))
@app.post('/post')
@login_required
def post():
    body = request.form.get('body', '').strip()
    raw_club_id = request.form.get('club_id', '')
    if not 2 <= len(body) <= 3000:
        abort(400, 'Post must contain between 2 and 3000 characters')
    try:
        club_id = int(raw_club_id)
    except (TypeError, ValueError):
        abort(400, 'Choose a valid reader circle')
    c = db()
    try:
        if not c.execute('SELECT 1 FROM clubs WHERE id=?', (club_id,)).fetchone():
            abort(400, 'Choose a valid reader circle')
        c.execute('INSERT INTO posts(user_id,club_id,body,created) VALUES(?,?,?,?)',
                  (current_user()['id'], club_id, body, datetime.now().isoformat(timespec='seconds')))
        c.commit()
    finally:
        c.close()
    flash('Your community post has been published.')
    return redirect('/community')

@app.route('/creator')
@login_required
def creator():
    user = current_user()
    if user['role'] not in ('creator','admin'): abort(403)
    from creator_analytics import creator_dashboard_data
    conn = db()
    try:
        profile = conn.execute('SELECT store_name FROM merchant_profiles WHERE user_id=?', (user['id'],)).fetchone()
        data = creator_dashboard_data(conn, user['id'])
    finally:
        conn.close()
    store_name = profile['store_name'] if profile else user['name']
    return page('Creator Portal', render_template('creator.html', store_name=store_name, data=data))

# --------------------------- Analytics & admin ---------------------------
@app.route('/analytics')
@login_required
def analytics():
    if current_user()['role'] != 'admin': abort(403)
    c=db(); books=c.execute("SELECT * FROM books ORDER BY reads DESC").fetchall(); loans=c.execute("SELECT COUNT(*) n FROM loans").fetchone()['n']; orders=c.execute("SELECT COALESCE(SUM(total),0) t FROM orders").fetchone()['t']; c.close()
    return page('Analytics', render_template('analytics.html', books=books, total_reads=sum(b['reads'] for b in books), max_reads=max((b['reads'] for b in books), default=1), loans=loans, orders=orders))

@app.get('/admin/dashboard')
@login_required
def admin_dashboard():
    user = current_user()
    if user['role'] != 'admin':
        return page('Library Admin','''<section class="card" style="max-width:680px;margin:40px auto"><span class="pill">Administrator access</span><h1>Library Admin is for administrators</h1><p class="muted">Your account does not have permission to view administration data.</p><a class="btn" href="/">Return to dashboard</a></section>''')
    conn = db()
    try:
        stats = {
            'users': conn.execute('SELECT COUNT(*) FROM users').fetchone()[0],
            'books': conn.execute('SELECT COUNT(*) FROM books').fetchone()[0],
            'in_stock': conn.execute('SELECT COUNT(*) FROM books b LEFT JOIN catalog_products cp ON cp.book_id=b.id WHERE COALESCE(cp.sale_enabled,1)=1 AND COALESCE(cp.digital_available,0)=0 AND COALESCE(cp.inventory_quantity,b.stock,0)>0').fetchone()[0],
            'out_of_stock': conn.execute('SELECT COUNT(*) FROM books b LEFT JOIN catalog_products cp ON cp.book_id=b.id WHERE COALESCE(cp.sale_enabled,1)=1 AND COALESCE(cp.digital_available,0)=0 AND COALESCE(cp.inventory_quantity,b.stock,0)<=0').fetchone()[0],
            'scheduled_chapters': conn.execute("SELECT COUNT(*) FROM manga_chapters WHERE status='scheduled'").fetchone()[0],
            'active_entitlements': conn.execute("SELECT COUNT(*) FROM subscription_entitlements WHERE status='active'").fetchone()[0],
            'orders': conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0],
            'loans': conn.execute('SELECT COUNT(*) FROM loans').fetchone()[0],
        }
        audits = conn.execute('SELECT a.action,a.created,u.name FROM audit a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.created DESC LIMIT 8').fetchall()
    finally:
        conn.close()
    return page('Admin Dashboard','''<h1>Library Admin Dashboard</h1><p class="muted">Live totals from the platform database.</p><div class="grid"><div class="card"><div class="muted">Accounts</div><div class="kpi">{{stats.users}}</div></div><div class="card"><div class="muted">Catalog titles</div><div class="kpi">{{stats.books}}</div></div><div class="card"><div class="muted">Orders</div><div class="kpi">{{stats.orders}}</div></div><div class="card"><div class="muted">Loans</div><div class="kpi">{{stats.loans}}</div></div><div class="card"><div class="muted">In Stock</div><div class="kpi">{{stats.in_stock}}</div></div><div class="card"><div class="muted">Out of Stock</div><div class="kpi">{{stats.out_of_stock}}</div></div><div class="card"><div class="muted">Scheduled chapters</div><div class="kpi">{{stats.scheduled_chapters}}</div></div><div class="card"><div class="muted">Active entitlements</div><div class="kpi">{{stats.active_entitlements}}</div></div></div><h2>Administration</h2><div class="row"><a class="btn" href="/admin">Open library controls</a><a class="btn ghost" href="/admin/users/new">Create account</a><a class="btn ghost" href="/admin/fulfillment">Fulfillment</a><a class="btn ghost" href="/admin/catalog/new">Add catalog title</a></div><h2>Recent activity</h2>{% if audits %}<table class="table"><thead><tr><th>Activity</th><th>Account</th><th>Time</th></tr></thead><tbody>{% for item in audits %}<tr><td>{{item['action']}}</td><td>{{item['name'] or 'System'}}</td><td>{{item['created']}}</td></tr>{% endfor %}</tbody></table>{% else %}<p class="muted">No recent administrative activity.</p>{% endif %}''',stats=stats,audits=audits)

@app.route('/admin',methods=['GET','POST'])
@login_required
def admin():
    if current_user()['role'] != 'admin':
        return page('Library Admin','''<section class="card" style="max-width:680px;margin:40px auto"><span class="pill">Administrator access</span><h1>Library Admin is for administrators</h1><p class="muted">Your account does not have permission to manage the library. Your account and library data are unchanged.</p><div class="row"><a class="btn" href="/">Return to dashboard</a><a class="btn ghost" href="/account">View my account</a></div></section>''')
    c=db(); books=c.execute("SELECT b.*, COALESCE(cp.product_type,'physical_book') product_type, COALESCE(cp.sale_enabled,1) sale_enabled, COALESCE(cp.digital_available,0) digital_available, COALESCE(cp.inventory_quantity,b.stock,0) inventory_quantity, CASE WHEN COALESCE(cp.sale_enabled,1)=0 THEN 'Unavailable' WHEN COALESCE(cp.digital_available,0)=1 THEN 'Available Online' WHEN COALESCE(cp.inventory_quantity,b.stock,0)>0 THEN 'In Stock' ELSE 'Out of Stock' END availability_status FROM books b LEFT JOIN catalog_products cp ON cp.book_id=b.id ORDER BY b.title").fetchall(); rooms=c.execute("SELECT * FROM rooms").fetchall(); autos=c.execute("SELECT * FROM automations").fetchall(); suppliers=c.execute("SELECT * FROM suppliers").fetchall(); audits=c.execute("SELECT a.*,u.name FROM audit a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.created DESC LIMIT 10").fetchall(); stats={'scheduled_chapters':c.execute("SELECT COUNT(*) FROM manga_chapters WHERE status='scheduled'").fetchone()[0], 'active_entitlements':c.execute("SELECT COUNT(*) FROM subscription_entitlements WHERE status='active'").fetchone()[0]}; c.close()
    return page('Library Admin','''<h1>Library network administration</h1><p class="muted">Multi-branch catalog, inventory, shelf location, acquisitions, rooms, automations, security and archive workflows.</p><div class="grid"><div class="card"><b>Catalog & metadata</b><p>ISBN/API-ready metadata, formats, languages.</p></div><div class="card"><b>Barcode / RFID / kiosk</b><p>Hardware integration seam + self-service workflow.</p></div><div class="card"><b>Digital archive</b><p>Preservation metadata, rare-book access policies.</p></div><div class="card"><b>Stock audits</b><p>Lost/damaged status and branch inventory.</p></div></div><p><a class="btn" href="/admin/fulfillment">Fulfillment Operations Dashboard</a> <a class="btn ghost" href="/admin/users/new">Create platform account</a></p><h2>Catalog editor</h2><p><a class="btn" href="/admin/catalog/new">Add new book</a></p><h2>Catalog CSV management</h2><div class="card"><p>Import a validated UTF-8 CSV (up to 500 books per file). Import is atomic. Only import metadata you have permission to use; importing does not grant book-content rights.</p><a class="btn" href="/admin/catalog/export.csv">Export catalog CSV</a><form method="post" action="/admin/catalog/import" enctype="multipart/form-data"><label for="catalog-file">Catalog CSV</label><input id="catalog-file" name="catalog" type="file" accept=".csv,text/csv" required><button class="btn" type="submit">Import catalog</button></form></div><h2>Inventory & availability</h2><p class="muted">This table reads the same catalog inventory used by public APIs and cart validation.</p><table class="table"><tr><th>Product</th><th>Type</th><th>Branch / Shelf</th><th>Quantity</th><th>Availability</th><th>Digital</th><th>ISBN</th></tr>{% for b in books %}<tr><td><a href="/admin/catalog/{{b['id']}}/edit">{{b['title']}} ✎</a></td><td>{{b['product_type']}}</td><td>{{b['branch']}} · {{b['shelf']}}</td><td>{{b['inventory_quantity']}}</td><td><span class="pill">{{b['availability_status']}}</span></td><td>{{'Yes' if b['digital_available'] else 'No'}}</td><td>{{b['isbn']}}</td></tr>{% endfor %}</table><h2>Manga publishing & memberships</h2><div class="card"><p>Use the protected APIs to publish chapters with a release time and optional early-access time. Admins can grant/revoke plan entitlements; chapter access is evaluated against the active entitlement and release schedule.</p><span class="pill">Scheduled: {{stats.scheduled_chapters}}</span><span class="pill">Active memberships: {{stats.active_entitlements}}</span></div><h2>Study-room booking</h2><div class="grid">{% for r in rooms %}<div class="card"><b>{{r['name']}}</b><p>{{r['branch']}} · {{r['capacity']}} seats</p><span class="pill">{{r['status']}}</span></div>{% endfor %}</div><h2>Workflow automations</h2><table class="table"><tr><th>Name</th><th>Trigger</th><th>Action</th><th>State</th></tr>{% for a in autos %}<tr><td>{{a['name']}}</td><td>{{a['trigger_text']}}</td><td>{{a['action_text']}}</td><td>{{'On' if a['enabled'] else 'Off'}}</td></tr>{% endfor %}</table><h2>Acquisitions & suppliers</h2><div class="grid">{% for s in suppliers %}<div class="card"><b>{{s['name']}}</b><p>{{s['contact']}}</p><span class="pill">Purchase orders</span></div>{% endfor %}</div><h2>Trust, access & audit logs</h2><div class="card"><span class="pill">Role-based access</span><span class="pill">Secure API boundary</span><span class="pill">Privacy settings</span><span class="pill">Backups</span><span class="pill">Accessibility</span><span class="pill">Bangla / English</span><span class="pill">PWA/mobile</span></div>{% for a in audits %}<div class="small muted">{{a['created']}} · {{a['name'] or 'system'}} · {{a['action']}}</div>{% endfor %}''',books=books,rooms=rooms,autos=autos,suppliers=suppliers,audits=audits,stats=stats)

def _fulfillment_page_args(args):
    """Strict, bounded query validation shared by HTML and CSV endpoints."""
    try:
        limit = int(args.get('limit', '50'))
        offset = int(args.get('offset', '0'))
    except (ValueError, TypeError, OverflowError):
        raise ValueError('Invalid pagination')
    if args.get('exceptions', '0') not in ('0', '1'):
        raise ValueError('Invalid exceptions filter')
    if not 1 <= limit <= 100 or not 0 <= offset <= 1000000:
        raise ValueError('Pagination out of bounds')
    return limit, offset, args.get('exceptions', '0') == '1'


@app.get('/admin/fulfillment/export.csv')
@login_required
def admin_fulfillment_export():
    """Export only the selected audited page; never export customer PII."""
    if current_user()['role'] != 'admin': abort(403)
    try:
        limit, offset, exceptions_only = _fulfillment_page_args(request.args)
    except ValueError:
        abort(400)
    from admin_fulfillment_dashboard import dashboard_data
    from mixed_fulfillment_audit import write_csv_report
    c = db()
    try:
        rows = dashboard_data(c, limit, offset, exceptions_only)
    finally:
        c.close()
    buffer = io.StringIO(newline='')
    write_csv_report({'orders': rows}, buffer)
    response = Response('\ufeff' + buffer.getvalue(), mimetype='text/csv; charset=utf-8')
    response.headers['Content-Disposition'] = 'attachment; filename="fulfillment_audit.csv"'
    response.headers['Cache-Control'] = 'no-store, private'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.get('/admin/fulfillment')
@login_required
def admin_fulfillment():
    """Read-only operational view. Requires an authenticated administrator."""
    if current_user()['role'] != 'admin': abort(403)
    from admin_fulfillment_dashboard import dashboard_page
    try:
        limit, offset, exceptions_only = _fulfillment_page_args(request.args)
    except ValueError:
        abort(400)
    c = db()
    try:
        audit_page = dashboard_page(c, limit, offset, exceptions_only)
    except ValueError:
        abort(400)
    finally:
        c.close()
    rows = audit_page['rows']
    return page('Fulfillment Operations','''<h1>Fulfillment Operations</h1>
<p class="muted">Read-only order health checks. Exceptions require manual review; no payments or deliveries are changed here.</p>
<p><a class="btn" href="/admin">Back to Admin</a> <a class="btn" href="/admin/fulfillment?exceptions=1">Exceptions only</a> <a class="btn" href="/admin/fulfillment">All orders</a> <a class="btn" href="{{url_for('admin_fulfillment_export', limit=limit, offset=offset, exceptions='1' if exceptions_only else '0')}}">Export this page (CSV)</a></p>
<table class="table"><thead><tr><th>Order</th><th>Status</th><th>Print lines</th><th>Digital lines</th><th>Audit</th></tr></thead>
<tbody>{% for row in rows %}<tr><td>#{{row.order_id}}</td><td>{{row.status}}</td><td>{{row.print_line_count}}</td><td>{{row.digital_line_count}}</td><td>{% if row.ready %}Ready{% else %}{% for issue in row.issues %}<div>{{issue}}</div>{% endfor %}{% endif %}</td></tr>{% endfor %}</tbody></table>
<p class="muted">Showing up to {{limit}} orders from offset {{offset}}. Exceptions filter applies only to this page, not all orders.</p>
{% if audit_page.has_previous %}<a class="btn" href="{{url_for('admin_fulfillment', limit=limit, offset=[0, offset-limit]|max, exceptions='1' if exceptions_only else '0')}}">Previous page</a>{% endif %}
{% if audit_page.has_next %}<a class="btn" href="{{url_for('admin_fulfillment', limit=limit, offset=offset+limit, exceptions='1' if exceptions_only else '0')}}">Next page</a>{% endif %}''', rows=rows, limit=limit, offset=offset, exceptions_only=exceptions_only, audit_page=audit_page)

# --------------------------- Feature coverage ---------------------------
@app.route('/features')
def features():
    groups={
    'Discover & rank':['Most Read','Highest Rated','Bestsellers','New Arrivals','Fast-rising releases','Genre rankings','Reading-based ratings','Verified reader activity','Popularity trends','Search / filter / sort','Book of the day','Personalized recommendations','Spoiler-aware reviews'],
    'Read & annotate':['Two-page book view','Page-turn / continuous scroll','Manga/comics mode','Auto-scroll / speed','Audio reader','Bookmarks','Colored highlights','Private notes','Quotes','Dictionary','Translation','Reading position sync','Progress tracking','Font/theme/accessibility','Licensed offline access'],
    'Buy, borrow & subscribe':['Read-before-buy samples','Pay-per-read','Subscriptions','Student/family/institutional plans','eBook/print/audiobook marketplace','Cart','Coupons','Gifting','Wishlist','Checkout','Delivery/order tracking','Lending','Renewals','Reservations','Waitlists','Inter-library loans','Resale marketplace','Dispute workflow'],
    'AI learning & research':['AI tutor','RAG Q&A','Summaries','Chapter explanations','Cross-book search','Book comparison','Knowledge graph','Vocabulary/language learning','OCR/ISBN scan','Flashcards','Quizzes','Study plans','Spaced repetition','Citation generator','Reading-time estimator','Book recall assistant'],
    'Library administration':['Multi-branch/library accounts','Catalog/metadata','ISBN APIs','Inventory','Shelf locator','Barcode/RFID','Self-service kiosk','Acquisitions','Suppliers/purchase orders','Lost/damaged tracking','Stock audits','Study-room booking','Digital archive','Rare-book preservation','Donation matching'],
    'Community & creators':['Book clubs','Discussion rooms','Events','Live reading rooms','Shared lists','Group goals','Reviews','Author Q&A','Author dashboard','Publisher portal','Licensing','Royalty reporting','Book donations','Second-hand listings'],
    'Analytics, automation & trust':['Reading analytics','Circulation/revenue dashboards','Demand forecasting','Workflow automation','Due-date alerts','Inventory alerts','Payments/refunds integration','Role-based access','Audit logs','Secure APIs','Backups','Privacy settings','Accessibility','Bangla/English UI','Mobile/PWA support']}
    return page('Feature Coverage','''<h1>Full PDF feature coverage map</h1><p class="muted">Every requested capability is represented either as working local prototype behavior or as an explicit production integration seam where external licensing, hardware, payment, AI or provider infrastructure is required.</p>{% for g,items in groups.items() %}<h2>{{g}}</h2><div class="card">{% for x in items %}<span class="pill">✓ {{x}}</span>{% endfor %}</div>{% endfor %}<h2>Production boundary</h2><div class="card"><p>Real book content/downloads require title rights. Real OCR, translation, TTS, ISBN metadata, RAG/LLM, email/SMS, payments/refunds, delivery tracking and RFID/barcode hardware require configured providers. This prototype intentionally does not fake those external services.</p></div>''',groups=groups)

# --------------------------- JSON API ---------------------------
@app.get('/manifest.webmanifest')
def manifest():
    return jsonify({
        'id': '/', 'name':'LibraAI Reading & Learning', 'short_name':'LibraAI',
        'description':'Read, study, and organize your library with LibraAI.',
        'start_url':'/', 'scope':'/', 'display':'standalone',
        'background_color':'#090f26', 'theme_color':'#101a36',
        'icons':[
            {'src':'/assets/pwa-icon-192.png','sizes':'192x192','type':'image/png','purpose':'any'},
            {'src':'/assets/pwa-icon-512.png','sizes':'512x512','type':'image/png','purpose':'any'},
            {'src':'/assets/pwa-icon-512.png','sizes':'512x512','type':'image/png','purpose':'maskable'}
        ]
    }), 200, {'Content-Type':'application/manifest+json'}

@app.get('/offline')
def offline_page():
    # Generic public fallback only; no account, reading, or purchase data is stored offline.
    html = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#101a36"><title>Offline · LibraAI</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#090f26;color:#eaf0ff;font:16px system-ui,sans-serif}.card{max-width:520px;margin:24px;padding:32px;border:1px solid #27355b;border-radius:24px;background:#101a36}h1{margin-top:0}p{line-height:1.6;color:#b9c5df}button{border:0;border-radius:10px;padding:12px 16px;background:#8570ff;color:white;font-weight:700;cursor:pointer}</style></head><body><main class="card"><h1>You’re offline</h1><p>LibraAI couldn’t reach the server. Your private account, library, and checkout pages are not saved for offline use.</p><p>Reconnect to continue reading, syncing progress, or managing your account.</p><button onclick="location.reload()">Try again</button></main></body></html>"""
    return app.response_class(html, mimetype='text/html')

@app.get('/favicon.ico')
@app.get('/assets/pwa-icon-192.png')
def pwa_icon_192():
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), 'pwa-icon-192.png', mimetype='image/png')

@app.get('/assets/pwa-icon-512.png')
def pwa_icon_512():
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), 'pwa-icon-512.png', mimetype='image/png')

@app.get('/service-worker.js')
def service_worker():
    # Cache only public offline/help assets. Never cache private pages, account data, or API responses.
    js = """const CACHE='libraai-public-shell-v2';const ASSETS=['/offline','/manifest.webmanifest','/assets/pwa-icon-192.png','/assets/pwa-icon-512.png'];self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)));self.skipWaiting()});self.addEventListener('activate',event=>{event.waitUntil((async()=>{const keys=await caches.keys();await Promise.all(keys.filter(key=>key.startsWith('libraai-')&&key!==CACHE).map(key=>caches.delete(key)));await self.clients.claim()})())});self.addEventListener('fetch',event=>{const request=event.request;const url=new URL(request.url);if(request.method!=='GET'||url.origin!==self.location.origin)return;if(request.mode==='navigate'){event.respondWith(fetch(request).catch(async()=>{const cache=await caches.open(CACHE);return (await cache.match('/offline'))||Response.error()}));return}if(ASSETS.includes(url.pathname)){event.respondWith(caches.match(request).then(cached=>cached||fetch(request)));}})"""
    return app.response_class(js, mimetype='application/javascript', headers={'Service-Worker-Allowed':'/'})

@app.get('/api/books')
def api_books(): return jsonify(book_rows(request.args.get('sort','trending'),request.args.get('genre'),request.args.get('q')))
@app.get('/api/catalog/products')
def api_catalog_products():
    """Shared product catalog for physical books and digital formats."""
    products = book_rows(request.args.get('sort','trending'), request.args.get('genre'), request.args.get('q'))
    kind = request.args.get('type')
    if kind:
        products = [p for p in products if p.get('product_type') == kind]
    return jsonify({'items': products, 'count': len(products)}), 200, {'Cache-Control':'no-store'}

@app.get('/api/catalog/products/<int:book_id>')
def api_catalog_product_detail(book_id):
    products = [p for p in book_rows('trending') if int(p.get('id',0)) == book_id]
    if not products: return jsonify({'error':'Product not found'}), 404
    return jsonify(products[0]), 200, {'Cache-Control':'no-store'}

@app.get('/api/manga/<int:series_book_id>/chapters')
def api_manga_chapters(series_book_id):
    user = current_user()
    conn = db()
    try:
        if not conn.execute('SELECT 1 FROM books WHERE id=?',(series_book_id,)).fetchone():
            return jsonify({'error':'Series not found'}), 404
        rows = conn.execute("SELECT * FROM manga_chapters WHERE series_book_id=? AND status IN ('published','scheduled') ORDER BY chapter_number",(series_book_id,)).fetchall()
        now = datetime.now().isoformat(timespec='seconds')
        entitled = False
        if user:
            entitlement = conn.execute("SELECT 1 FROM subscription_entitlements WHERE user_id=? AND status='active' AND (expires_at IS NULL OR expires_at>?) LIMIT 1",(user['id'],now)).fetchone()
            entitled = bool(entitlement)
        items=[]
        for row in rows:
            item=dict(row)
            released = item['status']=='published' and item['release_at'] <= now
            early = bool(item.get('early_access_at') and item['early_access_at'] <= now and entitled)
            item['is_accessible'] = bool((released or early) and (not item['membership_required'] or entitled))
            item['access_status'] = 'Available' if item['is_accessible'] else ('Subscription Required' if item['membership_required'] or item.get('early_access_at') else 'Scheduled')
            if not item['is_accessible']: item['content_url'] = None
            items.append(item)
        return jsonify({'items':items,'subscription_active':entitled}), 200, {'Cache-Control':'private, no-store'}
    finally: conn.close()

@app.post('/api/admin/catalog/products/<int:book_id>')
@login_required
def api_admin_update_catalog_product(book_id):
    user=current_user()
    if not user or user['role']!='admin': abort(403)
    data=request.get_json(silent=True)
    if not isinstance(data,dict): return jsonify({'error':'JSON object required'}),400
    allowed_types={'physical_book','ebook','audiobook','manga','stationery','study_material'}
    kind=data.get('product_type','physical_book')
    qty=data.get('inventory_quantity')
    sale=data.get('sale_enabled',True); digital=data.get('digital_available',False)
    if kind not in allowed_types or type(qty) is not int or qty<0 or type(sale) is not bool or type(digital) is not bool:
        return jsonify({'error':'Invalid product type, inventory quantity, or availability flags'}),400
    conn=db()
    try:
        if not conn.execute('SELECT 1 FROM books WHERE id=?',(book_id,)).fetchone(): return jsonify({'error':'Book not found'}),404
        conn.execute("INSERT INTO catalog_products(book_id,product_type,sale_enabled,digital_available,inventory_quantity,access_type,updated_at) VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(book_id) DO UPDATE SET product_type=excluded.product_type,sale_enabled=excluded.sale_enabled,digital_available=excluded.digital_available,inventory_quantity=excluded.inventory_quantity,updated_at=CURRENT_TIMESTAMP",(book_id,kind,int(sale),int(digital),qty,data.get('access_type','purchase')))
        conn.execute('UPDATE books SET stock=? WHERE id=?',(qty,book_id)); conn.commit()
        item=next((p for p in book_rows('trending') if int(p['id'])==book_id),None)
        return jsonify({'ok':True,'product':item}),200,{'Cache-Control':'no-store'}
    finally: conn.close()

@app.post('/api/admin/manga/<int:series_book_id>/chapters')
@login_required
def api_admin_publish_manga_chapter(series_book_id):
    user=current_user()
    if not user or user['role'] not in ('admin','creator'): abort(403)
    data=request.get_json(silent=True)
    if not isinstance(data,dict): return jsonify({'error':'JSON object required'}),400
    try: number=float(data['chapter_number'])
    except (KeyError,TypeError,ValueError): return jsonify({'error':'chapter_number is required'}),400
    title=str(data.get('title','')).strip()
    if number<=0 or not title or len(title)>180: return jsonify({'error':'Valid chapter number and title are required'}),400
    release_at=str(data.get('release_at') or datetime.now().isoformat(timespec='seconds'))
    early_at=data.get('early_access_at')
    status=data.get('status','scheduled')
    if status not in ('scheduled','published','draft'): return jsonify({'error':'Invalid status'}),400
    conn=db()
    try:
        if not conn.execute('SELECT 1 FROM books WHERE id=?',(series_book_id,)).fetchone(): return jsonify({'error':'Series not found'}),404
        try:
            cur=conn.execute('INSERT INTO manga_chapters(series_book_id,chapter_number,title,content_url,release_at,early_access_at,membership_required,status) VALUES(?,?,?,?,?,?,?,?)',(series_book_id,number,title,data.get('content_url'),release_at,early_at,int(bool(data.get('membership_required',False))),status))
        except sqlite3.IntegrityError: return jsonify({'error':'Chapter number already exists for this series'}),409
        conn.commit(); row=conn.execute('SELECT * FROM manga_chapters WHERE id=?',(cur.lastrowid,)).fetchone()
        return jsonify({'ok':True,'chapter':dict(row)}),201,{'Cache-Control':'no-store'}
    finally: conn.close()

@app.get('/api/subscriptions/me')
def api_my_subscription_entitlement():
    user=current_user()
    if not user: return jsonify({'active':False,'requires_sign_in':True}),200,{'Cache-Control':'no-store'}
    conn=db()
    try:
        now=datetime.now().isoformat(timespec='seconds')
        rows=conn.execute("SELECT plan_code,status,starts_at,expires_at FROM subscription_entitlements WHERE user_id=? AND status='active' AND (expires_at IS NULL OR expires_at>?) ORDER BY starts_at DESC",(user['id'],now)).fetchall()
        return jsonify({'active':bool(rows),'entitlements':[dict(r) for r in rows]}),200,{'Cache-Control':'private, no-store'}
    finally: conn.close()

@app.post('/api/admin/subscriptions/entitlements')
@login_required
def api_admin_grant_subscription_entitlement():
    user=current_user()
    if not user or user['role']!='admin': abort(403)
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or type(data.get('user_id')) is not int or not str(data.get('plan_code','')).strip(): return jsonify({'error':'user_id and plan_code are required'}),400
    conn=db()
    try:
        if not conn.execute('SELECT 1 FROM users WHERE id=?',(data['user_id'],)).fetchone(): return jsonify({'error':'User not found'}),404
        conn.execute("INSERT INTO subscription_entitlements(user_id,plan_code,status,expires_at) VALUES(?,?,'active',?) ON CONFLICT(user_id,plan_code) DO UPDATE SET status='active',expires_at=excluded.expires_at",(data['user_id'],str(data['plan_code']).strip()[:60],data.get('expires_at')))
        conn.commit(); return jsonify({'ok':True,'user_id':data['user_id'],'plan_code':data['plan_code'],'status':'active'}),200
    finally: conn.close()

@app.get('/api/wishlist')
def api_wishlist_list():
    """Return the signed-in user's wishlist from the persistent database for cross-device sync."""
    user = current_user()
    if not user: return jsonify({'error':'Authentication required'}), 401, {'Cache-Control':'no-store'}
    conn = db()
    try:
        rows = conn.execute('''SELECT b.id,b.title,b.author,b.genre,b.rating,b.reads,b.sales,b.year,b.format,b.price,b.stock,b.description,b.language,b.isbn
            FROM wishlist w JOIN books b ON b.id=w.book_id WHERE w.user_id=? ORDER BY w.id DESC''',
            (user['id'],)).fetchall()
        return jsonify({'items':[dict(row) for row in rows]}), 200, {'Cache-Control':'private, no-store'}
    finally:
        conn.close()

@app.post('/api/wishlist')
def api_wishlist_update():
    """Idempotently save/remove a catalog book for the authenticated account."""
    user = current_user()
    if not user: return jsonify({'error':'Authentication required'}), 401, {'Cache-Control':'no-store'}
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or type(data.get('book_id')) is not int or data['book_id'] < 1 or type(data.get('saved')) is not bool:
        return jsonify({'error':'book_id integer and saved boolean are required'}), 400
    conn = db()
    try:
        if not conn.execute('SELECT 1 FROM books WHERE id=?', (data['book_id'],)).fetchone():
            return jsonify({'error':'Book not found in live catalog'}), 404
        if data['saved']:
            conn.execute('INSERT OR IGNORE INTO wishlist(user_id,book_id) VALUES(?,?)', (user['id'], data['book_id']))
        else:
            conn.execute('DELETE FROM wishlist WHERE user_id=? AND book_id=?', (user['id'], data['book_id']))
        conn.commit()
        return jsonify({'ok':True,'book_id':data['book_id'],'saved':data['saved']}), 200, {'Cache-Control':'private, no-store'}
    finally:
        conn.close()

@app.get('/api/wishlist/<int:book_id>')
@login_required
def api_wishlist_status(book_id):
    conn = db()
    try:
        if not conn.execute('SELECT 1 FROM books WHERE id=?', (book_id,)).fetchone():
            abort(404)
        saved = conn.execute('SELECT 1 FROM wishlist WHERE user_id=? AND book_id=?', (current_user()['id'], book_id)).fetchone() is not None
        return jsonify({'saved': saved}), 200, {'Cache-Control': 'private, no-store'}
    finally:
        conn.close()

@app.get('/api/books/<int:book_id>')
def api_book_detail(book_id):
    if book_id < 1:
        abort(404)
    conn = db()
    try:
        item = conn.execute('SELECT id,title,author,genre,rating,reads,sales,year,format,price,stock,description,language,isbn,branch,shelf FROM books WHERE id=?', (book_id,)).fetchone()
        if item is None:
            return jsonify({'error': 'Book not found'}), 404
        return jsonify(dict(item))
    finally:
        conn.close()

@app.get('/books/<int:book_id>')
def public_book_detail(book_id):
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), 'book_detail.html')

@app.get('/assets/book_detail.css')
def book_detail_css():
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), 'book_detail.css', mimetype='text/css')

@app.get('/assets/book_detail.js')
def book_detail_js():
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), 'book_detail.js', mimetype='application/javascript')

@app.post('/api/search/semantic')
def api_semantic_search():
    """Search real catalog records by meaning using external embeddings when configured."""
    data = request.get_json(silent=True) or {}
    query = data.get('query', '')
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        return jsonify({'error': 'query must be a non-empty string up to 500 characters'}), 400
    # Public search is rate-limited to protect external embedding spend. Store
    # only a keyed digest of the client address, never the raw address.
    client_ip = request.remote_addr or 'unknown'
    limiter_key = hmac.new(app.secret_key.encode(), ('semantic-search|' + client_ip).encode(), hashlib.sha256).hexdigest()
    now = int(time.time())
    conn = db()
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS semantic_search_limits (identity TEXT PRIMARY KEY, window_started INTEGER NOT NULL, request_count INTEGER NOT NULL)')
        limit_row = conn.execute('SELECT window_started,request_count FROM semantic_search_limits WHERE identity=?', (limiter_key,)).fetchone()
        if limit_row and now - int(limit_row[0]) < 60 and int(limit_row[1]) >= 30:
            return jsonify({'error': 'Search rate limit reached. Please wait a minute and try again.'}), 429, {'Retry-After': '60'}
        if not limit_row or now - int(limit_row[0]) >= 60:
            conn.execute('INSERT INTO semantic_search_limits(identity,window_started,request_count) VALUES(?,?,1) ON CONFLICT(identity) DO UPDATE SET window_started=excluded.window_started,request_count=1', (limiter_key, now))
        else:
            conn.execute('UPDATE semantic_search_limits SET request_count=request_count+1 WHERE identity=?', (limiter_key,))
        conn.execute('DELETE FROM semantic_search_limits WHERE window_started < ?', (now - 3600,))
        conn.commit()
    finally:
        conn.close()
    from semantic_search import rank_books
    rows = book_rows('trending')
    result = rank_books(query, rows, connect=db, limit=10)
    books = []
    for item in result['results']:
        books.append({
            'id': item.get('id'), 'title': item.get('title'), 'author': item.get('author'),
            'genre': item.get('genre'), 'rating': item.get('rating'), 'reads': item.get('reads'),
            'sales': item.get('sales'), 'year': item.get('year'), 'format': item.get('format'),
            'price': item.get('price'), 'stock': item.get('stock'), 'description': item.get('description'),
            'language': item.get('language'), 'product_type': item.get('product_type'),
            'sale_enabled': item.get('sale_enabled'), 'digital_available': item.get('digital_available'),
            'inventory_quantity': item.get('inventory_quantity'), 'availability_status': item.get('availability_status'),
            'semantic_score': item.get('semantic_score'), 'url': f"/book/{item.get('id')}"
        })
    return jsonify({'status': 'ok', 'mode': result['mode'], 'query': query.strip(), 'count': len(books), 'results': books}), 200, {'Cache-Control': 'no-store'}

@app.get('/api/books/page')
def api_books_page():
    from catalog_pagination import parse_catalog_query, paginate
    try:
        page_number, page_size, order, genre, query = parse_catalog_query(request.args)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    result = paginate(book_rows(order, genre, query), page_number, page_size)
    return jsonify(result)

def _catalog_recommendation(question):
    """Return grounded catalog recommendations for preference-based chat prompts."""
    q = question.casefold()
    intent_terms = ('recommend', 'suggest', 'recommendation', 'i like', 'i love', 'i enjoy',
                    'ami', 'bhalobashi', 'pochondo', 'boi porte', 'romance', 'romantic',
                    'mystery', 'thriller', 'fantasy', 'science fiction', 'sci-fi', 'horror',
                    'self-help', 'history', 'comedy', 'adventure', 'romantic')
    if not any(term in q for term in intent_terms):
        return None
    rows = book_rows('trending')
    if not rows:
        return {'status': 'evidence_only', 'answer': 'I could not find books in the current catalog yet. Try again after books are added.'}
    aliases = {
        'romance': ('romance', 'romantic', 'love story', 'love stories', 'প্রেম', 'রোমান্স'),
        'mystery': ('mystery', 'detective', 'crime'),
        'thriller': ('thriller', 'suspense', 'psychological'),
        'fantasy': ('fantasy', 'magic', 'magical'),
        'science fiction': ('science fiction', 'sci-fi', 'scifi', 'space'),
        'horror': ('horror', 'ghost', 'supernatural'),
        'self-help': ('self-help', 'self help', 'personal development'),
        'history': ('history', 'historical'),
        'adventure': ('adventure', 'quest', 'journey'),
    }
    matched = []
    for genre, terms in aliases.items():
        if any(term in q for term in terms):
            matched.extend(terms)
    from semantic_search import rank_books
    semantic = rank_books(question, rows, connect=db, limit=5)
    selected = semantic['results']
    if not selected:
        scored = []
        for book in rows:
            searchable = ' '.join(str(book.get(k) or '') for k in ('title','author','genre','description')).casefold()
            score = 0
            if matched:
                score += 8 if any(t in str(book.get('genre') or '').casefold() for t in matched) else 0
                score += sum(2 for t in matched if t in searchable)
            score += float(book.get('rating') or 0) * .2
            score += min(int(book.get('reads') or 0), 1000000) / 1000000
            if score > 0 or not matched:
                scored.append((score, book))
        scored.sort(key=lambda pair: (pair[0], score_book(pair[1], 'trending')), reverse=True)
        selected = [b for _, b in scored[:5]]
    if not selected:
        selected = rows[:5]
    preference = next((name.title() for name, terms in aliases.items() if any(t in q for t in terms)), 'your reading preferences')
    lines = [f"Based on your interest in {preference}, here are matching books from the LibraAI catalog:"]
    for b in selected:
        lines.append(f"• {b.get('title','Untitled')} — {b.get('author','Unknown author')} | {b.get('genre','Genre not listed')} | Rating {b.get('rating', 'N/A')} | /book/{b.get('id')}")
    lines.append('These suggestions are based on catalog metadata, not invented titles. Tell me a favorite author, mood, language, or preferred difficulty to refine the list.')
    return {'status': 'catalog_recommendations', 'search_mode': semantic.get('mode', 'local_semantic_fallback'), 'answer': '\n'.join(lines), 'recommendations': [{'id': b.get('id'), 'title': b.get('title'), 'author': b.get('author'), 'genre': b.get('genre'), 'rating': b.get('rating'), 'url': f"/book/{b.get('id')}"} for b in selected]}

@app.route('/api/ai/history', methods=['GET', 'POST', 'DELETE'])
def api_ai_history():
    """Account-scoped durable AI conversation history; never shared between users."""
    user = current_user()
    if not user:
        return jsonify({'error': 'Sign in required', 'code': 'authentication_required'}), 401
    uid = int(user['id'])
    if request.method == 'GET':
        with db() as conn:
            rows = conn.execute(
                'SELECT role, content AS text, created_at FROM '
                'ai_conversation_messages WHERE user_id=? ORDER BY id DESC LIMIT 100',
                (uid,),
            ).fetchall()
        return jsonify({'messages': [dict(row) for row in reversed(rows)]})
    if request.method == 'DELETE':
        with db() as conn:
            conn.execute('DELETE FROM ai_conversation_messages WHERE user_id=?', (uid,))
        return jsonify({'ok': True, 'messages': []})
    data = request.get_json(silent=True) or {}
    messages = data.get('messages')
    if not isinstance(messages, list) or len(messages) > 100:
        return jsonify({'error': 'messages must be a list of at most 100 items'}), 400
    clean = []
    for item in messages:
        if not isinstance(item, dict) or item.get('role') not in ('user', 'assistant'):
            return jsonify({'error': 'Each message must have a valid role and text'}), 400
        content = item.get('text')
        if not isinstance(content, str) or not content.strip() or len(content) > 4000:
            return jsonify({'error': 'Message text must contain 1–4000 characters'}), 400
        clean.append((item['role'], content.strip()))
    with db() as conn:
        conn.execute('DELETE FROM ai_conversation_messages WHERE user_id=?', (uid,))
        conn.executemany(
            'INSERT INTO ai_conversation_messages(user_id, role, content) VALUES(?,?,?)',
            [(uid, role, content) for role, content in clean[-100:]],
        )
    return jsonify({'ok': True, 'count': len(clean[-100:])})


@app.post('/api/study-tools')
@login_required
def api_study_tools():
    """Generate a study set and optionally persist it to the signed-in account."""
    data = request.get_json(silent=True) or {}
    from study_tools import generate_study_set
    try:
        result = generate_study_set(data.get('text', ''), mode=data.get('mode', 'auto'))
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    if data.get('save') is True:
        title = data.get('title', 'My study set')
        if not isinstance(title, str):
            return jsonify({'error': 'title must be text'}), 400
        title = re.sub(r'\s+', ' ', title).strip()[:120] or 'My study set'
        encoded = json.dumps(result, ensure_ascii=False, separators=(',', ':'))
        if len(encoded) > 100000:
            return jsonify({'error': 'Generated study set is too large to save.'}), 413
        user = current_user()
        conn = db()
        try:
            cursor = conn.execute(
                'INSERT INTO saved_study_sets(user_id,title,result_json) VALUES(?,?,?)',
                (int(user['id']), title, encoded),
            )
            conn.commit()
            result['saved_set'] = {'id': cursor.lastrowid, 'title': title}
        finally:
            conn.close()
    return jsonify(result)


@app.get('/api/study-tools/saved')
@login_required
def api_saved_study_sets():
    """List only the current account's saved study sets, newest first."""
    user = current_user()
    conn = db()
    try:
        rows = conn.execute(
            'SELECT id,title,created_at FROM saved_study_sets WHERE user_id=? ORDER BY id DESC LIMIT 50',
            (int(user['id']),),
        ).fetchall()
        return jsonify({'study_sets': [dict(row) for row in rows]})
    finally:
        conn.close()


@app.get('/api/study-tools/saved/<int:set_id>')
@login_required
def api_get_saved_study_set(set_id):
    user = current_user()
    conn = db()
    try:
        row = conn.execute(
            'SELECT id,title,result_json,created_at FROM saved_study_sets WHERE id=? AND user_id=?',
            (set_id, int(user['id'])),
        ).fetchone()
        if row is None:
            return jsonify({'error': 'Saved study set not found.'}), 404
        try:
            result = json.loads(row['result_json'])
        except (TypeError, json.JSONDecodeError):
            return jsonify({'error': 'Saved study set data is invalid.'}), 500
        return jsonify({'id': row['id'], 'title': row['title'], 'created_at': row['created_at'], 'result': result})
    finally:
        conn.close()


@app.delete('/api/study-tools/saved/<int:set_id>')
@login_required
def api_delete_saved_study_set(set_id):
    user = current_user()
    conn = db()
    try:
        cursor = conn.execute(
            'DELETE FROM saved_study_sets WHERE id=? AND user_id=?',
            (set_id, int(user['id'])),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({'error': 'Saved study set not found.'}), 404
        return jsonify({'ok': True, 'deleted_id': set_id})
    finally:
        conn.close()


@app.post('/api/ai')
@login_required
def api_ai():
    data=request.get_json(silent=True) or {}
    question=data.get('question','')
    if not isinstance(question,str) or len(question)>2000: abort(400)
    recommendation = _catalog_recommendation(question)
    if recommendation is not None:
        return jsonify(recommendation), 200
    from ai_tutor_provider import answer_question
    result=answer_question(question, int(current_user()['id']))
    return jsonify(result), (503 if result['status']=='provider_unavailable' else 200)
from setup_readiness import setup_readiness_bp
app.register_blueprint(setup_readiness_bp)

@app.get('/api/health')
def health():
    # Liveness only: no claim that payments, AI, licensing or DB are ready.
    return jsonify({'status':'alive','app':'LibraAI','scope':'liveness-only'})

@app.get('/api/ready')
def readiness():
    # Infrastructure readiness only. Commercial launch readiness is checked
    # separately with production_preflight.py (which fails closed).
    try:
        with db() as conn:
            conn.execute('SELECT 1 FROM users LIMIT 1').fetchone()
            conn.execute('SELECT 1 FROM books LIMIT 1').fetchone()
        if _session_backend == 'redis' or _rate_backend == 'redis':
            import redis
            redis.Redis.from_url(_redis_url, socket_connect_timeout=2, socket_timeout=2).ping()
        return jsonify({'status':'ready','scope':'database-and-shared-store' if (_session_backend == 'redis' or _rate_backend == 'redis') else 'database-and-application-only'})
    except Exception:
        return jsonify({'status':'unavailable','scope':'database-or-shared-store'}), 503

from flask import g
from api_resilience import check_rate_limit, client_fingerprint, JsonRequestFormatter

_request_logger = logging.getLogger('libraai.request')
if not _request_logger.handlers:
    _request_handler = logging.StreamHandler()
    _request_handler.setFormatter(JsonRequestFormatter())
    _request_logger.addHandler(_request_handler)
    _request_logger.propagate = False
_request_logger.setLevel(logging.INFO)

@app.before_request
def request_observability_and_rate_limit():
    # Request IDs are generated by the server; client-provided IDs are ignored.
    g.request_id = uuid.uuid4().hex
    g.request_started_at = time.monotonic()
    limited = check_rate_limit(request.path, request.method, request.remote_addr)
    if limited:
        response = jsonify(limited)
        response.status_code = int(limited.get('status', 429))
        if limited.get('retry_after'):
            response.headers['Retry-After'] = str(limited['retry_after'])
        return response

@app.errorhandler(HTTPException)
def consistent_api_http_errors(error):
    # Keep browser-facing HTML errors intact; API callers always receive a
    # predictable JSON envelope while preserving the top-level `error` field.
    if request.path.startswith('/api/'):
        response = jsonify({
            'error': error.description if error.code and error.code < 500 else 'Request could not be completed.',
            'code': f'http_{error.code or 500}',
            'request_id': getattr(g, 'request_id', None),
        })
        response.status_code = error.code or 500
        return response
    return error

@app.errorhandler(Exception)
def consistent_unexpected_api_errors(error):
    # Avoid leaking tracebacks, provider messages, SQL text or user data to API clients.
    if request.path.startswith('/api/'):
        _request_logger.error('api_unhandled_exception', extra={
            'event_name': 'api_unhandled_exception',
            'request_id': getattr(g, 'request_id', None),
            'method': request.method,
            'route': request.url_rule.rule if request.url_rule else 'unmatched',
            'status': 500,
            'duration_ms': round((time.monotonic() - getattr(g, 'request_started_at', time.monotonic())) * 1000, 2),
            'client_fingerprint': client_fingerprint(request.remote_addr),
        })
        return jsonify({'error': 'Request could not be completed.', 'code': 'http_500',
                        'request_id': getattr(g, 'request_id', None)}), 500
    # Keep unexpected HTML failures generic rather than returning exception details.
    return 'Internal Server Error', 500

@app.after_request
def safe_request_telemetry(response):
    request_id = getattr(g, 'request_id', None)
    if request_id:
        response.headers['X-Request-ID'] = request_id
        elapsed_ms = round((time.monotonic() - getattr(g, 'request_started_at', time.monotonic())) * 1000, 2)
        # Do not log query strings, bodies, email, auth cookies, or raw IPs.
        _request_logger.info('request_complete', extra={
            'event_name': 'request_complete', 'request_id': request_id,
            'method': request.method,
            'route': request.url_rule.rule if request.url_rule else 'unmatched',
            'status': response.status_code, 'duration_ms': elapsed_ms,
            'client_fingerprint': client_fingerprint(request.remote_addr),
        })
    return response

@app.before_request
def enforce_authenticated_session_lifetime():
    # Run for every request so inactive sessions expire even on routes that do
    # not call current_user() directly. The cookie is signed; timestamps are
    # therefore server-issued state, not trusted request parameters.
    if session.get('uid'):
        if session_expired(session):
            session.clear()
            return None
        touch_authenticated_session(session)

@app.before_request
def verify_form_csrf():
    if request.method in ('POST','PUT','PATCH','DELETE'):
        if request.endpoint == 'payments.ssl_ipn' or request.endpoint == 'royalties.payout_provider_webhook':
            return None
        token = session.get('_csrf')
        supplied = request.form.get('_csrf') or request.headers.get('X-CSRF-Token')
        if not token or not supplied or not hmac.compare_digest(token,supplied):
            abort(400, 'Invalid CSRF token')

@app.after_request
def security_headers(response):
    if session.get('uid') or request.path.startswith(('/account', '/api/')):
        response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    response.headers['X-Permitted-Cross-Domain-Policies']='none'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
    response.headers['Content-Security-Policy']="frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
    if os.environ.get('LIBRAAI_ENV') == 'production':
        response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
        response.headers['Cross-Origin-Resource-Policy']='same-origin'
    if request.endpoint not in ('manifest','service_worker'):
        response.headers['Cache-Control']='private, no-store'
    return response

from extended import bp as extended_bp, initialize as initialize_extended
from research_tools import bp as research_bp
from learning_engine import bp as learning_bp, initialize as initialize_learning
app.register_blueprint(research_bp)
app.register_blueprint(extended_bp)
app.register_blueprint(learning_bp)

from platform_plus import plus, setup as setup_platform_plus
app.register_blueprint(plus)
@app.route('/assets/premium_ui.css')
def premium_styles():
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), 'premium_ui.css', mimetype='text/css')
from commercial_extensions import commercial, setup as setup_commercial
app.register_blueprint(commercial)
from licensed_library import licensed, setup as setup_licensed
app.register_blueprint(licensed)
from audiobook_library import bp as audiobook_bp, setup as setup_audiobook_library
app.register_blueprint(audiobook_bp)
from reader_engagement import engagement, setup as setup_engagement
app.register_blueprint(engagement)
init_db()
from ecosystem_routes import install_ecosystem, setup_ecosystem
install_ecosystem(app, db, current_user)
setup_ecosystem(db)
setup_engagement()
setup_licensed()
setup_audiobook_library(db)
from digital_entitlements import setup as setup_digital_entitlements
with db() as _entitlements_db:
    setup_digital_entitlements(_entitlements_db)
setup_commercial()
initialize_extended()
initialize_learning()
setup_platform_plus()
from inventory_audit_engine import setup as setup_inventory_audits
from inventory_audit_routes import inventory_audits
app.register_blueprint(inventory_audits)
with db() as _inventory_db:
    setup_inventory_audits(_inventory_db)

from order_lifecycle import setup as setup_order_lifecycle
from order_routes import orders_bp
app.register_blueprint(orders_bp)
with db() as _order_db:
    setup_order_lifecycle(_order_db)

from verified_reading_routes import install as install_verified_reading
install_verified_reading(app, db)

from royalty_routes import install as install_royalty_routes
install_royalty_routes(app, db)

from advanced_reader import reader_plus
app.register_blueprint(reader_plus)

# Additive library waitlist integration (existing routes and UI remain intact).
from waitlist_engine import setup as setup_waitlist
from waitlist_routes import waitlist_bp
app.register_blueprint(waitlist_bp)
with db() as _waitlist_db:
    setup_waitlist(_waitlist_db)

# Read-only liveness and SQLite readiness endpoints for deployment probes.
# Public product website, signup and bundled static assets.
@app.get('/explore')
def explore_public():
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), 'explore.html')

@app.get('/assets/explore.css')
def explore_css():
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), 'explore.css', mimetype='text/css')

@app.get('/assets/explore.js')
def explore_js():
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), 'explore.js', mimetype='application/javascript')

@app.get('/welcome')
def welcome():
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), 'landing_home.html')

@app.get('/assets/landing-home.css')
def landing_home_css():
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), 'landing_home.css', mimetype='text/css')

@app.get('/assets/landing.css')
def landing_css():
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), 'landing.css', mimetype='text/css')

@app.get('/assets/landing.js')
def landing_js():
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), 'landing.js', mimetype='application/javascript')

@app.get('/assets/landing-home.js')
def landing_home_js():
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), 'landing_home.js', mimetype='application/javascript')

@app.get('/assets/hero-library.webp')
def hero_library_asset():
    from flask import send_from_directory
    assets_dir = os.path.join(os.path.dirname(__file__), 'static', 'assets')
    if os.path.exists(os.path.join(assets_dir, 'hero-library.webp')):
        return send_from_directory(assets_dir, 'hero-library.webp', mimetype='image/webp')
    return send_from_directory(os.path.dirname(__file__), 'hero-library.webp', mimetype='image/webp')

@app.get('/assets/hero-reading.webp')
def hero_reading_asset():
    from flask import send_from_directory
    assets_dir = os.path.join(os.path.dirname(__file__), 'static', 'assets')
    if os.path.exists(os.path.join(assets_dir, 'hero-reading.webp')):
        return send_from_directory(assets_dir, 'hero-reading.webp', mimetype='image/webp')
    return send_from_directory(os.path.dirname(__file__), 'hero-reading.webp', mimetype='image/webp')

@app.get('/assets/hero-bookshelf.webp')
def hero_bookshelf_asset():
    from flask import send_from_directory
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'static', 'assets'), 'hero-bookshelf.webp', mimetype='image/webp')

@app.get('/privacy-policy')
def privacy_policy():
    from flask import send_from_directory
    return send_from_directory(os.path.dirname(__file__), 'privacy_policy.html')

# Serve unified static suite & interactive dashboard
@app.get('/static/<path:filename>')
def serve_static_suite(filename):
    from flask import send_from_directory
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    return send_from_directory(static_dir, filename)

# Stable account-page and asset URLs used by older navigation entries and
# direct account links. Keep them mapped to the same authenticated API contract.
@app.get('/account')
@app.get('/account.html')
def account_page_compatibility():
    from flask import send_from_directory
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'static'), 'account.html')

@app.get('/account.js')
def account_js_compatibility():
    from flask import send_from_directory
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'static'), 'account.js', mimetype='application/javascript')

@app.get('/account.css')
def account_css_compatibility():
    from flask import send_from_directory
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'static'), 'account.css', mimetype='text/css')

# Direct shortcuts to merged standalone UI screens
@app.get('/ui/<name>')
def serve_ui_screen(name):
    from flask import send_from_directory
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    filename = name if name.endswith('.html') else f'{name}.html'
    target = os.path.join(static_dir, filename)
    if os.path.isfile(target):
        return send_from_directory(static_dir, filename)
    return ('UI screen not found', 404)

@app.route('/register', methods=['GET','POST'])
@app.route('/signup', methods=['GET','POST'])
def register():
    frontend_json = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if request.method == 'POST':
        from account_registration import PUBLIC_ACCOUNT_TYPES, AccountRegistrationError, create_account
        # Limit abusive signup attempts by source IP without storing the raw address.
        signup_key = identity_key('signup', request.remote_addr or 'unknown', app.secret_key)
        conn = db()
        try:
            if blocked(conn, signup_key):
                if frontend_json: return jsonify({'ok':False,'message':'Too many signup attempts. Please try again later.'}), 429
                abort(429, 'Too many signup attempts. Please try again later.')
            account_type = request.form.get('account_type', 'customer')
            if account_type not in PUBLIC_ACCOUNT_TYPES:
                failed(conn, signup_key)
                if frontend_json: return jsonify({'ok':False,'message':'Choose a customer or seller account.'}), 400
                flash('Choose a customer or seller account.')
            else:
                role, plan = PUBLIC_ACCOUNT_TYPES[account_type]
                try:
                    user_id, password_hash = create_account(
                        conn,
                        request.form.get('name', ''),
                        request.form.get('email', ''),
                        request.form.get('password', ''),
                        role,
                        plan,
                        generate_password_hash,
                        (request.form.get('store_name') or None) if account_type == 'merchant' else None,
                        request.form.get('username') or None,
                    )
                except AccountRegistrationError as exc:
                    failed(conn, signup_key)
                    if frontend_json: return jsonify({'ok':False,'message':str(exc)}), 400
                    flash(str(exc))
                except sqlite3.IntegrityError:
                    failed(conn, signup_key)
                    if frontend_json: return jsonify({'ok':False,'message':'This email is already registered.'}), 409
                    flash('This email is already registered.')
                else:
                    clear(conn, signup_key)
                    session.clear()
                    session['uid'] = user_id
                    session['_credential_fingerprint'] = credential_fingerprint(password_hash)
                    start_authenticated_session(session)
                    # A fresh anti-CSRF token after authentication.
                    session['_csrf'] = secrets.token_urlsafe(32)
                    audit('Created '+account_type+' account')
                    created_user = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
                    if frontend_json: return jsonify({'ok':True,'redirect':_workspace_for_role(created_user)})
                    return redirect(_workspace_for_role(created_user))
        finally:
            conn.close()
    return page('Create account','''<section class="card" style="max-width:520px;margin:35px auto;padding:30px"><span class="pill">Join LibraAI</span><h1>Create your account</h1><p class="muted">Start discovering and organizing your reading journey.</p><form method="post" autocomplete="on"><label for="account_type">Account type</label><select class="input" id="account_type" name="account_type" required><option value="customer">Customer — read, buy and borrow</option><option value="merchant">Merchant — publish and sell books</option></select><label for="name">Your name</label><input class="input" id="name" name="name" autocomplete="name" minlength="2" maxlength="100" required><label for="username">Username <span class="muted">(optional; auto-generated if blank)</span></label><input class="input" id="username" name="username" autocomplete="username" minlength="2" maxlength="32" pattern="[A-Za-z0-9_.-]+"><label for="store_name">Store or publishing name</label><input class="input" id="store_name" name="store_name" autocomplete="organization" minlength="2" maxlength="120"><label for="email">Email address</label><input class="input" id="email" name="email" type="email" autocomplete="email" maxlength="254" required><label for="password">Password (at least 12 characters)</label><input class="input" id="password" name="password" type="password" autocomplete="new-password" minlength="12" maxlength="128" required><button class="btn" type="submit">Create account →</button></form><p class="muted">Administrator accounts are provisioned securely by an existing administrator.</p><p class="muted">Already registered? <a href="/login" style="color:#6953d9">Sign in</a></p></section>''')


@app.route('/admin/users/new', methods=['GET','POST'])
@login_required
def admin_create_user():
    if current_user()['role'] != 'admin':
        abort(403)
    from account_registration import MANAGED_ACCOUNT_TYPES, AccountRegistrationError, create_account
    if request.method == 'POST':
        account_type = request.form.get('account_type', '')
        if account_type not in MANAGED_ACCOUNT_TYPES:
            abort(400, 'Unsupported account type')
        role, plan = MANAGED_ACCOUNT_TYPES[account_type]
        conn = db()
        try:
            user_id, _ = create_account(
                conn,
                request.form.get('name', ''),
                request.form.get('email', ''),
                request.form.get('password', ''),
                role,
                plan,
                generate_password_hash,
                request.form.get('store_name') or None if role == 'creator' else None,
            )
        except AccountRegistrationError as exc:
            flash(str(exc))
        except sqlite3.IntegrityError:
            flash('This email is already registered.')
        else:
            if role == 'librarian':
                branch = (request.form.get('branch') or 'Central').strip()[:80]
                with db() as branch_db:
                    branch_db.execute('INSERT INTO librarian_branches(user_id,branch) VALUES(?,?)',(user_id,branch))
            audit('Created '+account_type+' account #'+str(user_id))
            flash(account_type.capitalize()+' account created successfully.')
            return redirect(url_for('admin_create_user'))
        finally:
            conn.close()
    return page('Create platform account','''<section class="card" style="max-width:560px;margin:35px auto;padding:30px"><h1>Create platform account</h1><p class="muted">Administrators can provision customer, seller or additional administrator accounts. The new user can sign in immediately with the assigned credentials.</p><form method="post" autocomplete="off"><label for="account_type">Account type</label><select class="input" id="account_type" name="account_type" required><option value="customer">Customer</option><option value="seller">Seller</option><option value="librarian">Librarian</option><option value="admin">Administrator</option></select><label for="branch">Librarian branch (only for librarian)</label><input class="input" id="branch" name="branch" value="Central" maxlength="80"><label for="name">Full name</label><input class="input" id="name" name="name" autocomplete="off" minlength="2" maxlength="100" required><label for="email">Email address</label><input class="input" id="email" name="email" type="email" autocomplete="off" maxlength="254" required><label for="password">Temporary password (12–128 characters)</label><input class="input" id="password" name="password" type="password" autocomplete="new-password" minlength="12" maxlength="128" required><button class="btn" type="submit">Create account</button></form><p class="muted">For the first production administrator, initialize the schema and run <code>python bootstrap_admin.py</code> with an absolute LIBRAAI_DB_PATH. Public admin self-signup is intentionally disabled.</p><p><a href="/admin">Back to admin</a></p></section>''')

from account_privacy import account_bp
app.config['LIBRAAI_ACCOUNT_DB'] = DB
app.register_blueprint(account_bp)

from catalog_routes import install_catalog
install_catalog(app, db, current_user)

from operational_health import health_bp
app.config['LIBRAAI_HEALTH_DB'] = DB
app.register_blueprint(health_bp)

from support_routes import install as install_support
install_support(app, db, current_user)


from catalog_editor_routes import install_catalog_editor
install_catalog_editor(app, db, current_user, page)

from payment_routes import payments_bp
from payment_engine import setup as setup_payments
app.register_blueprint(payments_bp)
with db() as _payment_db:
    setup_payments(_payment_db)
    from refund_engine import setup as setup_refunds
    setup_refunds(_payment_db)
from refund_routes import refunds_bp
app.register_blueprint(refunds_bp)


# Admin-only, read-only operational overview.
from operations_routes import operations_bp
app.register_blueprint(operations_bp)

from shipping_routes import shipping_bp
from shipping_engine import setup as setup_shipping
app.register_blueprint(shipping_bp)
with db() as _shipping_db:
    setup_shipping(_shipping_db)


# Entitlement-gated downloads from storage outside the web/static directory.
from secure_ebook_delivery import register as register_ebook_delivery
register_ebook_delivery(app, db)

# Premium UI pages for previously API-only/partial feature groups.
from ui_gap_routes import ui_gap_bp
app.register_blueprint(ui_gap_bp)

from dashboard_workspace import install_dashboard_workspace
install_dashboard_workspace(app, db, current_user)

from seller_workspace import install_seller_workspace
install_seller_workspace(app, db, current_user)

from library_operations import install as install_library_operations
install_library_operations(app, db, current_user)

# Start only after ALL blueprints and schema migrations have been registered.
if __name__=='__main__':
    if os.environ.get('LIBRAAI_ENV') == 'production':
        raise RuntimeError('Use Gunicorn or a production WSGI server, not Flask development server')
    app.run(debug=os.environ.get('LIBRAAI_DEBUG')=='1', host='127.0.0.1', port=5000)

