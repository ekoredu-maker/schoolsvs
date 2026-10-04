from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

import storage  # noqa: E402


class SafeStateSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.old_db = storage.DB_PATH
        self.old_backup = storage.BACKUP_DIR
        storage.DB_PATH = self.root / "schoolsvs.db"
        storage.BACKUP_DIR = self.root / "backups"
        storage.init_db()
        storage.upsert_case({"id":"a","caseNo":"2026-A","status":"접수중"})
        storage.upsert_case({"id":"b","caseNo":"2026-B","status":"조사중"})
        storage.set_value("counter", 3)
        storage.set_value("settings", {"school":"테스트초"})

    def tearDown(self):
        storage.DB_PATH = self.old_db
        storage.BACKUP_DIR = self.old_backup
        self.tmp.cleanup()

    def test_merge_subset_never_deletes_server_only_case(self):
        result = storage.sync_state(
            [{"id":"a","caseNo":"2026-A","status":"조사중"}],
            4,
            {"school":"테스트초"},
            mode="merge",
        )
        self.assertEqual(result["removed"], 0)
        self.assertIsNotNone(storage.get_case("a"))
        self.assertIsNotNone(storage.get_case("b"))
        self.assertEqual(storage.get_case("a")["status"], "조사중")

    def test_reconcile_deletes_absent_case_only_after_backup(self):
        result = storage.sync_state(
            [{"id":"a","caseNo":"2026-A","status":"접수중"}],
            3,
            {"school":"테스트초"},
            mode="reconcile",
        )
        self.assertEqual(result["removed"], 1)
        self.assertEqual(result["removedIds"], ["b"])
        self.assertIsNotNone(result["backup"])
        self.assertIsNone(storage.get_case("b"))
        backup_path = storage.BACKUP_DIR / result["backup"]
        self.assertTrue(backup_path.exists())
        payload = json.loads(backup_path.read_text(encoding="utf-8"))
        ids = {x["id"] for x in payload["cases"]}
        self.assertEqual(ids, {"a", "b"})

    def test_empty_reconcile_is_blocked_when_database_has_cases(self):
        with self.assertRaisesRegex(ValueError, "전체 사안을 삭제"):
            storage.sync_state([], 1, {}, mode="reconcile")
        self.assertIsNotNone(storage.get_case("a"))
        self.assertIsNotNone(storage.get_case("b"))

    def test_empty_merge_does_not_delete_anything(self):
        result = storage.sync_state([], 1, {}, mode="merge")
        self.assertEqual(result["removed"], 0)
        self.assertEqual({x["id"] for x in storage.list_cases()}, {"a", "b"})

    def test_explicit_empty_reconcile_can_be_used_only_when_allowed(self):
        result = storage.sync_state([], 1, {}, mode="reconcile", allow_empty_reconcile=True)
        self.assertEqual(result["removed"], 2)
        self.assertEqual(storage.list_cases(), [])
        self.assertTrue((storage.BACKUP_DIR / result["backup"]).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
