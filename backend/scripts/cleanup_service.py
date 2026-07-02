"""Automated cleanup service. Removes temp/old files safely."""
import os, sys, time, shutil, glob
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

REPORT_DIR = os.path.join(os.path.dirname(__file__), '..', 'reports')
CHARTS_DIR = os.path.join(REPORT_DIR, 'charts')
BACKEND_DIR = os.path.join(os.path.dirname(__file__), '..')
PROTECTED_DIRS = [
    os.path.join(BACKEND_DIR, 'app'),
    os.path.join(BACKEND_DIR, 'scripts'),
    os.path.join(BACKEND_DIR, 'alembic'),
]
PROTECTED_FILES = [
    'requirements.txt', 'main.py', 'docker-compose.yml',
]

SAFE_PATTERNS = [
    ('__pycache__', 'dir'),
    ('*.pyc', 'file'),
    ('*.pyo', 'file'),
    ('*.tmp', 'file'),
    ('*.temp', 'file'),
    ('*.bak', 'file'),
    ('*.backup', 'file'),
    ('*.swp', 'file'),
    ('.DS_Store', 'file'),
    ('.coverage', 'file'),
    ('*.egg-info', 'dir'),
    ('.pytest_cache', 'dir'),
]

STALE_DIRS = [
    'exports',
    'docs',
]

STALE_FILE_PATTERNS = ['*.csv', '*.xlsx', '*.log', '*.dump', '*.sql']
STALE_DAYS = 7


def _is_protected(path):
    abs_path = os.path.abspath(path)
    for d in PROTECTED_DIRS:
        if abs_path.startswith(os.path.abspath(d)):
            return True
    for f in PROTECTED_FILES:
        if abs_path.endswith(f):
            return True
    return False


def _find_and_remove(pattern, search_type, dry_run=True):
    removed = []
    skipped = []
    items = []
    if search_type == 'dir':
        for root, dirs, _ in os.walk(BACKEND_DIR):
            for d in dirs:
                if glob.fnmatch.fnmatch(d, pattern):
                    full = os.path.join(root, d)
                    if _is_protected(full):
                        skipped.append(full)
                    else:
                        items.append(full)
    else:
        for root, _, files in os.walk(BACKEND_DIR):
            for f in files:
                if glob.fnmatch.fnmatch(f, pattern):
                    full = os.path.join(root, f)
                    if _is_protected(full):
                        skipped.append(full)
                    else:
                        items.append(full)
    for item in items:
        try:
            if dry_run:
                removed.append(item)
            else:
                if os.path.isdir(item):
                    shutil.rmtree(item)
                else:
                    os.remove(item)
                removed.append(item)
        except Exception as e:
            print(f"  FAIL: {item}: {e}")
    return removed, skipped


def _clean_stale_files(dry_run=True):
    cutoff = datetime.now() - timedelta(days=STALE_DAYS)
    removed = []
    for root, _, files in os.walk(BACKEND_DIR):
        for f in files:
            full = os.path.join(root, f)
            if _is_protected(full):
                continue
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(full))
                if mtime < cutoff:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in ['.csv', '.xlsx', '.log', '.dump', '.sql']:
                        if dry_run:
                            removed.append(full)
                        else:
                            os.remove(full)
                            removed.append(full)
            except Exception:
                pass
    return removed


def run_cleanup(dry_run=True):
    print(f"AlphaHunter Cleanup Service ({'DRY RUN' if dry_run else 'LIVE'})")
    print("=" * 60)

    total_removed = 0
    total_skipped = 0

    print(f"\nCleaning safe patterns...")
    for pattern, stype in SAFE_PATTERNS:
        removed, skipped = _find_and_remove(pattern, stype, dry_run)
        if removed:
            print(f"  {pattern}: {len(removed)} removed")
        total_removed += len(removed)
        total_skipped += len(skipped)

    print(f"\nCleaning stale files (> {STALE_DAYS} days)...")
    stale = _clean_stale_files(dry_run)
    print(f"  {len(stale)} stale files")
    total_removed += len(stale)

    print(f"\nCleaning stale reports...")
    if os.path.exists(CHARTS_DIR):
        for f in os.listdir(CHARTS_DIR):
            full = os.path.join(CHARTS_DIR, f)
            if dry_run:
                total_removed += 1
            else:
                os.remove(full)
                total_removed += 1
        if dry_run:
            print(f"  {len(os.listdir(CHARTS_DIR))} chart files")
        else:
            print(f"  Charts cleaned" if os.path.exists(CHARTS_DIR) else "  No charts dir")

    print(f"\n{'='*60}")
    print(f"Results: {total_removed} items {'to remove' if dry_run else 'removed'}")
    print(f"         {total_skipped} protected items skipped")
    if dry_run:
        print(f"Run with argument --execute to perform actual cleanup")
    else:
        print(f"Cleanup complete")
    return total_removed


if __name__ == "__main__":
    dry_run = "--execute" not in sys.argv
    run_cleanup(dry_run=dry_run)
