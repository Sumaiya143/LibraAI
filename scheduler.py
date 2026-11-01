"""Local scheduled reminders. No external payment, email or hardware side effects."""
import datetime, time, threading
from advanced_server import db

def run_due_reminders(today=None):
    today = today or datetime.date.today().isoformat()
    created=0
    with db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS reminder_deliveries (user_id INTEGER NOT NULL,task_id INTEGER NOT NULL,due TEXT NOT NULL,created INTEGER NOT NULL,PRIMARY KEY(user_id,task_id,due))')
        c.execute('BEGIN IMMEDIATE')
        rows=c.execute('SELECT id,user_id,task,due FROM planner WHERE done=0 AND due IS NOT NULL AND substr(due,1,10)<=? LIMIT 500',(today,)).fetchall()
        for r in rows:
            cur=c.execute('INSERT OR IGNORE INTO reminder_deliveries VALUES(?,?,?,?)',(r['user_id'],r['id'],r['due'],int(time.time())))
            if cur.rowcount:
                c.execute('INSERT INTO notification_queue(user_id,body,created) VALUES(?,?,?)',(r['user_id'],'Reading task due: '+r['task'][:160],int(time.time())))
                created+=1
    return created

def start_scheduler(interval=300):
    def loop():
        while True:
            try: run_due_reminders()
            except Exception as exc: print('Scheduler error:',str(exc))
            time.sleep(interval)
    thread=threading.Thread(target=loop,daemon=True,name='libra-reminders')
    thread.start()
    return thread

# Only supported local trigger/action combinations execute automatically.
def run_workflows(today=None):
    today = today or datetime.date.today().isoformat()
    created = 0
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS workflow_deliveries (
            workflow_id INTEGER NOT NULL, task_id INTEGER NOT NULL,
            due TEXT NOT NULL, created INTEGER NOT NULL,
            PRIMARY KEY(workflow_id,task_id,due))''')
        c.execute('BEGIN IMMEDIATE')
        rules=c.execute("SELECT id,user_id,name FROM workflows WHERE enabled=1 AND trigger_name='task_overdue' AND action_name='notify_owner'").fetchall()
        for rule in rules:
            tasks=c.execute('SELECT id,task,due FROM planner WHERE user_id=? AND done=0 AND due IS NOT NULL AND substr(due,1,10)<? LIMIT 500',(rule['user_id'],today)).fetchall()
            for task in tasks:
                inserted=c.execute('INSERT OR IGNORE INTO workflow_deliveries VALUES(?,?,?,?)',(rule['id'],task['id'],task['due'],int(time.time())))
                if inserted.rowcount:
                    message='Overdue reading task: '+task['task'][:160]
                    c.execute('INSERT INTO notification_queue(user_id,body,created) VALUES(?,?,?)',(rule['user_id'],message,int(time.time())))
                    c.execute('INSERT INTO workflow_runs(workflow_id,status,details) VALUES(?,?,?)',(rule['id'],'completed',message))
                    created+=1
    return created

def make_verified_backup(directory=None):
    import sqlite3, pathlib, secrets
    from server import DB
    folder=pathlib.Path(directory) if directory else pathlib.Path(DB).parent/'backups'
    folder.mkdir(parents=True,exist_ok=True)
    dest=folder/('scheduled-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3)+'.sqlite3')
    with sqlite3.connect(DB) as source, sqlite3.connect(dest) as target:
        source.backup(target)
    with sqlite3.connect(dest) as check:
        assert check.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        # Restore drill into a separate temporary database; never overwrite the live database.
        with sqlite3.connect(':memory:') as restored:
            check.backup(restored)
            assert restored.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    return str(dest)

def start_maintenance(interval=300,backup_every=86400):
    def loop():
        last_backup=0
        while True:
            try:
                run_due_reminders()
                run_workflows()
                if time.time()-last_backup>=backup_every:
                    make_verified_backup()
                    last_backup=time.time()
            except Exception as exc:
                print('Maintenance error:',str(exc))
            time.sleep(interval)
    thread=threading.Thread(target=loop,daemon=True,name='libra-maintenance')
    thread.start()
    return thread
