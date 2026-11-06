"""Focus List: a polished CustomTkinter to-do list and calendar dashboard."""

from __future__ import annotations

import calendar
import json
import queue
import re
import sys
import threading
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from tkinter import messagebox
from uuid import uuid4

import customtkinter as ctk


APP_TITLE = "To-Do List"
APP_DIRECTORY = (
    Path(sys.executable).parent
    if getattr(sys, "frozen", False)
    else Path(__file__).parent
)
TASKS_FILE = APP_DIRECTORY / "tasks.json"
SETTINGS_FILE = APP_DIRECTORY / "settings.json"
DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"
CATEGORIES = ("Práce", "Škola", "Osobní", "Programování")
PRIORITIES = ("Nízká 🟢", "Střední 🟡", "Vysoká 🔴")
VOCATIVE_NAMES = {
    "petr": "Petře",
    "stepan": "Stepane",
    "štěpán": "Štěpáne",
    "tomáš": "Tomáši",
    "tomas": "Tomáši",
    "jan": "Jane",
    "martin": "Martine",
    "michal": "Michale",
    "ondřej": "Ondřeji",
    "ondrej": "Ondřeji",
    "lukáš": "Lukáši",
    "lukas": "Lukáši",
    "jakub": "Jakube",
    "adam": "Adame",
    "david": "Davide",
    "filip": "Filipe",
    "radek": "Radku",
    "marek": "Marku",
    "jiří": "Jiří",
    "jiri": "Jiří",
    "pavel": "Pavle",
    "karel": "Karle",
    "matěj": "Matěji",
    "matej": "Matěji",
}


def vocative_name(name: str) -> str:
    """Return a known Czech vocative form, preserving the stored name otherwise."""
    original = name.strip()
    if not original:
        return original
    normalized = re.sub(r"\s+", " ", original).casefold()
    vocative = VOCATIVE_NAMES.get(normalized)
    if not vocative:
        return original
    if original.isupper():
        return vocative.upper()
    return vocative[:1].upper() + vocative[1:]

@dataclass
class Task:
    """A task persisted in tasks.json."""

    id: str
    text: str
    completed: bool = False
    created_at: str = ""
    due_date: str = ""
    due_time: str = ""
    completed_at: str = ""
    last_reminded_at: str = ""
    category: str = "Osobní"
    priority: str = "Střední 🟡"

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = date.today().isoformat()


