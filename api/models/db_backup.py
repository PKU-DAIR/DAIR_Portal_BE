import datetime
import shutil
import sqlite3
from pathlib import Path


DB_DIR = Path('./db')
DB_PATH = DB_DIR / 'db.sqlite3'
BACKUP_DIR = Path('./backup')
BACKUP_INTERVAL_DAYS = 30


def _backup_date_from_name(name: str):
    if not name.startswith('db_'):
        return None
    try:
        return datetime.datetime.strptime(name, 'db_%Y_%m_%d').date()
    except ValueError:
        return None


def _latest_backup_date():
    if not BACKUP_DIR.exists():
        return None
    backup_dates = [
        backup_date
        for child in BACKUP_DIR.iterdir()
        if child.is_dir()
        for backup_date in [_backup_date_from_name(child.name)]
        if backup_date is not None
    ]
    return max(backup_dates) if backup_dates else None


def _copy_sqlite_db(source_path: Path, target_path: Path):
    if not source_path.exists():
        return
    with sqlite3.connect(source_path) as source_db:
        with sqlite3.connect(target_path) as target_db:
            source_db.backup(target_db)


def create_monthly_db_backup():
    today = datetime.date.today()
    latest_backup = _latest_backup_date()
    if latest_backup is not None and (today - latest_backup).days < BACKUP_INTERVAL_DAYS:
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target_dir = BACKUP_DIR / f'db_{today:%Y_%m_%d}'
    if target_dir.exists():
        return target_dir

    tmp_dir = BACKUP_DIR / f'.{target_dir.name}.tmp'
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)

    for item in DB_DIR.iterdir():
        if item.name == DB_PATH.name or item.name.startswith(f'{DB_PATH.name}-'):
            continue
        target = tmp_dir / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)

    _copy_sqlite_db(DB_PATH, tmp_dir / DB_PATH.name)
    tmp_dir.rename(target_dir)
    print(f'Database backup created: {target_dir}')
    return target_dir
