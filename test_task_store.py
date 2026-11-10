"""Regression checks for the data paths that must never lose a task."""
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from task_store import StoreError, Task, TaskStore, atomic_json, next_due, parse_tasks, vocative_name


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.store = TaskStore(self.directory)

    def test_legacy_data_keeps_name_fields_and_completed_history(self):
        raw = [{"id": "old", "text": "zdar", "completed": True, "created_at": "2026-11-06", "completed_at": "2026-11-06T12:10:40", "priority": "Vysoká 🔴", "future_field": "keep"}]
        atomic_json(self.directory / "tasks.json", raw)
        atomic_json(self.directory / "settings.json", {"name": "Štěpán", "other": 7})
        store = TaskStore(self.directory)
        store.add("New task")
        store.save_settings(theme="dark")
        reloaded = TaskStore(self.directory)
        old = reloaded.find("old")
        self.assertTrue(old.completed)
        self.assertEqual(old.completed_at, raw[0]["completed_at"])
        self.assertEqual(old.priority, "high")
        self.assertEqual(old.extra["future_field"], "keep")
        self.assertEqual(reloaded.settings, {"name": "Štěpán", "other": 7, "theme": "dark"})
        self.assertEqual(vocative_name("Marek"), "Marku")

    def test_add_edit_delete_and_undo_survive_reload(self):
        task = self.store.add("Plan", notes="Draft", subtasks=[{"text": "First step"}])
        self.store.update(task.id, text="Updated", due_date="2026-11-11", due_time="9:05")
        self.assertEqual(self.store.find(task.id).due_time, "09:05")
        self.store.delete(task.id)
        self.assertIsNone(self.store.find(task.id))
        self.store.undo()
        self.assertEqual(TaskStore(self.directory).find(task.id).text, "Updated")
        self.store.undo()
        self.assertEqual(self.store.find(task.id).text, "Plan")
        self.assertFalse(self.store.find(task.id).subtasks[0]["completed"])

    def test_failed_save_rolls_back_memory_and_original_file(self):
        task = self.store.add("Keep me")
        original = self.store.path.read_bytes()
        with patch("task_store.atomic_json", side_effect=OSError("disk unavailable")):
            with self.assertRaises(StoreError): self.store.delete(task.id)
        self.assertEqual(self.store.path.read_bytes(), original)
        self.assertEqual(self.store.find(task.id).text, "Keep me")
        self.assertEqual(len(self.store.history), 1)

    def test_invalid_existing_file_is_never_replaced(self):
        path = self.directory / "tasks.json"
        path.write_text("[broken", encoding="utf-8")
        with self.assertRaises(StoreError): TaskStore(self.directory)
        self.assertEqual(path.read_text(), "[broken")

    def test_backup_contains_last_valid_state(self):
        first = self.store.add("First")
        self.store.add("Second")
        backup = json.loads(self.store.path.with_suffix(".json.bak").read_text())
        self.assertEqual([item["id"] for item in backup], [first.id])

    def test_import_merges_without_duplicates_and_undoes(self):
        existing = self.store.add("Existing")
        path = self.directory / "import.json"
        atomic_json(path, [existing.to_dict(), {"id": "new", "text": "Imported"}])
        self.assertEqual(self.store.import_file(path), 1)
        self.assertEqual(self.store.import_file(path), 0)
        self.store.undo()
        self.assertEqual(len(self.store.tasks), 1)
        atomic_json(path, [{"id": "bad", "text": "Broken", "due_date": "2026-02-30"}])
        with self.assertRaises(StoreError): self.store.import_file(path)
        self.assertEqual(len(self.store.tasks), 1)

    def test_filters_search_notes_checklist_and_order(self):
        today = date.today()
        old = self.store.add("Past", due_date=(today-timedelta(days=1)).isoformat(), category="Práce")
        today_task = self.store.add("Now", due_date=today.isoformat(), priority="high", notes="Find this", starred=True)
        future = self.store.add("Later", due_date=(today+timedelta(days=1)).isoformat(), subtasks=[{"text": "Hidden word"}])
        plain = self.store.add("Unscheduled")
        self.assertEqual({t.id for t in self.store.visible("today")}, {old.id, today_task.id})
        self.assertEqual([t.id for t in self.store.visible("upcoming")], [future.id])
        self.assertEqual([t.id for t in self.store.visible("important")], [today_task.id])
        self.assertEqual([t.id for t in self.store.visible(search="find this")], [today_task.id])
        self.assertEqual([t.id for t in self.store.visible(search="hidden")], [future.id])
        self.assertEqual(self.store.visible(sort="Due date")[-1].id, plain.id)
        self.assertEqual(self.store.visible(sort="Priority")[0].id, today_task.id)
        self.store.reorder(old.id, future.id)
        self.assertLess(self.store.tasks.index(old), self.store.tasks.index(future))

    def test_recurring_completion_and_undo_are_one_transaction(self):
        task = self.store.add("Daily", due_date=date.today().isoformat(), repeat="daily", subtasks=[{"text": "Step", "completed": True}])
        self.store.toggle(task.id)
        self.assertEqual(len(self.store.tasks), 2)
        child = next(t for t in self.store.tasks if t.id != task.id)
        self.assertFalse(child.completed)
        self.assertFalse(child.subtasks[0]["completed"])
        self.assertEqual(child.repeat_from, task.id)
        self.assertEqual(child.due_date, (date.today()+timedelta(days=1)).isoformat())
        self.store.toggle(task.id); self.store.toggle(task.id)
        self.assertEqual(len(self.store.tasks), 2)
        self.store.undo(); self.store.undo(); self.store.undo()
        self.assertEqual(len(self.store.tasks), 1)
        self.assertFalse(self.store.tasks[0].completed)

    def test_monthly_repeats_preserve_31st_and_skip_overdue(self):
        task = Task(id="monthly", text="Month end", due_date="2026-01-31", repeat="monthly")
        self.assertEqual(next_due(task, date(2026, 1, 31)), "2026-02-28")
        task.due_date = "2026-02-28"; task.repeat_day = 31
        self.assertEqual(next_due(task, date(2026, 2, 28)), "2026-03-31")
        self.assertEqual(next_due(task, date(2026, 5, 2)), "2026-05-31")
        task.repeat = "weekly"; task.due_date = "2026-01-01"
        self.assertGreater(next_due(task, date(2026, 5, 2)), "2026-05-02")

    def test_validation_rejects_invalid_data(self):
        for raw in ([{"id": "1", "text": "Task", "completed": "false"}], [{"id": "1", "text": "Task", "due_time": "12:00"}], [{"id": "1", "text": "Task", "subtasks": ["bad"]}], [{"id": "1", "text": "A"}, {"id": "1", "text": "B"}]):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError): parse_tasks(raw)

    def test_due_change_resets_reminder(self):
        task = self.store.add("Reminder", due_date="2026-11-10", due_time="12:00", last_reminded_at="old")
        self.store.update(task.id, due_date="2026-11-11")
        self.assertEqual(self.store.find(task.id).last_reminded_at, "")

    def test_export_round_trip_unicode_and_fields(self):
        task = self.store.add("Příprava", notes="Žluťoučký", repeat="monthly", due_date="2026-11-30")
        output = self.directory / "backup.json"
        self.store.export(output)
        loaded = parse_tasks(json.loads(output.read_text(encoding="utf-8")))
        self.assertEqual(loaded[0].to_dict(), task.to_dict())


if __name__ == "__main__": unittest.main()
