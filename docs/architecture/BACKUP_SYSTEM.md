# Backup and Restore System

## Overview
A comprehensive backup and restore system for the Astrolabe Paper Database with automatic rotation, validation, and one-click UI controls.

## Features

### ✓ One-Click Backup from UI
- Create backups directly from the sidebar
- Download backups to local machine
- View backup size and file count

### ✓ Auto-Backup After Ingestion
- Automatically creates backup after successful paper ingestion
- Triggered by both `ingest.py` and `ingest_pipeline.py --all`
- Includes log files in auto-backups

### ✓ Automatic Rotation
- Keeps last 5 backups automatically
- Older backups deleted when limit exceeded
- Saves disk space while maintaining safety net

### ✓ Restore with Validation
- Validates backup integrity before restore
- Creates safety backup before restore (can undo restore)
- Two-click confirmation to prevent accidents
- Clears ChromaDB cache after restore

## Usage

### UI Backup & Restore

1. **Create Backup**:
   - Open the app: `streamlit run app.py`
   - Go to sidebar → "Backup & Restore" section
   - Click "📦 Create Backup"
   - Optionally download the backup with "💾 Download Backup"

2. **Restore from Backup**:
   - Select a backup from the dropdown
   - Click "♻️ Restore"
   - Click again to confirm (safety confirmation)
   - Refresh page to see restored data

### Programmatic Backup

```python
from lib import backup

# Create backup
result = backup.create_backup(include_logs=False)
if result['success']:
    print(f"Backup created: {result['backup_path']}")
    print(f"Size: {result['size_mb']} MB")
    print(f"Files: {result['file_count']}")

# List backups
backups = backup.list_backups()
for b in backups:
    print(f"{b['name']}: {b['size_mb']} MB")

# Restore backup
from pathlib import Path
result = backup.restore_backup(Path("data_backups/backup_2026-02-04_20-49-02.zip"))
if result['success']:
    print(result['message'])
```

### Auto-Backup During Ingestion

Backups are automatically created after:
- `python scripts/ingest.py` (successful ingestion)
- `python scripts/ingest_pipeline.py --all` (full pipeline completion)

## What Gets Backed Up

All files in the `data/` directory:
- `chroma_db/` - Vector database (most critical)
- `metadata.json` - Paper metadata
- `query_history.db` - Search history
- `read_status.db` - Read/unread tracking
- `ingest_state.json` - Resume state
- `pipeline_state.json` - Pipeline state
- `settings.json` - User preferences
- Log files (when `include_logs=True`)

## Backup Location

Backups stored in: `data_backups/`

Format: `backup_YYYY-MM-DD_HH-MM-SS.zip`

## Technical Details

### Backup Module (`lib/backup.py`)

Core functions:
- `create_backup(include_logs=False)` - Create timestamped backup
- `list_backups()` - List available backups with metadata
- `validate_backup(zip_path)` - Validate backup integrity
- `restore_backup(zip_path, create_safety_backup=True)` - Restore from backup
- `rotate_old_backups()` - Delete backups older than MAX_BACKUPS (5)

### Safety Features

1. **Validation**: Checks zip integrity and required files
2. **Safety Backup**: Creates backup before restore (can undo)
3. **Confirmation**: UI requires two clicks to restore
4. **Cache Clear**: Clears ChromaDB cache after restore
5. **Rotation**: Prevents disk space issues

### Error Handling

- Graceful failures with error messages
- Non-blocking (ingestion continues if backup fails)
- Detailed logging for troubleshooting

## Testing

### Test Backup Creation
```bash
python -c "from lib import backup; result = backup.create_backup(); print(result)"
```

### Test Rotation
```bash
# Create 6 backups, verify only 5 remain
python -c "from lib import backup; import time; [backup.create_backup() or time.sleep(1) for _ in range(6)]"
ls data_backups/  # Should show 5 backups
```

### Test Validation
```bash
python -c "from lib import backup; from pathlib import Path; backups = backup.list_backups(); print(backup.validate_backup(Path(backups[0]['path'])))"
```

## Configuration

Edit `lib/backup.py` to change:
- `MAX_BACKUPS = 5` - Number of backups to keep
- `BACKUP_DIR` - Backup directory location

## Exclusions

The `data_backups/` directory is excluded from git via `.gitignore`.
