"""Conservative SQLite indexes for high-frequency reader and commerce queries."""
INDEXES = (
    'CREATE INDEX IF NOT EXISTS idx_progress_user_updated ON progress(user_id, updated DESC)',
    'CREATE INDEX IF NOT EXISTS idx_annotations_user_book_created ON annotations(user_id, book_id, created DESC)',
    'CREATE INDEX IF NOT EXISTS idx_reviews_book_created ON reviews(book_id, created DESC)',
    'CREATE INDEX IF NOT EXISTS idx_wishlist_user ON wishlist(user_id, book_id)',
    'CREATE INDEX IF NOT EXISTS idx_cart_user ON cart(user_id, book_id)',
    'CREATE INDEX IF NOT EXISTS idx_orders_user_created ON orders(user_id, created DESC)',
    'CREATE INDEX IF NOT EXISTS idx_orders_status_created ON orders(status, created DESC)',
    'CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created DESC)',
    'CREATE INDEX IF NOT EXISTS idx_flashcards_user_due ON flashcards(user_id, due)',
    'CREATE INDEX IF NOT EXISTS idx_loans_user_status_due ON loans(user_id, status, due)',
    'CREATE INDEX IF NOT EXISTS idx_books_genre_reads ON books(genre, reads DESC)',
    'CREATE INDEX IF NOT EXISTS idx_books_sales_year ON books(sales DESC, year DESC)',
)


def create_indexes(connection):
    """Create indexes after the application's base tables exist; safe to rerun."""
    for statement in INDEXES:
        connection.execute(statement)
    connection.commit()
    return len(INDEXES)