class FocusListApp(ctk.CTk):
    """Main application window."""

    PURPLE = "#6d5dfc"
    PURPLE_HOVER = "#5848ed"
    CORAL = "#ff9478"
    TEXT = ("#172033", "#f7f8fc")
    MUTED = ("#718096", "#9aa7bd")
    CARD = ("#ffffff", "#1b2435")
    PANEL = ("#f8faff", "#111827")
    BORDER = ("#e5eaf3", "#2d3950")
    SUCCESS = "#4fd1a5"

    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("Light")
        ctk.set_default_color_theme("blue")
        self.title(APP_TITLE)
        self.geometry("1280x800")
        self.minsize(1120, 680)

        self.tasks: list[Task] = []
        self.tasks_lock = threading.Lock()
        self.reminder_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.stop_event = threading.Event()
        self.selected_date = date.min
        self.calendar_month = date.today().replace(day=1)
        self.user_name = ""
        self.search_var = ctk.StringVar()
        self.category_filter_var = ctk.StringVar(value="Všechny kategorie")
        self.priority_filter_var = ctk.StringVar(value="Všechny priority")
        self.category_var = ctk.StringVar(value=CATEGORIES[2])
        self.priority_var = ctk.StringVar(value=PRIORITIES[1])
        self.task_input: ctk.CTkEntry
        self.date_var = ctk.StringVar()
        self.time_var = ctk.StringVar()
        self.date_entry: ctk.CTkEntry
        self.time_entry: ctk.CTkEntry
        self.active_list: ctk.CTkScrollableFrame
        self.completed_list: ctk.CTkScrollableFrame
        self.tabs: ctk.CTkTabview
        self.notification: ctk.CTkLabel
        self.calendar_grid: ctk.CTkFrame
        self.calendar_title: ctk.CTkLabel
        self.filter_label: ctk.CTkLabel
        self.mode_button: ctk.CTkButton
        self.clock_label: ctk.CTkLabel
        self.date_label: ctk.CTkLabel
        self.counter_label: ctk.CTkLabel
        self.greeting_label: ctk.CTkLabel
        self.overlay: ctk.CTkFrame | None = None

        self._load_settings()
        self._load_tasks()
        self._build_ui()
        if not self.user_name:
            self.after(150, self._show_name_setup)
        self._update_clock()
        self._render_calendar()
        self._render_tasks()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._reminder_thread = threading.Thread(
            target=self._reminder_worker,
            name="task-reminder",
            daemon=True,
        )
        self._reminder_thread.start()
        self.after(500, self._process_reminders)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=0, minsize=292)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, corner_radius=0, fg_color=self.PANEL)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(
            self.sidebar,
            text="FOCUS LIST",
            text_color=self.PURPLE,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, padx=28, pady=(34, 4), sticky="w")
        ctk.CTkLabel(
            self.sidebar,
            text="To-Do List",
            text_color=self.TEXT,
            font=ctk.CTkFont(size=23, weight="bold"),
        ).grid(row=1, column=0, padx=28, sticky="w")
        self.greeting_label = ctk.CTkLabel(
            self.sidebar,
            text=f"Ahoj, {vocative_name(self.user_name)}!" if self.user_name else "Ahoj!",
            text_color=self.MUTED,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.greeting_label.grid(row=2, column=0, padx=28, pady=(3, 0), sticky="w")
        self.counter_label = ctk.CTkLabel(
            self.sidebar,
            text="0 completed",
            text_color="#ffffff",
            fg_color=self.PURPLE,
            corner_radius=12,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.counter_label.grid(row=3, column=0, padx=28, pady=(22, 30), sticky="w")

        calendar_card = ctk.CTkFrame(
            self.sidebar,
            fg_color=self.CARD,
            border_width=1,
            border_color=self.BORDER,
            corner_radius=18,
        )
        calendar_card.grid(row=4, column=0, padx=18, sticky="new")
        calendar_card.grid_columnconfigure(1, weight=1)
        previous_button = ctk.CTkButton(
            calendar_card,
            text="‹",
            width=28,
            fg_color="transparent",
            hover_color=self.BORDER,
            text_color=self.TEXT,
            font=ctk.CTkFont(size=22),
            command=lambda: self._change_month(-1),
        )
        previous_button.grid(row=0, column=0, padx=(10, 0), pady=14)
        self.calendar_title = ctk.CTkLabel(
            calendar_card,
            text="",
            text_color=self.TEXT,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.calendar_title.grid(row=0, column=1, pady=14)
        next_button = ctk.CTkButton(
            calendar_card,
            text="›",
            width=28,
            fg_color="transparent",
            hover_color=self.BORDER,
            text_color=self.TEXT,
            font=ctk.CTkFont(size=22),
            command=lambda: self._change_month(1),
        )
        next_button.grid(row=0, column=2, padx=(0, 10), pady=14)
        self.calendar_grid = ctk.CTkFrame(calendar_card, fg_color="transparent")
        self.calendar_grid.grid(row=1, column=0, columnspan=3, padx=10, pady=(0, 14))

        ctk.CTkLabel(
            self.sidebar,
            text="Click a date to filter your tasks.",
            text_color=self.MUTED,
            font=ctk.CTkFont(size=12),
        ).grid(row=6, column=0, padx=28, pady=(18, 30), sticky="sw")

        self.main = ctk.CTkFrame(self, fg_color=self.PANEL, corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew", padx=(1, 0))
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(4, weight=1)

        header = ctk.CTkFrame(self.main, fg_color="transparent")
        header.grid(row=0, column=0, padx=38, pady=(30, 18), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        self.clock_label = ctk.CTkLabel(
            header,
            text="",
            text_color=self.TEXT,
            font=ctk.CTkFont(size=31, weight="bold"),
        )
        self.clock_label.grid(row=0, column=0, sticky="w")
        self.date_label = ctk.CTkLabel(
            header,
            text="",
            text_color=self.MUTED,
            font=ctk.CTkFont(size=14),
        )
        self.date_label.grid(row=1, column=0, pady=(2, 0), sticky="w")
        ctk.CTkLabel(
            header,
            text="To-Do List",
            text_color=self.PURPLE,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=2, column=0, pady=(8, 0), sticky="w")
        self.mode_button = ctk.CTkButton(
            header,
            text="☾  Dark mode",
            width=128,
            height=36,
            corner_radius=12,
            fg_color=self.CARD,
            hover_color=self.BORDER,
            text_color=self.TEXT,
            command=self._toggle_theme,
        )
        self.mode_button.grid(row=0, column=1, rowspan=2, sticky="e")

        self.notification = ctk.CTkLabel(
            self.main,
            text="",
            height=34,
            corner_radius=10,
            text_color="#ffffff",
            fg_color=self.SUCCESS,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.notification.grid(row=1, column=0, padx=38, pady=(0, 12), sticky="ew")
        self.notification.grid_remove()

        form = ctk.CTkFrame(
            self.main,
            fg_color=self.CARD,
            border_width=1,
            border_color=self.BORDER,
            corner_radius=18,
        )
        form.grid(row=2, column=0, padx=38, pady=(0, 20), sticky="ew")
        form.grid_columnconfigure(0, weight=1)
        self.task_input = ctk.CTkEntry(
            form,
            placeholder_text="Add a new task...",
            height=42,
            border_width=0,
            fg_color="transparent",
            text_color=self.TEXT,
            font=ctk.CTkFont(size=14),
        )
        self.task_input.grid(row=0, column=0, padx=(16, 8), pady=10, sticky="ew")
        self.task_input.bind("<Return>", self._handle_submit)
        self.date_entry = self._picker_entry(
            form,
            self.date_var,
            "Datum (DD.MM.YYYY)",
            self._show_date_picker,
            1,
            width=142,
        )
        self.time_entry = self._picker_entry(
            form,
            self.time_var,
            "Čas (HH:MM)",
            self._show_time_picker,
            2,
            width=112,
        )
        self.category_box = ctk.CTkComboBox(
            form,
            values=list(CATEGORIES),
            variable=self.category_var,
            width=122,
            height=38,
            border_color=self.BORDER,
            fg_color=self.PANEL,
            button_color=self.PURPLE,
            text_color=self.TEXT,
            font=ctk.CTkFont(size=11),
        )
        self.category_box.grid(row=0, column=3, padx=4, pady=10)
        self.priority_box = ctk.CTkComboBox(
            form,
            values=list(PRIORITIES),
            variable=self.priority_var,
            width=132,
            height=38,
            border_color=self.BORDER,
            fg_color=self.PANEL,
            button_color=self.PURPLE,
            text_color=self.TEXT,
            font=ctk.CTkFont(size=11),
        )
        self.priority_box.grid(row=0, column=4, padx=4, pady=10)
        ctk.CTkButton(
            form,
            text="Add Task",
            width=92,
            height=40,
            corner_radius=12,
            fg_color=self.PURPLE,
            hover_color=self.PURPLE_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._add_task,
        ).grid(row=0, column=5, padx=(4, 10), pady=10)

        search_bar = ctk.CTkFrame(self.main, fg_color="transparent")
        search_bar.grid(row=3, column=0, padx=38, pady=(0, 12), sticky="ew")
        search_bar.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(
            search_bar,
            textvariable=self.search_var,
            placeholder_text="Hledat úkol...",
            height=38,
            fg_color=self.CARD,
            border_color=self.BORDER,
            text_color=self.TEXT,
        ).grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self.search_var.trace_add("write", lambda *_: self._render_tasks())
        self.category_filter = ctk.CTkComboBox(
            search_bar,
            values=["Všechny kategorie", *CATEGORIES],
            variable=self.category_filter_var,
            width=150,
            height=38,
            fg_color=self.CARD,
            border_color=self.BORDER,
            button_color=self.PURPLE,
            text_color=self.TEXT,
            command=lambda _: self._render_tasks(),
        )
        self.category_filter.grid(row=0, column=1, padx=4)
        self.priority_filter = ctk.CTkComboBox(
            search_bar,
            values=["Všechny priority", *PRIORITIES],
            variable=self.priority_filter_var,
            width=150,
            height=38,
            fg_color=self.CARD,
            border_color=self.BORDER,
            button_color=self.PURPLE,
            text_color=self.TEXT,
            command=lambda _: self._render_tasks(),
        )
        self.priority_filter.grid(row=0, column=2, padx=(4, 0))

        self.tabs = ctk.CTkTabview(
            self.main,
            fg_color="transparent",
            segmented_button_fg_color=self.CARD,
            segmented_button_selected_color=self.PURPLE,
            segmented_button_selected_hover_color=self.PURPLE_HOVER,
            segmented_button_unselected_color=self.CARD,
            segmented_button_unselected_hover_color=self.BORDER,
            text_color=self.TEXT,
        )
        self.tabs.grid(row=4, column=0, padx=30, pady=(0, 10), sticky="ew")
        self.tabs.grid_configure(sticky="nsew")
        self.tabs.add("Active Tasks")
        self.tabs.add("Completed Tasks")
        self.tabs.set("Active Tasks")
        self.active_list = self._create_task_list(self.tabs.tab("Active Tasks"))
        self.completed_list = self._create_task_list(self.tabs.tab("Completed Tasks"))

    def _picker_entry(
        self,
        parent: ctk.CTkFrame,
        variable: ctk.StringVar,
        placeholder: str,
        command: object,
        column: int,
        width: int,
    ) -> ctk.CTkEntry:
        wrapper = ctk.CTkFrame(parent, fg_color=self.PANEL, corner_radius=10)
        wrapper.grid(row=0, column=column, padx=4, pady=10)
        wrapper.grid_columnconfigure(0, weight=1)
        entry = ctk.CTkEntry(
            wrapper,
            textvariable=variable,
            placeholder_text=placeholder,
            width=width - 34,
            height=38,
            border_width=0,
            fg_color="transparent",
            text_color=self.TEXT,
            font=ctk.CTkFont(size=11),
        )
        entry.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            wrapper,
            text="⌄",
            width=30,
            height=34,
            corner_radius=8,
            fg_color="transparent",
            hover_color=self.BORDER,
            text_color=self.MUTED,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=command,
        ).grid(row=0, column=1, padx=2, pady=2)
        return entry

    def _show_date_picker(self, target: ctk.StringVar | None = None) -> None:
        target = target or self.date_var
        picker = ctk.CTkToplevel(self)
        picker.title("Vyberte datum")
        picker.geometry("330x350")
        picker.resizable(False, False)
        picker.configure(fg_color=self.PANEL)
        picker.transient(self)
        picker.grab_set()
        try:
            current = datetime.strptime(target.get(), "%d.%m.%Y").date()
        except ValueError:
            current = date.today()
        month_state = {"value": current.replace(day=1)}
        grid = ctk.CTkFrame(picker, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=18, pady=18)

        def render_month() -> None:
            for child in grid.winfo_children():
                child.destroy()
            month = month_state["value"]
            header = ctk.CTkFrame(grid, fg_color="transparent")
            header.pack(fill="x", pady=(0, 14))
            ctk.CTkButton(
                header, text="‹", width=32, fg_color="transparent",
                hover_color=self.BORDER, text_color=self.TEXT,
                command=lambda: change_month(-1),
            ).pack(side="left")
            ctk.CTkLabel(
                header, text=month.strftime("%B %Y"), text_color=self.TEXT,
                font=ctk.CTkFont(size=15, weight="bold"),
            ).pack(side="left", expand=True)
            ctk.CTkButton(
                header, text="›", width=32, fg_color="transparent",
                hover_color=self.BORDER, text_color=self.TEXT,
                command=lambda: change_month(1),
            ).pack(side="right")
            weekdays = ctk.CTkFrame(grid, fg_color="transparent")
            weekdays.pack()
            for column, label in enumerate(("Po", "Út", "St", "Čt", "Pá", "So", "Ne")):
                ctk.CTkLabel(
                    weekdays, text=label, width=38, text_color=self.MUTED,
                    font=ctk.CTkFont(size=10, weight="bold"),
                ).grid(row=0, column=column, padx=1, pady=2)
            for row, week in enumerate(calendar.monthcalendar(month.year, month.month), start=1):
                for column, day_number in enumerate(week):
                    if day_number == 0:
                        ctk.CTkLabel(weekdays, text="", width=38, height=28).grid(
                            row=row, column=column, padx=1, pady=1
                        )
                        continue
                    selected = date(month.year, month.month, day_number)
                    ctk.CTkButton(
                        weekdays,
                        text=str(day_number),
                        width=38,
                        height=28,
                        corner_radius=8,
                        fg_color=self.PURPLE if selected == current else "transparent",
                        hover_color=self.PURPLE_HOVER,
                        text_color="#ffffff" if selected == current else self.TEXT,
                        command=lambda value=selected: choose(value),
                    ).grid(row=row, column=column, padx=1, pady=1)

        def change_month(offset: int) -> None:
            month = month_state["value"]
            index = month.month - 1 + offset
            month_state["value"] = date(month.year + index // 12, index % 12 + 1, 1)
            render_month()

        def choose(value: date) -> None:
            target.set(value.strftime("%d.%m.%Y"))
            picker.destroy()

        render_month()

    def _show_time_picker(self, target: ctk.StringVar | None = None) -> None:
        target = target or self.time_var
        picker = ctk.CTkToplevel(self)
        picker.title("Vyberte čas")
        picker.geometry("300x210")
        picker.resizable(False, False)
        picker.configure(fg_color=self.PANEL)
        picker.transient(self)
        picker.grab_set()
        current = target.get().split(":")
        hour = current[0] if len(current) == 2 else "09"
        minute = current[1] if len(current) == 2 else "00"
        ctk.CTkLabel(
            picker, text="Čas úkolu", text_color=self.TEXT,
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(24, 14))
        controls = ctk.CTkFrame(picker, fg_color="transparent")
        controls.pack()
        hour_box = ctk.CTkComboBox(
            controls, values=[f"{value:02d}" for value in range(24)],
            width=84, height=40, fg_color=self.CARD, border_color=self.BORDER,
            button_color=self.PURPLE, text_color=self.TEXT,
        )
        hour_box.set(hour)
        hour_box.pack(side="left", padx=5)
        ctk.CTkLabel(controls, text=":", text_color=self.TEXT, font=ctk.CTkFont(size=20)).pack(side="left")
        minute_box = ctk.CTkComboBox(
            controls, values=[f"{value:02d}" for value in range(0, 60, 5)],
            width=84, height=40, fg_color=self.CARD, border_color=self.BORDER,
            button_color=self.PURPLE, text_color=self.TEXT,
        )
        minute_box.set(minute if minute in {f"{value:02d}" for value in range(0, 60, 5)} else "00")
        minute_box.pack(side="left", padx=5)
        ctk.CTkButton(
            picker, text="Použít", width=140, height=38, corner_radius=11,
            fg_color=self.PURPLE, hover_color=self.PURPLE_HOVER,
            command=lambda: (target.set(f"{hour_box.get()}:{minute_box.get()}"), picker.destroy()),
        ).pack(pady=22)

    def _dialog_picker_entry(
        self,
        parent: ctk.CTkFrame,
        variable: ctk.StringVar,
        placeholder: str,
        command: object,
    ) -> ctk.CTkEntry:
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.pack(fill="x", padx=28, pady=4)
        wrapper.grid_columnconfigure(0, weight=1)
        entry = ctk.CTkEntry(
            wrapper,
            textvariable=variable,
            placeholder_text=placeholder,
            height=38,
            fg_color=self.CARD,
            border_color=self.BORDER,
            text_color=self.TEXT,
        )
        entry.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            wrapper,
            text="⌄",
            width=34,
            height=34,
            corner_radius=8,
            fg_color=self.CARD,
            hover_color=self.BORDER,
            text_color=self.MUTED,
            command=command,
        ).grid(row=0, column=1, padx=(4, 0))
        return entry

    def _create_task_list(self, parent: ctk.CTkFrame) -> ctk.CTkScrollableFrame:
        task_list = ctk.CTkScrollableFrame(
            parent,
            fg_color="transparent",
            scrollbar_button_color=self.BORDER,
            scrollbar_button_hover_color=self.PURPLE,
        )
        task_list.pack(fill="both", expand=True)
        return task_list

    def _update_clock(self) -> None:
        now = datetime.now()
        self.clock_label.configure(text=now.strftime("%I:%M:%S %p"))
        self.date_label.configure(text=now.strftime("%A, %B %d, %Y"))
        self.after(1000, self._update_clock)

    def _toggle_theme(self) -> None:
        is_dark = ctk.get_appearance_mode() == "Dark"
        ctk.set_appearance_mode("Light" if is_dark else "Dark")
        self.mode_button.configure(text="☀  Light mode" if not is_dark else "☾  Dark mode")
        self._render_calendar()
        self._render_tasks()

    def _handle_submit(self, _event: object) -> str:
        self._add_task()
        return "break"

    def _add_task(self) -> None:
        text = self.task_input.get().strip()
        due_values = self._read_due_values()
        if due_values is None:
            return
        due_date, due_time = due_values
        if not text:
            self.task_input.focus_set()
            return
        if due_date and due_time:
            due_datetime = datetime.strptime(
                f"{due_date} {due_time}",
                f"{DATE_FORMAT} {TIME_FORMAT}",
            )
            if due_datetime <= datetime.now():
                messagebox.showwarning(
                    "Past due date",
                    "A task cannot be created with a due date and time in the past.",
                    parent=self,
                )
                self.date_entry.focus_set()
                return

        with self.tasks_lock:
            self.tasks.insert(
                0,
                Task(
                    id=str(uuid4()),
                    text=text,
                    created_at=date.today().isoformat(),
                    due_date=due_date,
                    due_time=due_time,
                    category=self.category_var.get(),
                    priority=self.priority_var.get(),
                ),
            )
        self.task_input.delete(0, "end")
        self.date_var.set("")
        self.time_var.set("")
        self._save_tasks()
        self._render_calendar()
        self._render_tasks()
        self.task_input.focus_set()

    def _read_due_values(self) -> tuple[str, str] | None:
        date_text = self.date_var.get().strip()
        time_text = self.time_var.get().strip()
        if not date_text and not time_text:
            return "", ""
        if not date_text:
            messagebox.showwarning("Chybí datum", "Vyberte nebo zadejte datum.", parent=self)
            self.date_entry.focus_set()
            return None
        if not time_text:
            messagebox.showwarning("Chybí čas", "Vyberte nebo zadejte čas.", parent=self)
            self.time_entry.focus_set()
            return None
        try:
            parsed_date = datetime.strptime(date_text, "%d.%m.%Y")
            parsed_time = datetime.strptime(time_text, TIME_FORMAT)
            due_datetime = datetime.strptime(
                f"{parsed_date.strftime(DATE_FORMAT)} {parsed_time.strftime(TIME_FORMAT)}",
                f"{DATE_FORMAT} {TIME_FORMAT}",
            )
        except ValueError:
            messagebox.showwarning(
                "Neplatný termín",
                "Použijte datum DD.MM.YYYY a čas HH:MM.",
                parent=self,
            )
            return None
        return due_datetime.strftime(DATE_FORMAT), due_datetime.strftime(TIME_FORMAT)

    def _toggle_task(self, task: Task) -> None:
        with self.tasks_lock:
            task.completed = not task.completed
            task.completed_at = (
                datetime.now().isoformat(timespec="seconds")
                if task.completed
                else ""
            )
        self._save_tasks()
        self._render_tasks()
        if task.completed:
            self._show_completion_overlay()

    def _delete_task(self, task: Task) -> None:
        with self.tasks_lock:
            self.tasks = [item for item in self.tasks if item.id != task.id]
        self._save_tasks()
        self._render_calendar()
        self._render_tasks()

    def _filtered_tasks(self) -> list[Task]:
        search = self.search_var.get().strip().casefold()
        category = self.category_filter_var.get()
        priority = self.priority_filter_var.get()
        filtered = self.tasks
        if self.selected_date != date.min:
            selected = self.selected_date.isoformat()
            filtered = [task for task in filtered if task.due_date == selected]
        if search:
            filtered = [task for task in filtered if search in task.text.casefold()]
        if category != "Všechny kategorie":
            filtered = [task for task in filtered if task.category == category]
        if priority != "Všechny priority":
            filtered = [task for task in filtered if task.priority == priority]
        return filtered

    def _show_notification(self, message: str) -> None:
        self.notification.configure(text=message)
        self.notification.grid()
        if hasattr(self, "_notification_job"):
            self.after_cancel(self._notification_job)
        self._notification_job = self.after(4200, self.notification.grid_remove)

    def _reminder_worker(self) -> None:
        """Check due tasks off the UI thread and enqueue one-hour reminders."""
        while not self.stop_event.is_set():
            now = datetime.now()
            with self.tasks_lock:
                task_snapshot = [
                    Task(**asdict(task))
                    for task in self.tasks
                    if not task.completed and task.due_date and task.due_time
                ]
            for task in task_snapshot:
                try:
                    due_datetime = datetime.strptime(
                        f"{task.due_date} {task.due_time}",
                        f"{DATE_FORMAT} {TIME_FORMAT}",
                    )
                except ValueError:
                    continue
                seconds_until_due = (due_datetime - now).total_seconds()
                if 0 < seconds_until_due <= 3600 and task.last_reminded_at != due_datetime.isoformat():
                    self.reminder_queue.put((task.id, f"Reminder: “{task.text}” is due within one hour."))
                    with self.tasks_lock:
                        for current_task in self.tasks:
                            if current_task.id == task.id:
                                current_task.last_reminded_at = due_datetime.isoformat()
                                break
            self.stop_event.wait(15)

    def _process_reminders(self) -> None:
        try:
            while True:
                task_id, message = self.reminder_queue.get_nowait()
                if any(task.id == task_id and not task.completed for task in self.tasks):
                    self.bell()
                    self._save_tasks()
                    self._show_notification(message)
        except queue.Empty:
            pass
        if not self.stop_event.is_set():
            self.after(500, self._process_reminders)

    def _close(self) -> None:
        self.stop_event.set()
        self.destroy()

    def _render_tasks(self) -> None:
        active_tasks = [task for task in self._filtered_tasks() if not task.completed]
        completed_tasks = [task for task in self._filtered_tasks() if task.completed]
        self._render_task_list(self.active_list, active_tasks, "No active tasks here yet.")
        self._render_task_list(
            self.completed_list,
            completed_tasks,
            "Completed tasks will appear here.",
        )

        completed_count = sum(task.completed for task in self.tasks)
        self.counter_label.configure(text=f"{completed_count} completed")

    def _render_task_list(
        self,
        task_list: ctk.CTkScrollableFrame,
        tasks: list[Task],
        empty_text: str,
    ) -> None:
        for child in task_list.winfo_children():
            child.destroy()
        if not tasks:
            ctk.CTkLabel(
                task_list,
                text=empty_text,
                text_color=self.MUTED,
                font=ctk.CTkFont(size=14),
            ).pack(pady=50)
            return
        for task in tasks:
            self._create_task_card(task, task_list)

    def _create_task_card(
        self,
        task: Task,
        task_list: ctk.CTkScrollableFrame,
    ) -> None:
        card = ctk.CTkFrame(
            task_list,
            fg_color=self.CARD,
            border_width=1,
            border_color=self.BORDER,
            corner_radius=16,
            height=68,
        )
        card.pack(fill="x", padx=4, pady=6)
        card.grid_columnconfigure(1, weight=1)

        checkbox = ctk.CTkCheckBox(
            card,
            text="",
            width=28,
            checkbox_width=22,
            checkbox_height=22,
            border_width=2,
            fg_color=self.PURPLE,
            hover_color=self.PURPLE_HOVER,
            command=lambda current=task: self._toggle_task(current),
        )
        checkbox.grid(row=0, column=0, padx=(16, 6), pady=17)
        if task.completed:
            checkbox.select()

        font = ctk.CTkFont(size=14, weight="bold")
        if task.completed:
            font.configure(overstrike=True)
        task_label = ctk.CTkLabel(
            card,
            text=task.text,
            text_color=self.MUTED if task.completed else self.TEXT,
            font=font,
            anchor="w",
        )
        task_label.grid(row=0, column=1, padx=4, sticky="ew")

        meta = f"{task.category}  •  {task.priority}"
        ctk.CTkLabel(
            card,
            text=meta,
            text_color=self.MUTED,
            font=ctk.CTkFont(size=10),
        ).grid(row=0, column=2, padx=8)

        if task.due_date:
            due_text = task.due_date
            if task.due_time:
                due_text += f"  {task.due_time}"
            due_label = ctk.CTkLabel(
                card,
                text=f"◷  {due_text}",
                text_color=self.MUTED,
                font=ctk.CTkFont(size=11),
            )
            due_label.grid(row=0, column=3, padx=8)

        if not task.completed:
            ctk.CTkButton(
                card,
                text="Upravit",
                width=64,
                height=28,
                corner_radius=8,
                fg_color="transparent",
                hover_color=self.BORDER,
                text_color=self.PURPLE,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda current=task: self._show_edit_dialog(current),
            ).grid(row=0, column=4, padx=4)

        ctk.CTkButton(
            card,
            text="×",
            width=30,
            height=30,
            corner_radius=10,
            fg_color="transparent",
            hover_color=("#feeceb", "#482632"),
            text_color=self.MUTED,
            font=ctk.CTkFont(size=20),
            command=lambda current=task: self._delete_task(current),
        ).grid(row=0, column=5, padx=(0, 10))

    def _show_edit_dialog(self, task: Task) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Upravit úkol")
        dialog.geometry("440x510")
        dialog.resizable(False, False)
        dialog.configure(fg_color=self.PANEL)
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="Upravit úkol",
            text_color=self.TEXT,
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(anchor="w", padx=28, pady=(28, 16))
        text_input = ctk.CTkEntry(
            dialog,
            height=42,
            fg_color=self.CARD,
            border_color=self.BORDER,
            text_color=self.TEXT,
        )
        text_input.insert(0, task.text)
        text_input.pack(fill="x", padx=28, pady=6)

        def combo(label: str, values: list[str], current: str) -> ctk.CTkComboBox:
            ctk.CTkLabel(dialog, text=label, text_color=self.MUTED).pack(
                anchor="w", padx=28, pady=(8, 2)
            )
            widget = ctk.CTkComboBox(
                dialog,
                values=values,
                height=38,
                fg_color=self.CARD,
                border_color=self.BORDER,
                button_color=self.PURPLE,
                text_color=self.TEXT,
            )
            widget.set(current)
            widget.pack(fill="x", padx=28)
            return widget

        category_box = combo("Kategorie", list(CATEGORIES), task.category)
        priority_box = combo("Priorita", list(PRIORITIES), task.priority)
        edit_date_var = ctk.StringVar(
            value=(
                datetime.strptime(task.due_date, DATE_FORMAT).strftime("%d.%m.%Y")
                if task.due_date
                else ""
            )
        )
        edit_time_var = ctk.StringVar(value=task.due_time)
        ctk.CTkLabel(
            dialog,
            text="Datum (DD.MM.YYYY)",
            text_color=self.MUTED,
        ).pack(anchor="w", padx=28, pady=(8, 2))
        self._dialog_picker_entry(
            dialog,
            edit_date_var,
            "Datum (DD.MM.YYYY)",
            lambda: self._show_date_picker(edit_date_var),
        )
        ctk.CTkLabel(
            dialog,
            text="Čas (HH:MM)",
            text_color=self.MUTED,
        ).pack(anchor="w", padx=28, pady=(8, 2))
        self._dialog_picker_entry(
            dialog,
            edit_time_var,
            "Čas (HH:MM)",
            lambda: self._show_time_picker(edit_time_var),
        )

        def save_edit() -> None:
            new_text = text_input.get().strip()
            display_date = edit_date_var.get().strip()
            new_time = edit_time_var.get().strip()
            if not new_text:
                messagebox.showwarning("Chybí text", "Úkol musí mít text.", parent=dialog)
                return
            try:
                new_date = (
                    datetime.strptime(display_date, "%d.%m.%Y").strftime(DATE_FORMAT)
                    if display_date
                    else ""
                )
            except ValueError:
                messagebox.showwarning("Neplatné datum", "Použijte DD.MM.YYYY.", parent=dialog)
                return
            if new_date and new_time:
                try:
                    due_datetime = datetime.strptime(
                        f"{new_date} {new_time}",
                        f"{DATE_FORMAT} {TIME_FORMAT}",
                    )
                except ValueError:
                    messagebox.showwarning("Neplatný termín", "Zadejte platné datum a čas.", parent=dialog)
                    return
                if due_datetime <= datetime.now():
                    messagebox.showwarning("Termín v minulosti", "Termín musí být v budoucnosti.", parent=dialog)
                    return
            elif new_date or new_time:
                messagebox.showwarning("Neúplný termín", "Vyplňte datum i čas, nebo obě pole smažte.", parent=dialog)
                return
            with self.tasks_lock:
                task.text = new_text
                task.category = category_box.get()
                task.priority = priority_box.get()
                task.due_date = new_date
                task.due_time = new_time
                task.last_reminded_at = ""
            self._save_tasks()
            self._render_calendar()
            self._render_tasks()
            dialog.destroy()

        ctk.CTkButton(
            dialog,
            text="Uložit změny",
            height=42,
            corner_radius=12,
            fg_color=self.PURPLE,
            hover_color=self.PURPLE_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=save_edit,
        ).pack(fill="x", padx=28, pady=(24, 8))
        ctk.CTkButton(
            dialog,
            text="Zrušit",
            height=36,
            corner_radius=10,
            fg_color="transparent",
            hover_color=self.BORDER,
            text_color=self.MUTED,
            command=dialog.destroy,
        ).pack(fill="x", padx=28)

    def _show_completion_overlay(self) -> None:
        if self.overlay is not None and self.overlay.winfo_exists():
            return
        self.overlay = ctk.CTkFrame(
            self,
            fg_color=("#2a1c4d", "#120d27"),
            corner_radius=0,
        )
        self.overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.overlay.lift()
        card = ctk.CTkFrame(
            self.overlay,
            width=520,
            height=330,
            fg_color=self.CORAL,
            corner_radius=28,
        )
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)
        ctk.CTkLabel(
            card,
            text="🎉 Úkol splněn!",
            text_color="#3c205d",
            font=ctk.CTkFont(size=32, weight="bold"),
        ).pack(pady=(58, 12))
        ctk.CTkLabel(
            card,
            text=f"Skvělá práce, {vocative_name(self.user_name) or 'to zvládáte'}! Jeden krok je za vámi.",
            text_color="#5b2e68",
            font=ctk.CTkFont(size=14),
            wraplength=410,
            justify="center",
        ).pack(padx=30)
        ctk.CTkButton(
            card,
            text="Pokračovat",
            width=190,
            height=48,
            corner_radius=15,
            fg_color="#3c205d",
            hover_color="#28143f",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._hide_completion_overlay,
        ).pack(pady=(32, 0))

    def _hide_completion_overlay(self) -> None:
        if self.overlay is not None and self.overlay.winfo_exists():
            self.overlay.destroy()
        self.overlay = None

    def _change_month(self, offset: int) -> None:
        month_index = self.calendar_month.month - 1 + offset
        year = self.calendar_month.year + month_index // 12
        month = month_index % 12 + 1
        self.calendar_month = date(year, month, 1)
        self._render_calendar()

    def _render_calendar(self) -> None:
        for child in self.calendar_grid.winfo_children():
            child.destroy()
        self.calendar_title.configure(
            text=self.calendar_month.strftime("%B %Y")
        )
        for column, weekday in enumerate(("M", "T", "W", "T", "F", "S", "S")):
            ctk.CTkLabel(
                self.calendar_grid,
                text=weekday,
                width=30,
                text_color=self.MUTED,
                font=ctk.CTkFont(size=11, weight="bold"),
            ).grid(row=0, column=column, padx=1, pady=(0, 6))

        month_days = calendar.monthcalendar(
            self.calendar_month.year,
            self.calendar_month.month,
        )
        due_dates = {task.due_date for task in self.tasks if task.due_date}
        for row, week in enumerate(month_days, start=1):
            for column, day_number in enumerate(week):
                if not day_number:
                    ctk.CTkLabel(self.calendar_grid, text="", width=30).grid(
                        row=row, column=column, padx=1, pady=2
                    )
                    continue
                day = date(
                    self.calendar_month.year,
                    self.calendar_month.month,
                    day_number,
                )
                is_selected = day == self.selected_date
                has_tasks = day.isoformat() in due_dates
                ctk.CTkButton(
                    self.calendar_grid,
                    text=f"{day_number}{' •' if has_tasks else ''}",
                    width=30,
                    height=28,
                    corner_radius=8,
                    fg_color=self.PURPLE if is_selected else "transparent",
                    hover_color=self.PURPLE_HOVER,
                    text_color="#ffffff" if is_selected else self.TEXT,
                    font=ctk.CTkFont(size=11, weight="bold" if has_tasks else "normal"),
                    command=lambda selected=day: self._select_date(selected),
                ).grid(row=row, column=column, padx=1, pady=2)

        ctk.CTkButton(
            self.calendar_grid,
            text="Show all tasks",
            width=220,
            height=28,
            corner_radius=8,
            fg_color="transparent",
            hover_color=self.BORDER,
            text_color=self.PURPLE,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._show_all_tasks,
        ).grid(row=len(month_days) + 1, column=0, columnspan=7, pady=(8, 0))

    def _select_date(self, selected: date) -> None:
        self.selected_date = selected
        self._render_calendar()
        self._render_tasks()

    def _show_all_tasks(self) -> None:
        self.selected_date = date.min
        self._render_calendar()
        self._render_tasks()

    def _show_name_setup(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Vítejte v To-Do List")
        dialog.geometry("440x280")
        dialog.resizable(False, False)
        dialog.configure(fg_color=self.PANEL)
        dialog.transient(self)
        dialog.grab_set()
        ctk.CTkLabel(
            dialog,
            text="Vítejte! 👋",
            text_color=self.TEXT,
            font=ctk.CTkFont(size=26, weight="bold"),
        ).pack(pady=(32, 6))
        ctk.CTkLabel(
            dialog,
            text="Jak vám můžeme říkat?",
            text_color=self.MUTED,
            font=ctk.CTkFont(size=14),
        ).pack(pady=(0, 18))
        name_input = ctk.CTkEntry(
            dialog,
            placeholder_text="Vaše jméno",
            width=300,
            height=42,
            fg_color=self.CARD,
            border_color=self.BORDER,
            text_color=self.TEXT,
        )
        name_input.pack()
        name_input.focus_set()

        def save_name() -> None:
            name = name_input.get().strip()
            if not name:
                return
            self.user_name = name
            self._save_settings()
            self.greeting_label.configure(text=f"Ahoj, {vocative_name(name)}!")
            dialog.destroy()

        name_input.bind("<Return>", lambda _: save_name())
        ctk.CTkButton(
            dialog,
            text="Začít plánovat",
            width=180,
            height=42,
            corner_radius=13,
            fg_color=self.PURPLE,
            hover_color=self.PURPLE_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=save_name,
        ).pack(pady=22)

    def _load_settings(self) -> None:
        if not SETTINGS_FILE.exists():
            return
        try:
            settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(settings, dict) and isinstance(settings.get("name"), str):
                self.user_name = settings["name"].strip()
        except (OSError, json.JSONDecodeError):
            self.user_name = ""

    def _save_settings(self) -> None:
        try:
            SETTINGS_FILE.write_text(
                json.dumps({"name": self.user_name}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as error:
            messagebox.showerror("Chyba nastavení", f"Nastavení se nepodařilo uložit:\n{error}", parent=self)

    def _load_tasks(self) -> None:
        if not TASKS_FILE.exists():
            return
        try:
            raw_tasks = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
            if not isinstance(raw_tasks, list):
                raise ValueError("The tasks file must contain a JSON list.")
            loaded: list[Task] = []
            for item in raw_tasks:
                if not isinstance(item, dict):
                    continue
                if not isinstance(item.get("id"), str) or not isinstance(item.get("text"), str):
                    continue
                loaded.append(
                    Task(
                        id=item["id"],
                        text=item["text"],
                        completed=item.get("completed", False),
                        created_at=item.get("created_at", date.today().isoformat()),
                        due_date=item.get("due_date", ""),
                        due_time=item.get("due_time", ""),
                        completed_at=item.get("completed_at", ""),
                        last_reminded_at=item.get("last_reminded_at", ""),
                        category=item.get("category", "Osobní"),
                        priority=item.get("priority", "Střední 🟡"),
                    )
                )
            self.tasks = loaded
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            messagebox.showwarning(
                "Could not load tasks",
                f"The saved task file could not be loaded:\n{error}",
                parent=self,
            )

    def _save_tasks(self) -> None:
        try:
            with self.tasks_lock:
                task_data = [asdict(task) for task in self.tasks]
            TASKS_FILE.write_text(
                json.dumps(task_data, indent=2),
                encoding="utf-8",
            )
        except OSError as error:
            messagebox.showerror(
                "Could not save tasks",
                f"Your latest change could not be saved:\n{error}",
                parent=self,
            )


if __name__ == "__main__":
    app = FocusListApp()
    app.mainloop()
