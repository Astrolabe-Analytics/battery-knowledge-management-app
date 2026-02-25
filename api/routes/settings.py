"""
Settings API routes — app configuration, backups, theme.

Wraps: lib/app_helpers.py (load/save_settings), lib/backup.py
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path

router = APIRouter()


class SettingsUpdate(BaseModel):
    theme: Optional[str] = None
    skip_delete_confirmation: Optional[bool] = None
    semantic_scholar_api_key: Optional[str] = None


@router.get("")
def get_settings():
    """Get all application settings."""
    from lib.settings_helpers import load_settings
    return load_settings()


@router.patch("")
def update_settings(body: SettingsUpdate):
    """Update application settings (partial update)."""
    from lib.settings_helpers import load_settings, save_settings

    current = load_settings()
    updates = body.model_dump(exclude_none=True)
    current.update(updates)
    save_settings(current)
    return {"success": True, "settings": current}


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------

@router.get("/backups")
def list_backups():
    """List all available backups."""
    from lib.backup import list_backups
    backups = list_backups()
    return {"backups": backups}


@router.post("/backups")
def create_backup():
    """Create a new backup of all data."""
    from lib.backup import create_backup, rotate_old_backups
    result = create_backup()
    rotate_old_backups()
    return result


@router.get("/backups/{backup_filename}/download")
def download_backup(backup_filename: str):
    """Download a backup zip file."""
    backup_path = Path("data_backups") / backup_filename
    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup not found")
    return FileResponse(
        backup_path,
        media_type="application/zip",
        filename=backup_filename,
    )


@router.post("/backups/{backup_filename}/restore")
def restore_backup(backup_filename: str):
    """Restore from a backup zip file."""
    from lib.backup import restore_backup, validate_backup

    backup_path = Path("data_backups") / backup_filename
    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup not found")

    if not validate_backup(backup_path):
        raise HTTPException(status_code=400, detail="Backup file is invalid or corrupt")

    result = restore_backup(backup_path)
    return result
