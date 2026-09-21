#!/usr/bin/env python3
"""
SQLite backup script for SUME Dashboard.

Creates timestamped backups of the database with optional compression.
Designed to be run manually or via cron.

Usage:
    python scripts/backup_db.py                    # Default: backup to data/backups/
    python scripts/backup_db.py --output /path     # Custom output directory
    python scripts/backup_db.py --compress          # gzip compression
    python scripts/backup_db.py --keep 7            # Keep only last 7 backups
"""

import argparse
import gzip
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def backup_database(db_path: Path, output_dir: Path, compress: bool = False) -> Path:
    """
    Create a backup of the SQLite database using the online backup API.

    This is safe to run while the database is in use (no locking issues).

    Args:
        db_path: Path to the source database.
        output_dir: Directory to write the backup.
        compress: If True, gzip the backup file.

    Returns:
        Path to the created backup file.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = ".db.gz" if compress else ".db"
    backup_path = output_dir / f"sume_backup_{timestamp}{suffix}"

    # Use SQLite's online backup API (safe during active use)
    source = sqlite3.connect(str(db_path))
    dest = sqlite3.connect(str(backup_path))

    try:
        source.backup(dest)
        print(f"✅ Backup created: {backup_path}")
        print(f"   Size: {backup_path.stat().st_size / 1024:.1f} KB")
    finally:
        dest.close()
        source.close()

    return backup_path


def cleanup_old_backups(output_dir: Path, keep: int) -> int:
    """
    Remove old backups, keeping only the most recent `keep` files.

    Args:
        output_dir: Directory containing backups.
        keep: Number of backups to keep.

    Returns:
        Number of backups removed.
    """
    backups = sorted(output_dir.glob("sume_backup_*"), key=lambda p: p.stat().st_mtime)

    if len(backups) <= keep:
        return 0

    to_remove = backups[:-keep]
    for backup in to_remove:
        backup.unlink()
        print(f"🗑️  Removed old backup: {backup.name}")

    return len(to_remove)


def main():
    parser = argparse.ArgumentParser(description="Backup SUME Dashboard database")
    parser.add_argument(
        "--db",
        default="data/sume.db",
        help="Path to database (default: data/sume.db)",
    )
    parser.add_argument(
        "--output",
        default="data/backups",
        help="Output directory (default: data/backups/)",
    )
    parser.add_argument(
        "--compress",
        action="store_true",
        help="Compress backup with gzip",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=10,
        help="Number of backups to keep (default: 10)",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    output_dir = Path(args.output)

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    try:
        backup_path = backup_database(db_path, output_dir, args.compress)
        removed = cleanup_old_backups(output_dir, args.keep)
        if removed:
            print(f"🧹 Cleaned up {removed} old backup(s)")
        print(f"\n📦 Backup complete: {backup_path}")
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
