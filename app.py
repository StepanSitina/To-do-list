"""Focus List desktop application.

Part 1: task management, JSON persistence, and completion counter.
"""

from __future__ import annotations

import json
import tkinter as tk
from dataclasses import asdict, dataclass
from pathlib import Path
from tkinter import messagebox, ttk
from uuid import uuid4


APP_TITLE = "Focus List"
TASKS_FILE = Path(__file__).with_name("tasks.json")


@dataclass
class Task:
    """A task persisted in the local JSON file."""

    id: str
    text: str
    completed: bool = False


class TodoApp(tk.Tk):
    """Main window for the Focus List task manager."""

    BACKGROUND = "#f4f7fb"
    SURFACE = "#ffffff"
    TEXT = "#263445"
    MUTED = "#667085"
    ACCENT = "#5b52c6"
    ACCENT_HOVER = "#4840ac"
    BORDER = "#e2e8f0"
    COMPLETED = "#98a2b3"

    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("760x620")
        self.minsize(520, 460)
        self.configure(bg=self.BACKGROUND)

        self.tasks: list[Task] = []
        self.task_widgets: dict[str, tuple[tk.Frame, tk.BooleanVar]] = {}
        self.input_var = tk.StringVar()
        self.counter_var = tk.StringVar(value="Completed: 0")

        self._configure_styles()
        self._build_layout()
        self._load_tasks()
        self._render_tasks()

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Task.TCheckbutton",
            background=self.SURFACE,
            foreground=self.TEXT,
            font=("Segoe UI", 11),
            padding=(8, 8),
        )
        style.configure(
            "Task.Completed.TCheckbutton",
            background=self.SURFACE,
            foreground=self.COMPLETED,
            font=("Segoe UI", 11, "overstrike"),
            padding=(8, 8),
        )
        style.map(
            "Task.TCheckbutton",
            background=[("active", self.SURFACE)],
            foreground=[("disabled", self.COMPLETED)],
        )

    def _build_layout(self) -> None:
        content = tk.Frame(self, bg=self.BACKGROUND)
        content.pack(fill="both", expand=True, padx=42, pady=38)

        header = tk.Frame(content, bg=self.BACKGROUND)
        header.pack(fill="x", pady=(0, 26))

        tk.Label(
            header,
            text="DAILY MOMENTUM",
            bg=self.BACKGROUND,
            fg="#6b63d9",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Focus List",
            bg=self.BACKGROUND,
            fg="#18212d",
            font=("Segoe UI", 30, "bold"),
        ).pack(anchor="w", pady=(3, 5))
        tk.Label(
            header,
            text="Small steps, steady progress, one clear list.",
            bg=self.BACKGROUND,
            fg=self.MUTED,
            font=("Segoe UI", 11),
        ).pack(anchor="w")
        tk.Label(
            header,
            textvariable=self.counter_var,
            bg="#e8e7ff",
            fg="#4f46b8",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=7,
        ).pack(anchor="w", pady=(16, 0))

        form = tk.Frame(content, bg=self.BACKGROUND)
        form.pack(fill="x", pady=(0, 20))
        self.task_entry = tk.Entry(
            form,
            textvariable=self.input_var,
            bg=self.SURFACE,
            fg=self.TEXT,
            insertbackground=self.TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.BORDER,
            highlightcolor=self.ACCENT,
            font=("Segoe UI", 11),
        )
        self.task_entry.pack(side="left", fill="x", expand=True, ipady=11, padx=(0, 10))
        self.task_entry.bind("<Return>", self._handle_submit)

        tk.Button(
            form,
            text="Add Task",
            command=self._add_task,
            bg=self.ACCENT,
            activebackground=self.ACCENT_HOVER,
            activeforeground="white",
            fg="white",
            relief="flat",
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            padx=20,
            pady=10,
        ).pack(side="right")

        self.task_container = tk.Frame(content, bg=self.BACKGROUND)
        self.task_container.pack(fill="both", expand=True)

    def _handle_submit(self, _event: tk.Event[tk.Entry]) -> str:
        self._add_task()
        return "break"

    def _add_task(self) -> None:
        text = self.input_var.get().strip()
        if not text:
            self.task_entry.focus_set()
            return

        self.tasks.insert(0, Task(id=str(uuid4()), text=text))
        self.input_var.set("")
        self._save_tasks()
        self._render_tasks()
        self.task_entry.focus_set()

    def _toggle_task(self, task: Task) -> None:
        task.completed = not task.completed
        self._save_tasks()
        self._render_tasks()

    def _delete_task(self, task: Task) -> None:
        self.tasks = [item for item in self.tasks if item.id != task.id]
        self._save_tasks()
        self._render_tasks()

    def _render_tasks(self) -> None:
        for child in self.task_container.winfo_children():
            child.destroy()
        self.task_widgets.clear()

        if not self.tasks:
            tk.Label(
                self.task_container,
                text="Your list is clear. Add your first task above.",
                bg=self.BACKGROUND,
                fg=self.MUTED,
                font=("Segoe UI", 11),
                pady=32,
            ).pack(fill="x")
        else:
            for task in self.tasks:
                self._create_task_row(task)

        completed_count = sum(task.completed for task in self.tasks)
        self.counter_var.set(f"Completed: {completed_count}")

    def _create_task_row(self, task: Task) -> None:
        row = tk.Frame(
            self.task_container,
            bg=self.SURFACE,
            highlightthickness=1,
            highlightbackground=self.BORDER,
        )
        row.pack(fill="x", pady=(0, 10))

        completed_var = tk.BooleanVar(value=task.completed)
        checkbutton = ttk.Checkbutton(
            row,
            text=task.text,
            variable=completed_var,
            command=lambda current_task=task: self._toggle_task(current_task),
            style="Task.Completed.TCheckbutton" if task.completed else "Task.TCheckbutton",
        )
        checkbutton.pack(side="left", fill="x", expand=True, padx=(8, 0), pady=5)

        tk.Button(
            row,
            text="×",
            command=lambda current_task=task: self._delete_task(current_task),
            bg=self.SURFACE,
            activebackground="#fff0f0",
            activeforeground="#d04444",
            fg=self.COMPLETED,
            relief="flat",
            cursor="hand2",
            font=("Segoe UI", 16),
            padx=12,
        ).pack(side="right", pady=5)
        self.task_widgets[task.id] = (row, completed_var)

    def _load_tasks(self) -> None:
        if not TASKS_FILE.exists():
            return

        try:
            raw_tasks = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
            if not isinstance(raw_tasks, list):
                raise ValueError("The tasks file must contain a JSON list.")

            self.tasks = [
                Task(
                    id=item["id"],
                    text=item["text"],
                    completed=item["completed"],
                )
                for item in raw_tasks
                if (
                    isinstance(item, dict)
                    and isinstance(item.get("id"), str)
                    and isinstance(item.get("text"), str)
                    and isinstance(item.get("completed"), bool)
                )
            ]
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            messagebox.showwarning(
                "Could not load tasks",
                f"The saved task file could not be loaded:\n{error}",
                parent=self,
            )
            self.tasks = []

    def _save_tasks(self) -> None:
        try:
            TASKS_FILE.write_text(
                json.dumps([asdict(task) for task in self.tasks], indent=2),
                encoding="utf-8",
            )
        except OSError as error:
            messagebox.showerror(
                "Could not save tasks",
                f"Your latest change could not be saved:\n{error}",
                parent=self,
            )


if __name__ == "__main__":
    app = TodoApp()
    app.mainloop()
