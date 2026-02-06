import shutil
import zipfile
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

BACKUP_DIR = Path(__file__).parent.parent / "data_backups"
DATA_DIR = Path(__file__).parent.parent / "data"
MAX_BACKUPS = 5

logger = logging.getLogger(__name__)


def create_backup(include_logs: bool = False) -> Dict[str, any]:
    """
    Create timestamped backup of entire data/ directory.

    Args:
        include_logs: Include log files in backup (default False)

    Returns:
        Dict with backup_path, timestamp, size, file_count, success status
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = f"backup_{timestamp}"
    backup_path = BACKUP_DIR / backup_name
    zip_path = BACKUP_DIR / f"{backup_name}.zip"

    try:
        # Create backup directory
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        # Files to backup
        files_to_backup = [
            "chroma_db",
            "metadata.json",
            "query_history.db",
            "read_status.db",
            "collections.db",
            "ingest_state.json",
            "pipeline_state.json",
            "settings.json"
        ]

        if include_logs:
            files_to_backup.extend(["ingest.log", "pipeline.log"])

        # Create zip file
        file_count = 0
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for item_name in files_to_backup:
                item_path = DATA_DIR / item_name
                if item_path.exists():
                    if item_path.is_dir():
                        # Add directory recursively
                        for file in item_path.rglob('*'):
                            if file.is_file():
                                arcname = str(file.relative_to(DATA_DIR))
                                zipf.write(file, arcname)
                                file_count += 1
                    else:
                        # Add single file
                        zipf.write(item_path, item_name)
                        file_count += 1

        # Get backup size
        backup_size_mb = zip_path.stat().st_size / (1024 * 1024)

        # Rotate old backups (keep last 5)
        rotate_old_backups()

        return {
            'success': True,
            'backup_path': str(zip_path),
            'timestamp': timestamp,
            'size_mb': round(backup_size_mb, 2),
            'file_count': file_count
        }

    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def rotate_old_backups():
    """Keep only the last MAX_BACKUPS backups, delete older ones."""
    if not BACKUP_DIR.exists():
        return

    # Get all backup zip files
    backups = sorted(BACKUP_DIR.glob("backup_*.zip"), key=lambda p: p.stat().st_mtime)

    # Delete oldest backups if we have more than MAX_BACKUPS
    if len(backups) > MAX_BACKUPS:
        for old_backup in backups[:-MAX_BACKUPS]:
            try:
                old_backup.unlink()
                logger.info(f"Deleted old backup: {old_backup.name}")
            except Exception as e:
                logger.warning(f"Failed to delete old backup {old_backup.name}: {e}")


def list_backups() -> List[Dict[str, any]]:
    """
    List all available backups with metadata.

    Returns:
        List of dicts with name, timestamp, size, file_count
    """
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

    # Extract timestamp from filename (backup_2026-02-04_14-30-15.zip)
    name = zip_path.stem
    timestamp_str = name.replace("backup_", "")

    # Count files in zip
    file_count = 0
    try:
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            file_count = len(zipf.namelist())
    except:
        pass

    return {
        'name': zip_path.name,
        'path': str(zip_path),
        'timestamp': timestamp_str,
        'size_mb': round(stat.st_size / (1024 * 1024), 2),
        'file_count': file_count,
        'created': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    }


def validate_backup(zip_path: Path) -> bool:
    """
    Validate backup zip integrity and required files.

    Returns:
        True if backup is valid
    """
    try:
        if not zip_path.exists():
            return False

        # Check if it's a valid zip
        if not zipfile.is_zipfile(zip_path):
            return False

        # Check for required files
        required_files = ["chroma_db", "metadata.json"]

        with zipfile.ZipFile(zip_path, 'r') as zipf:
            filenames = zipf.namelist()

            # Check if required files/directories are present
            for required in required_files:
                if not any(f.startswith(required) for f in filenames):
                    logger.error(f"Backup missing required file/dir: {required}")
                    return False

        return True

    except Exception as e:
        logger.error(f"Backup validation failed: {e}")
        return False


def restore_backup(zip_path: Path, create_safety_backup: bool = True) -> Dict[str, any]:
    """
    Restore database from backup zip.

    Args:
        zip_path: Path to backup zip file
        create_safety_backup: Create backup of current data before restoring

    Returns:
        Dict with success status and message
    """
    try:
        # Validate backup
        if not validate_backup(zip_path):
            return {
                'success': False,
                'error': "Invalid backup file"
            }

        # Create safety backup of current data
        if create_safety_backup and DATA_DIR.exists():
            safety_result = create_backup(include_logs=False)
            if safety_result['success']:
                logger.info(f"Created safety backup before restore: {safety_result['backup_path']}")

        # Clear current data directory (except backups)
        if DATA_DIR.exists():
            for item in DATA_DIR.iterdir():
                if item.name == "data_backups":
                    continue  # Don't delete backups folder
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete {item}: {e}")

        # Extract backup
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(DATA_DIR)

        # Clear ChromaDB cache to force reload
        try:
            from lib.rag import DatabaseClient
            DatabaseClient.clear_cache()
        except Exception as e:
            logger.warning(f"Failed to clear database cache: {e}")

        return {
            'success': True,
            'message': f"Successfully restored from {zip_path.name}"
        }

    except Exception as e:
        logger.error(f"Restore failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }
