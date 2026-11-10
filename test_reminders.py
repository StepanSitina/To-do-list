import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from reminders import countdown, due_datetime, next_celebration, pending_reminders
from task_store import Task, TaskStore


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 10, 10, 0, 30)

    def task(self, seconds, **values):
        end = self.now + timedelta(seconds=seconds)
        return Task(id="task", text="Příprava projektu", due_date=end.date().isoformat(), due_time=end.strftime("%H:%M"), **values)

    def test_day_hour_and_due_each_have_distinct_persistable_markers(self):
        task = self.task(23*3600)
        day = pending_reminders([task], {}, self.now)[0]
        self.assertTrue(day.key.endswith("|day"))
        task.reminders_sent.append(day.key)
        self.assertEqual(pending_reminders([task], {}, self.now), [])
        later = self.now + timedelta(hours=22, minutes=30)
        hour = pending_reminders([task], {}, later)[0]
        self.assertTrue(hour.key.endswith("|hour"))
        task.reminders_sent.append(hour.key)
        due = pending_reminders([task], {}, due_datetime(task))[0]
        self.assertTrue(due.key.endswith("|due"))

    def test_disabled_notifications_and_completed_tasks_never_send(self):
        task = self.task(-10)
        self.assertEqual(pending_reminders([task], {"notifications_enabled": False}, self.now), [])
        task.completed = True
        self.assertEqual(pending_reminders([task], {}, self.now), [])

    def test_timer_only_notifies_at_exact_finish_including_seconds(self):
        end = self.now + timedelta(seconds=20)
        task = self.task(20, timer_end=end.isoformat(), timer_started_at=self.now.isoformat())
        self.assertEqual(pending_reminders([task], {}, self.now), [])
        self.assertEqual(pending_reminders([task], {}, end-timedelta(seconds=1)), [])
        self.assertEqual(len(pending_reminders([task], {}, end)), 1)
        self.assertEqual(countdown(task, self.now), "Zbývá 00:20")
        self.assertEqual(countdown(task, end), "Čas vypršel")

    def test_timer_and_markers_survive_restart(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            store = TaskStore(Path(directory))
            end = self.now + timedelta(hours=24)
            task = store.add("Časovač", timer_end=end.isoformat(), timer_started_at=self.now.isoformat())
            reminder = pending_reminders(store.tasks, {}, end)[0]
            history = len(store.history)
            store.acknowledge_reminders([reminder])
            self.assertEqual(len(store.history), history)
            loaded = TaskStore(Path(directory))
            self.assertEqual(loaded.find(task.id).timer_end, end.isoformat())
            self.assertEqual(pending_reminders(loaded.tasks, {}, end+timedelta(minutes=1)), [])

    def test_sleep_catches_up_latest_phase_once_without_all_old_reminders(self):
        task = self.task(-300)
        result = pending_reminders([task], {}, self.now)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].key.endswith("|due"))
        task.reminders_sent.append(result[0].key)
        self.assertEqual(pending_reminders([task], {}, self.now), [])
        self.assertEqual(pending_reminders([self.task(-90000)], {}, self.now), [])

    def test_lead_preferences(self):
        self.assertEqual(pending_reminders([self.task(80000)], {"reminder_lead": "due"}, self.now), [])
        self.assertEqual(pending_reminders([self.task(80000)], {"reminder_lead": "hour"}, self.now), [])
        self.assertEqual(len(pending_reminders([self.task(1800)], {"reminder_lead": "hour"}, self.now)), 1)
        self.assertEqual(len(pending_reminders([self.task(80000)], {"reminder_lead": "day"}, self.now)), 1)

    def test_date_only_deadline_uses_nine_am(self):
        task = Task(id="date", text="Datum", due_date="2026-11-11")
        self.assertEqual(due_datetime(task), datetime(2026, 11, 11, 9))

    def test_legacy_one_hour_reminders_are_not_duplicated(self):
        task = self.task(1800)
        task.last_reminded_at = due_datetime(task).isoformat()
        self.assertEqual(pending_reminders([task], {}, self.now), [])
        self.assertTrue(pending_reminders([task], {}, due_datetime(task))[0].key.endswith("|due"))

    def test_changing_due_date_cancels_old_timer_and_reminder_markers(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            store = TaskStore(Path(directory))
            task = store.add("Timer", timer_end="2026-11-10T12:00:33", timer_started_at="2026-11-10T11:00:33", due_date="2026-11-10", due_time="12:00", reminders_sent=["old"])
            store.update(task.id, due_date="2026-11-11")
            changed = store.find(task.id)
            self.assertEqual(changed.timer_end, "")
            self.assertEqual(changed.reminders_sent, [])

    def test_repeat_task_does_not_inherit_finished_timer(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            store = TaskStore(Path(directory))
            task = store.add("Repeat", timer_end="2026-11-10T12:00:33", due_date="2026-11-10", due_time="12:00", repeat="daily")
            store.toggle(task.id)
            child = next(item for item in store.tasks if item.repeat_from == task.id)
            self.assertEqual(child.timer_end, "")
            self.assertEqual(child.reminders_sent, [])

    def test_every_completion_uses_a_different_quote_and_color(self):
        quote, palette = -1, -1
        for _ in range(100):
            new_quote, new_palette = next_celebration(quote, palette)
            self.assertNotEqual(new_quote, quote)
            self.assertNotEqual(new_palette, palette)
            quote, palette = new_quote, new_palette

    def test_include_completed_keeps_gray_rows_available(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            store = TaskStore(Path(directory))
            task = store.add("Hotový úkol")
            store.toggle(task.id)
            self.assertEqual(store.visible(), [])
            self.assertEqual(len(store.visible(include_completed=True)), 1)


if __name__ == "__main__": unittest.main()
