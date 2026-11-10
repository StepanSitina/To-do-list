"""Hidden application and native integration verification; never sends a banner."""
import json
import queue
import tempfile
import traceback
from datetime import datetime, timedelta
from pathlib import Path


def run_self_test(report):
    report = Path(report)
    report.parent.mkdir(parents=True, exist_ok=True)
    result = {"ok": False, "checks": [], "notifications_displayed": 0, "windows_activated": 0}
    app = None
    bridge = None
    guard = None
    try:
        import tkinter as tk
        import app as application
        from reminders import due_datetime
        from task_store import TaskStore, atomic_json
        from windows_desktop import DesktopBridge, InstanceGuard

        def check(condition, name):
            if not condition: raise AssertionError(name)
            result["checks"].append(name)

        def unexpected_dialog(*args, **kwargs):
            raise AssertionError(f"Unexpected dialog: {args}")

        application.messagebox.showerror = unexpected_dialog
        application.messagebox.showwarning = unexpected_dialog
        with tempfile.TemporaryDirectory(prefix="todo-selftest-", dir=report.parent) as folder:
            data = Path(folder)
            atomic_json(data / "settings.json", {"name": "Štěpán"})
            app = application.ToDoListApp(data, hidden=True, desktop=False)
            callbacks = []
            app.report_callback_exception = lambda *error: callbacks.append(str(error))
            check(app.title() == "To-do list", "application_name")
            check(app.state() == "withdrawn", "main_window_stays_hidden")
            app.quick.set("Ověřit ukládání úkolů")
            app.add_task()
            app.update()
            task = app.store.tasks[0]
            check(task.text == "Ověřit ukládání úkolů", "add_task")
            app.open_task(task.id)
            app.update()
            app.edit_notes.insert("1.0", "Poznámka přežije restart")
            app.update()
            check(app.save_editor(), "save_task_details")
            app.toggle_task(task.id)
            app.update()
            check(app.celebration is not None, "completion_screen")
            first_quote, first_palette = app.store.settings["last_quote"], app.store.settings["last_palette"]
            check(task.id in app.row_widgets, "completed_task_remains_visible")
            check(app.store.find(task.id).completed, "checkbox_completes_task")

            def labels(widget):
                for child in widget.winfo_children():
                    if isinstance(child, tk.Label): yield child
                    yield from labels(child)

            task_label = next(label for label in labels(app.row_widgets[task.id]) if label.cget("text") == task.text)
            check(task_label.cget("fg") == app.p["muted"] and "overstrike" in task_label.cget("font"), "completed_task_is_gray_and_crossed_out")
            check("1" in app.completed_total.cget("text"), "completed_counter")
            app.dismiss_celebration()
            app.toggle_task(task.id)
            app.toggle_task(task.id)
            check(app.store.settings["last_quote"] != first_quote and app.store.settings["last_palette"] != first_palette, "new_quote_and_palette_each_time")
            app.dismiss_celebration()
            app.toggle_theme()
            app.update()
            check(app.store.settings["theme"] == "dark", "dark_theme_persists")
            app.toggle_theme()

            class FakeTray:
                available = True
                enabled = True
                events = queue.Queue()
                sent = []
                def notify(self, title, text, **kwargs):
                    self.sent.append((title, text)); return True
                def dismiss_notification(self): pass
                def close(self): pass

            app.tray = FakeTray()
            app.toggle_task(task.id)
            check(app.start_timer(task.id, 1/60), "start_timer_with_second_precision")
            end = due_datetime(app.store.find(task.id))
            check(len(app.check_reminders(end + timedelta(seconds=1))) == 1, "background_timer_notification_delivery")
            check(len(app.check_reminders(end + timedelta(seconds=2))) == 0, "notification_sent_once")
            app.set_notifications(False)
            app.start_timer(task.id, 1/60)
            check(app.check_reminders(due_datetime(app.store.find(task.id))+timedelta(seconds=1)) == [], "notifications_can_be_disabled")
            check(len(app.tray.sent) == 1, "disabled_notifications_never_call_windows")
            app.close()
            check(app.state() == "withdrawn" and not app._shutting_down, "close_keeps_background_running")
            app.quit_app()
            app = None
            loaded = TaskStore(data)
            check(loaded.find(task.id).notes == "Poznámka přežije restart" and bool(loaded.find(task.id).timer_end), "json_tasks_and_timers_survive_restart")
            check(loaded.settings["notifications_enabled"] is False, "notification_preference_survives_restart")
            check(not callbacks, "no_tk_callback_errors")

            guard = InstanceGuard(data)
            duplicate = InstanceGuard(data)
            check(not guard.already_running and duplicate.already_running, "single_instance_guard")
            duplicate.close()
            bridge = DesktopBridge(data, application.RESOURCE_DIRECTORY / "assets" / "todo.ico")
            check(bridge.start(), "windows_tray_registration: " + (bridge.error or "ok"))
            check(bridge.notify("To-do list", "Zkouška formátu oznámení", dry_run=True), "native_notification_payload")
            check(guard.request_open(), "second_launch_signals_existing_instance")
            event = bridge.events.get(timeout=2)
            check(event[0] == "show", "tray_open_event_received_without_activating_window")
            bridge.close(); bridge = None
            guard.close(); guard = None
        result["ok"] = True
    except BaseException:
        result["error"] = traceback.format_exc()
    finally:
        if app:
            try: app.quit_app()
            except Exception: pass
        if bridge: bridge.close()
        if guard: guard.close()
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["ok"] else 1
