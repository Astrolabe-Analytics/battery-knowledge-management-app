"""
Tests for the Settings API routes (api/routes/settings.py).

Covers: get/patch settings, backup list/create/download/restore.
"""

from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest


class TestGetSettings:

    @patch("lib.settings_helpers.load_settings")
    def test_get_settings(self, mock_fn, client):
        mock_fn.return_value = {"theme": "dark", "skip_delete_confirmation": False}
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["theme"] == "dark"


class TestUpdateSettings:

    @patch("lib.settings_helpers.save_settings")
    @patch("lib.settings_helpers.load_settings")
    def test_update_settings(self, mock_load, mock_save, client):
        mock_load.return_value = {"theme": "light", "skip_delete_confirmation": False}
        resp = client.patch("/api/settings", json={"theme": "dark"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["settings"]["theme"] == "dark"
        mock_save.assert_called_once()


class TestListBackups:

    @patch("lib.backup.list_backups")
    def test_list_backups(self, mock_fn, client):
        mock_fn.return_value = [
            {"filename": "backup_2024-01-01.zip", "size": 1024},
        ]
        resp = client.get("/api/settings/backups")
        assert resp.status_code == 200
        assert len(resp.json()["backups"]) == 1


class TestCreateBackup:

    @patch("lib.backup.rotate_old_backups")
    @patch("lib.backup.create_backup")
    def test_create_backup(self, mock_create, mock_rotate, client):
        mock_create.return_value = {"success": True, "filename": "backup_new.zip"}
        resp = client.post("/api/settings/backups")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mock_rotate.assert_called_once()


class TestDownloadBackup:

    def test_download_not_found(self, client):
        with patch("api.routes.settings.Path") as MockPath:
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            MockPath.return_value.__truediv__ = MagicMock(return_value=mock_path)
            # The route uses Path("data_backups") / filename
            resp = client.get("/api/settings/backups/missing.zip/download")
            assert resp.status_code == 404


class TestRestoreBackup:

    def test_restore_not_found(self, client):
        resp = client.post("/api/settings/backups/missing.zip/restore")
        assert resp.status_code == 404
