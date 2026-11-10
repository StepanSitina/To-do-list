"""Local task data, validation, atomic persistence, and undo. No UI dependencies."""

from __future__ import annotations

import calendar
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

CATEGORIES = {"Práce": "Práce", "Škola": "Škola", "Osobní": "Osobní", "Programování": "Programování"}
PRIORITIES = {"low": "Nízká", "normal": "Střední", "high": "Vysoká"}
REPEATS = {"none": "Neopakuje se", "daily": "Každý den", "weekly": "Každý týden", "monthly": "Každý měsíc"}
VOCATIVE_NAMES = {
    "petr": "Petře", "stepan": "Stepane", "štěpán": "Štěpáne", "tomáš": "Tomáši",
    "tomas": "Tomáši", "jan": "Jane", "martin": "Martine", "michal": "Michale",
    "ondřej": "Ondřeji", "ondrej": "Ondřeji", "lukáš": "Lukáši", "lukas": "Lukáši",
    "jakub": "Jakube", "adam": "Adame", "david": "Davide", "filip": "Filipe",
    "radek": "Radku", "marek": "Marku", "jiří": "Jiří", "jiri": "Jiří",
    "pavel": "Pavle", "karel": "Karle", "matěj": "Matěji", "matej": "Matěji",
}


def vocative_name(name: str) -> str:
    original = name.strip()
    result = VOCATIVE_NAMES.get(" ".join(original.split()).casefold(), original)
    return result.upper() if original.isupper() else result


class StoreError(Exception):
    """A readable error that must never result in overwriting existing data."""


