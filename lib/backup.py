import shutil
import subprocess
import zipfile
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

BACKUP_DIR = Path(__file__).parent.parent / "data_backups"
DATA_DIR = Path(__file__).parent.parent / "data"
MAX_BACKUPS = 5
PG_DUMP = r"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe"
PSQL = r"C:\Program Files\PostgreSQL\16\bin\psql.exe"
DB_NAME = "astrolabe"
DB_USER = "postgres"
DB_PASSWORD = "postgres"
DB_HOST = "localhost"
DB_PORT = "5432"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pg_env() -> dict:
    """Return env dict with PGPASSWORD set so pg_dump/psql don't prompt."""
    import os
    env = os.environ.copy()
    env["PGPASSWORD"] = DB_PASSWORD
    return env


# ---------------------------------------------------------------------------
# Create / Restore
# ---------------------------------------------------------------------------

def create_backup(include_logs: bool = False) -> Dict[str, any]:
    """
    Create timestamped backup of PostgreSQL database + config files.
    Stores everything in a single zip under data_backups/.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = f"backup_{timestamp}"
    zip_path = BACKUP_DIR / f"{backup_name}.zip"

    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        # --- 1. pg_dump --------------------------------------------------
        dump_path = BACKUP_DIR / f"{backup_name}.sql"
        result = subprocess.run(
            [
                PG_DUMP,
                "-h", DB_HOST,
                "-p", DB_PORT,
                "-U", DB_USER,
                "-d", DB_NAME,
                "--no-owner",
                "--no-acl",
                "-f", str(dump_path),
            ],
            env=_pg_env(),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"pg_dump failed: {result.stderr}")

        # --- 2. Collect config files that still live on disk -------------
        extra_files = [
            "settings.json",
            "ingest_state.json",
            "pipeline_state.json",
        ]
        if include_logs:
            extra_files.extend(["ingest.log", "pipeline.log"])

        # --- 3. Build zip ------------------------------------------------
        file_count = 0
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # SQL dump
            zipf.write(dump_path, "database.sql")
            file_count += 1

            for fname in extra_files:
                fpath = DATA_DIR / fname
                if fpath.exists():
                    zipf.write(fpath, fname)
                    file_count += 1

        # Clean up loose SQL dump
        dump_path.unlink(missing_ok=True)

        backup_size_mb = zip_path.stat().st_size / (1024 * 1024)

        rotate_old_backups()

        return {
            "success": True,
            "backup_path": str(zip_path),
            "timestamp": timestamp,
            "size_mb": round(backup_size_mb, 2),
            "file_count": file_count,
        }

    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return {"success": False, "error": str(e)}


def rotate_old_backups():
    """Keep only the last MAX_BACKUPS backups, delete older ones."""
    if not BACKUP_DIR.exists():
        return

    backups = sorted(BACKUP_DIR.glob("backup_*.zip"), key=lambda p: p.stat().st_mtime)

    if len(backups) > MAX_BACKUPS:
        for old_backup in backups[:-MAX_BACKUPS]:
            try:
                old_backup.unlink()
                logger.info(f"Deleted old backup: {old_backup.name}")
            except Exception as e:
                logger.warning(f"Failed to delete old backup {old_backup.name}: {e}")


def list_backups() -> List[Dict[str, any]]:
    """List all available backups with metadata."""
    if not BACKUP_DIR.exists():
        return []

    backups = []
    for backup_zip in sorted(BACKUP_DIR.glob("backup_*.zip"), reverse=True):
        try:
            info = get_backup_info(backup_zip)
            backups.append(info)
        except Exception as e:
            logger.warning(f"Failed to read backup {backup_zip.name}: {e}")

    return backups


def get_backup_info(zip_path: Path) -> Dict[str, any]:
    """Get metadata about a backup file."""
    stat = zip_path.stat()
    name = zip_path.stem
    timestamp_str = name.replace("backup_", "")

    file_count = 0
    has_database_sql = False
    try:
        with zipfile.ZipFile(zip_path, "r") as zipf:
            names = zipf.namelist()
            file_count = len(names)
            has_database_sql = "database.sql" in names
    except Exception:
        pass

    return {
        "name": zip_path.name,
        "path": str(zip_path),
        "timestamp": timestamp_str,
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
        "file_count": file_count,
        "has_pg_dump": has_database_sql,
        "created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    }


def validate_backup(zip_path: Path) -> bool:
    """Validate backup zip integrity — must contain database.sql."""
    try:
        if not zip_path.exists() or not zipfile.is_zipfile(zip_path):
            return False

        with zipfile.ZipFile(zip_path, "r") as zipf:
            if "database.sql" not in zipf.namelist():
                logger.error("Backup missing database.sql")
                return False

        return True
    except Exception as e:
        logger.error(f"Backup validation failed: {e}")
        return False


def restore_backup(
    zip_path: Path, create_safety_backup: bool = True
) -> Dict[str, any]:
    """
    Restore PostgreSQL database and config files from backup zip.
    """
    try:
        if not validate_backup(zip_path):
            return {"success": False, "error": "Invalid backup file"}

        # Safety backup of current state
        if create_safety_backup:
            safety = create_backup(include_logs=False)
            if safety["success"]:
                logger.info(f"Safety backup: {safety['backup_path']}")

        # Extract zip to a temp dir
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(zip_path, "r") as zipf:
                zipf.extractall(tmpdir)

            # Restore database via psql
            dump_file = Path(tmpdir) / "database.sql"
            if dump_file.exists():
                result = subprocess.run(
                    [
                        PSQL,
                        "-h", DB_HOST,
                        "-p", DB_PORT,
                        "-U", DB_USER,
                        "-d", DB_NAME,
                        "-f", str(dump_file),
                    ],
                    env=_pg_env(),
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode != 0:
                    raise RuntimeError(f"psql restore failed: {result.stderr}")

            # Restore config files
            for fname in ("settings.json", "ingest_state.json", "pipeline_state.json"):
                src = Path(tmpdir) / fname
                if src.exists():
                    shutil.copy2(src, DATA_DIR / fname)

        return {
            "success": True,
            "message": f"Successfully restored from {zip_path.name}",
        }

    except Exception as e:
        logger.error(f"Restore failed: {e}")
        return {"success": False, "error": str(e)}
