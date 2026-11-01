"""Consistent SQLite online backup; run with LIBRAAI_DB_PATH configured."""
import os, sqlite3, sys
from pathlib import Path
from datetime import datetime, timezone
source=Path(os.environ.get('LIBRAAI_DB_PATH',Path(__file__).with_name('libraai.db')))
if not source.exists():
    raise SystemExit('Database not found: '+str(source))
out=Path(sys.argv[1]) if len(sys.argv)>1 else Path('backups')/(datetime.now(timezone.utc).strftime('libraai-%Y%m%d-%H%M%S.db'))
out.parent.mkdir(parents=True,exist_ok=True)
if out.resolve()==source.resolve():
    raise SystemExit('Backup target must differ from source')
with sqlite3.connect(f'file:{source}?mode=ro',uri=True) as src, sqlite3.connect(out) as dst:
    src.backup(dst)
    assert dst.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
print(out)