def atomic_json(path: Path, data: object, *, backup: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if backup and path.exists():
        # Only replace the recovery copy after verifying the current file.
        old = path.read_text(encoding="utf-8-sig")
        json.loads(old)
        atomic_text(path.with_suffix(path.suffix + ".bak"), old)
    atomic_text(path, payload)


def atomic_text(path: Path, text: str) -> None:
    temporary = path.parent / f".focus-{uuid4().hex}.tmp"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def normalize_priority(value: object) -> str:
    text = str(value).casefold()
    if text.startswith(("high", "vysok")):
        return "high"
    if text.startswith(("low", "nízk", "nizk")):
        return "low"
    return "normal"


@dataclass
class Task:
    id: str
    text: str
    completed: bool = False
    created_at: str = ""
    due_date: str = ""
    due_time: str = ""
    completed_at: str = ""
    last_reminded_at: str = ""
    category: str = "Osobní"
    priority: str = "normal"
    notes: str = ""
    subtasks: list[dict] = field(default_factory=list)
    repeat: str = "none"
    starred: bool = False
    repeat_from: str = ""
    repeat_day: int = 0
    timer_end: str = ""
    timer_started_at: str = ""
    reminders_sent: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self.created_at = self.created_at or datetime.now().isoformat(timespec="seconds")
        self.priority = normalize_priority(self.priority)

    def to_dict(self) -> dict:
        values = asdict(self)
        extras = values.pop("extra")
        return {**extras, **values}

    @classmethod
    def from_dict(cls, raw: object) -> Task:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not raw["id"]:
            raise ValueError("A task is missing its ID.")
        if not isinstance(raw.get("text"), str) or not raw["text"].strip():
            raise ValueError("A task is missing its title.")
        fields = cls.__dataclass_fields__
        values = {key: value for key, value in raw.items() if key in fields and key != "extra"}
        for key in ("completed", "starred"):
            if key in values and not isinstance(values[key], bool):
                raise ValueError(f"Invalid {key} value.")
        for key in ("created_at", "due_date", "due_time", "completed_at", "last_reminded_at", "category", "notes", "repeat_from", "timer_end", "timer_started_at"):
            if key in values and not isinstance(values[key], str):
                raise ValueError(f"Invalid {key} value.")
        for key in ("timer_end", "timer_started_at"):
            if values.get(key):
                parsed = datetime.fromisoformat(values[key])
                if parsed.tzinfo is not None:
                    raise ValueError("Timer timestamps must use local time.")
        if not isinstance(values.get("reminders_sent", []), list) or any(not isinstance(item, str) for item in values.get("reminders_sent", [])):
            raise ValueError("Invalid reminder history.")
        if values.get("due_date"):
            values["due_date"] = date.fromisoformat(values["due_date"]).isoformat()
        if values.get("due_time"):
            values["due_time"] = datetime.strptime(values["due_time"], "%H:%M").strftime("%H:%M")
            if not values.get("due_date"):
                raise ValueError("A due time needs a date.")
        if values.get("repeat", "none") not in REPEATS:
            raise ValueError("Unknown repeat interval.")
        if "repeat_day" in values and (type(values["repeat_day"]) is not int or not 0 <= values["repeat_day"] <= 31):
            raise ValueError("Invalid monthly repeat day.")
        subtasks = values.get("subtasks", [])
        if not isinstance(subtasks, list) or any(
            not isinstance(item, dict) or not isinstance(item.get("text"), str)
            or not isinstance(item.get("completed", False), bool) for item in subtasks
        ):
            raise ValueError("Invalid checklist.")
        values["subtasks"] = [{**item, "id": item.get("id") or str(uuid4()), "completed": item.get("completed", False)} for item in subtasks]
        values["extra"] = {key: value for key, value in raw.items() if key not in fields}
        return cls(**values)


def parse_tasks(raw: object) -> list[Task]:
    if not isinstance(raw, list):
        raise ValueError("The task file must contain a list.")
    tasks = [Task.from_dict(item) for item in raw]
    if len({task.id for task in tasks}) != len(tasks):
        raise ValueError("Task IDs must be unique.")
    return tasks


def next_due(task: Task, today: date | None = None) -> str:
    today = today or date.today()
    current = date.fromisoformat(task.due_date) if task.due_date else today
    if task.repeat == "daily":
        result = current + timedelta(days=max(1, (today - current).days + 1))
    elif task.repeat == "weekly":
        weeks = max(1, (today - current).days // 7 + 1)
        result = current + timedelta(weeks=weeks)
    elif task.repeat == "monthly":
        year, month = current.year, current.month
        anchor = task.repeat_day or current.day
        while True:
            month += 1
            if month == 13:
                year, month = year + 1, 1
            result = date(year, month, min(anchor, calendar.monthrange(year, month)[1]))
            if result > today:
                break
    else:
        return ""
    return result.isoformat()


class TaskStore:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.path = self.directory / "tasks.json"
        self.settings_path = self.directory / "settings.json"
        self.tasks: list[Task] = []
        self.settings: dict = {}
        self.history: list[tuple[str, list[dict]]] = []
        try:
            if self.path.exists():
                self.tasks = parse_tasks(json.loads(self.path.read_text(encoding="utf-8-sig")))
            if self.settings_path.exists():
                self.settings = json.loads(self.settings_path.read_text(encoding="utf-8-sig"))
                if not isinstance(self.settings, dict):
                    raise ValueError("Settings must be an object.")
        except (OSError, ValueError, TypeError) as error:
            raise StoreError(f"Could not read your saved data. The original files have been left in place.\n\n{error}") from error

    def find(self, task_id: str) -> Task | None:
        return next((task for task in self.tasks if task.id == task_id), None)

    def _snapshot(self) -> list[dict]:
        return [task.to_dict() for task in self.tasks]

    def _commit(self, label: str, change) -> None:
        before = self._snapshot()
        try:
            change()
            atomic_json(self.path, self._snapshot(), backup=True)
        except (OSError, ValueError, TypeError) as error:
            self.tasks = parse_tasks(before)
            raise StoreError(f"The change could not be saved. Your previous tasks are intact.\n\n{error}") from error
        self.history.append((label, before))
        self.history = self.history[-40:]

    def add(self, text: str, **values) -> Task:
        task = Task.from_dict({"id": str(uuid4()), "text": text.strip(), **values})
        self._commit("Task added", lambda: self.tasks.insert(0, task))
        return task

    def update(self, task_id: str, **values) -> None:
        task = self.find(task_id)
        if task is None:
            return
        data = {**task.to_dict(), **values}
        if (data.get("due_date"), data.get("due_time")) != (task.due_date, task.due_time):
            data["last_reminded_at"] = ""
            data["reminders_sent"] = []
            if "timer_end" not in values:
                data["timer_end"] = ""
                data["timer_started_at"] = ""
            data["repeat_day"] = date.fromisoformat(data["due_date"]).day if data.get("due_date") else 0
        if data.get("timer_end") != task.timer_end:
            data["reminders_sent"] = []
            data["last_reminded_at"] = ""
        replacement = Task.from_dict(data)
        index = self.tasks.index(task)
        self._commit("Task updated", lambda: self.tasks.__setitem__(index, replacement))

    def toggle(self, task_id: str) -> None:
        task = self.find(task_id)
        if task is None:
            return

        def change():
            task.completed = not task.completed
            task.completed_at = datetime.now().isoformat(timespec="seconds") if task.completed else ""
            if task.completed and task.repeat != "none" and not any(item.repeat_from == task.id for item in self.tasks):
                data = task.to_dict()
                data.update(id=str(uuid4()), completed=False, completed_at="", created_at="",
                            due_date=next_due(task), last_reminded_at="", repeat_from=task.id,
                            timer_end="", timer_started_at="", reminders_sent=[],
                            repeat_day=task.repeat_day or (date.fromisoformat(task.due_date).day if task.due_date else date.today().day))
                data["subtasks"] = [{**item, "id": str(uuid4()), "completed": False} for item in task.subtasks]
                self.tasks.insert(self.tasks.index(task) + 1, Task.from_dict(data))

        self._commit("Task completed" if not task.completed else "Task reopened", change)

    def delete(self, task_id: str) -> None:
        self._commit("Task deleted", lambda: self.tasks.__setitem__(slice(None), [task for task in self.tasks if task.id != task_id]))

    def reorder(self, task_id: str, before_id: str) -> None:
        task, before = self.find(task_id), self.find(before_id)
        if task is None or before is None or task is before:
            return

        def change():
            self.tasks.remove(task)
            self.tasks.insert(self.tasks.index(before), task)

        self._commit("Task moved", change)

    def undo(self) -> str | None:
        if not self.history:
            return None
        label, snapshot = self.history[-1]
        try:
            atomic_json(self.path, snapshot, backup=True)
        except (OSError, ValueError) as error:
            raise StoreError(f"Could not undo the change.\n\n{error}") from error
        self.tasks = parse_tasks(snapshot)
        self.history.pop()
        return label

    def save_settings(self, **values) -> None:
        settings = {**self.settings, **values}
        try:
            atomic_json(self.settings_path, settings)
        except OSError as error:
            raise StoreError(f"Could not save preferences.\n\n{error}") from error
        self.settings = settings

    def export(self, path: Path) -> None:
        try:
            atomic_json(path, self._snapshot())
        except OSError as error:
            raise StoreError(f"Could not export tasks.\n\n{error}") from error

    def import_file(self, path: Path) -> int:
        try:
            imported = parse_tasks(json.loads(path.read_text(encoding="utf-8-sig")))
        except (OSError, ValueError, TypeError) as error:
            raise StoreError(f"This file could not be imported.\n\n{error}") from error
        existing = {task.id for task in self.tasks}
        added = [task for task in imported if task.id not in existing]
        if added:
            self._commit("Tasks imported", lambda: self.tasks.extend(added))
        return len(added)

    def acknowledge_reminders(self, reminders) -> None:
        before = self._snapshot()
        try:
            for reminder in reminders:
                task = self.find(reminder.task_id)
                if task and reminder.key not in task.reminders_sent:
                    task.reminders_sent.append(reminder.key)
                    task.reminders_sent = task.reminders_sent[-20:]
            atomic_json(self.path, self._snapshot(), backup=True)
        except (OSError, ValueError) as error:
            self.tasks = parse_tasks(before)
            raise StoreError(f"Připomínku se nepodařilo uložit.\n\n{error}") from error

    def visible(self, view="all", *, search="", category="", priority="", sort="Manual order", on_date="", include_completed=False) -> list[Task]:
        today = date.today().isoformat()
        tasks = [task for task in self.tasks if (include_completed and view != "completed") or task.completed == (view == "completed")]
        if view == "today":
            tasks = [task for task in tasks if (task.completed and task.completed_at.startswith(today)) or (not task.completed and task.due_date and task.due_date <= today)]
        elif view == "upcoming":
            tasks = [task for task in tasks if task.due_date > today]
        elif view == "important":
            tasks = [task for task in tasks if task.starred]
        if on_date:
            tasks = [task for task in tasks if task.due_date == on_date]
        if category:
            tasks = [task for task in tasks if task.category == category]
        if priority:
            tasks = [task for task in tasks if task.priority == priority]
        words = search.casefold().split()
        if words:
            tasks = [task for task in tasks if all(word in (task.text + " " + task.notes + " " + " ".join(item["text"] for item in task.subtasks)).casefold() for word in words)]
        if sort in ("Due date", "Termín"):
            tasks.sort(key=lambda task: (task.due_date or "9999", task.due_time or "23:59"))
        elif sort in ("Priority", "Priorita"):
            tasks.sort(key=lambda task: ({"high": 0, "normal": 1, "low": 2}[task.priority], task.due_date or "9999"))
        elif sort in ("A to Z", "A až Z"):
            tasks.sort(key=lambda task: task.text.casefold())
        elif sort in ("Newest first", "Nejnovější"):
            tasks.sort(key=lambda task: task.created_at, reverse=True)
        return tasks
