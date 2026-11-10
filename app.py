"""To-do list — přehledné úkoly, časovače a připomínky pro Windows."""

from __future__ import annotations

import argparse
import calendar
import copy
import math
import os
import queue
import sys
import tempfile
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from task_store import CATEGORIES, PRIORITIES, REPEATS, StoreError, Task, TaskStore, atomic_json, vocative_name
from reminders import PALETTES, QUOTES, countdown, next_celebration, pending_reminders
from windows_desktop import APP_NAME, DesktopBridge, InstanceGuard, set_app_identity

APP_DIRECTORY = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
RESOURCE_DIRECTORY = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
LIGHT = {
    "paper": "#FCFCF9", "side": "#F0F0E9", "panel": "#F7F7F2", "ink": "#282F29",
    "muted": "#70776F", "faint": "#8E958C", "line": "#E2E5DC", "hover": "#F0F2EB",
    "green": "#355D49", "green_hover": "#284A39", "soft": "#DFE8DA", "green_text": "#355D49",
    "white": "#FFFFFF", "red": "#B14E3E", "red_soft": "#F8E8E0", "amber": "#967533",
    "field": "#FFFFFF", "toast": "#283F32", "selection": "#DDE7D7",
}
DARK = {
    "paper": "#202620", "side": "#191F1A", "panel": "#242C25", "ink": "#E9EDE5",
    "muted": "#A3AD9F", "faint": "#8E9A89", "line": "#374136", "hover": "#2A342A",
    "green": "#AFCBA3", "green_hover": "#C2D8B7", "soft": "#344631", "green_text": "#BCD3B1",
    "white": "#FFFFFF", "red": "#E8A28B", "red_soft": "#4B332B", "amber": "#D0B479",
    "field": "#293129", "toast": "#DDE8D5", "selection": "#43573A",
}
VIEWS = {"all": ("Všechny úkoly", "list"), "today": ("Dnes", "sun"), "upcoming": ("Nadcházející", "calendar"),
         "important": ("Důležité", "star"), "completed": ("Splněné", "checkcircle")}
SORTS = ("Vlastní pořadí", "Termín", "Priorita", "Nejnovější", "A až Z")
MONTHS = ("Leden", "Únor", "Březen", "Duben", "Květen", "Červen", "Červenec", "Srpen", "Září", "Říjen", "Listopad", "Prosinec")
MONTHS_SHORT = ("led", "úno", "bře", "dub", "kvě", "čer", "čvc", "srp", "zář", "říj", "lis", "pro")
WEEKDAYS = ("Po", "Út", "St", "Čt", "Pá", "So", "Ne")


def draw_icon(canvas, name, x, y, color, size=18, width=1.5):
    """A small consistent set of line icons, drawn at the current display scale."""
    s = size / 24
    line = lambda points, **kw: canvas.create_line(*[v * s + (x if i % 2 == 0 else y) for i, v in enumerate(points)], fill=color, width=width, capstyle=tk.ROUND, joinstyle=tk.ROUND, **kw)
    box = lambda a, b, c, d: canvas.create_rectangle(x+a*s, y+b*s, x+c*s, y+d*s, outline=color, width=width)
    oval = lambda a, b, c, d: canvas.create_oval(x+a*s, y+b*s, x+c*s, y+d*s, outline=color, width=width)
    if name == "plus":
        line([12, 5, 12, 19]); line([5, 12, 19, 12])
    elif name == "search":
        oval(4, 3, 16, 15); line([15, 14, 21, 20])
    elif name in ("check", "checkcircle"):
        if name == "checkcircle": oval(2, 2, 22, 22)
        line([6, 12, 10, 16, 18, 7])
    elif name == "list":
        for row in (5, 12, 19):
            box(3, row-1, 5, row+1); line([9, row, 21, row])
    elif name == "sun":
        oval(7, 7, 17, 17)
        for angle in range(0, 360, 45):
            a = math.radians(angle)
            line([12+8*math.cos(a), 12+8*math.sin(a), 12+11*math.cos(a), 12+11*math.sin(a)])
    elif name == "calendar":
        box(3, 5, 21, 21); line([3, 10, 21, 10]); line([8, 2, 8, 7]); line([16, 2, 16, 7]); box(7, 14, 9, 16)
    elif name == "star":
        points=[]
        for i in range(10):
            a = math.radians(-90+i*36); r = 10 if i%2 == 0 else 4.8
            points.extend((x+(12+r*math.cos(a))*s, y+(12+r*math.sin(a))*s))
        canvas.create_polygon(points, outline=color, fill="", width=width, joinstyle=tk.ROUND)
    elif name == "moon":
        line([17, 3, 12, 4, 8, 8, 8, 14, 12, 18, 18, 18, 21, 15, 20, 20, 14, 22, 7, 19, 3, 14, 3, 8, 7, 3, 12, 2, 17, 3], smooth=True)
    elif name == "close":
        line([6, 6, 18, 18]); line([18, 6, 6, 18])
    elif name == "left": line([15, 5, 8, 12, 15, 19])
    elif name == "right": line([9, 5, 16, 12, 9, 19])
    elif name == "more":
        for v in (5, 12, 19): canvas.create_oval(x+(v-1)*s, y+11*s, x+(v+1)*s, y+13*s, fill=color, outline="")
    elif name == "trash":
        line([3, 6, 21, 6]); line([9, 3, 15, 3]); line([6, 6, 7, 21, 17, 21, 18, 6]); line([10, 10, 10, 17]); line([14, 10, 14, 17])
    elif name == "settings":
        for row, center in ((5, 8), (12, 16), (19, 10)):
            line([3, row, 21, row]); canvas.create_rectangle(x+(center-2)*s, y+(row-2)*s, x+(center+2)*s, y+(row+2)*s, fill=canvas["bg"], outline=color, width=width)
    elif name == "note":
        box(5, 3, 19, 21); line([8, 8, 16, 8]); line([8, 12, 16, 12]); line([8, 16, 13, 16])
    elif name == "grip":
        for cx in (8, 15):
            for cy in (6, 12, 18): canvas.create_oval(x+cx*s, y+cy*s, x+(cx+1)*s, y+(cy+1)*s, fill=color, outline=color)
    elif name == "repeat":
        line([4, 9, 4, 5, 19, 5, 22, 8]); line([17, 8, 22, 8, 22, 3]); line([20, 15, 20, 19, 5, 19, 2, 16]); line([7, 16, 2, 16, 2, 21])


class IconButton(tk.Canvas):
    def __init__(self, parent, app, icon, command, *, bg=None, color=None, size=30, tip=""):
        self.app, self.icon, self.command = app, icon, command
        self.base_bg, self.color = bg or app.p["paper"], color or app.p["muted"]
        self.size = size
        super().__init__(parent, width=size, height=size, bg=self.base_bg, highlightthickness=0, bd=0, cursor="hand2", takefocus=1)
        self.bind("<Enter>", lambda _: self.paint(True))
        self.bind("<Leave>", lambda _: self.paint())
        self.bind("<Button-1>", lambda _: command())
        self.bind("<Return>", lambda _: command())
        self.bind("<space>", lambda _: command())
        self.bind("<FocusIn>", lambda _: self.paint(True))
        self.bind("<FocusOut>", lambda _: self.paint())
        if tip:
            self.bind("<Enter>", lambda _: self._tip(tip), add=True)
            self.bind("<Leave>", lambda _: app.hide_tip(), add=True)
        self.paint()

    def _tip(self, tip):
        self.app.show_tip(self, tip)

    def paint(self, hover=False):
        self.delete("all")
        self.configure(bg=self.app.p["hover"] if hover else self.base_bg)
        draw_icon(self, self.icon, (self.size-18)/2, (self.size-18)/2, self.color)


class ScrollFrame(tk.Frame):
    def __init__(self, parent, app, bg=None):
        super().__init__(parent, bg=bg or app.p["paper"])
        color = bg or app.p["paper"]
        self.canvas = tk.Canvas(self, bg=color, bd=0, highlightthickness=0)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview, style="Focus.Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=self._scroll)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=color)
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window, width=e.width))

    def _scroll(self, first, last):
        self.bar.set(first, last)
        if float(first) > 0 or float(last) < 1:
            if not self.bar.winfo_ismapped(): self.bar.pack(side="right", fill="y")
        else:
            self.bar.pack_forget()

    def wheel(self, event):
        if self.canvas.bbox("all") and self.inner.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(-int(event.delta / 120), "units")


class ToDoListApp(tk.Tk):
    def __init__(self, directory=APP_DIRECTORY, *, hidden=False, desktop=True):
        super().__init__()
        self.withdraw()
        self.title(APP_NAME)
        self.brand_icon = tk.PhotoImage(width=32, height=32)
        self.brand_icon.put("#355D49", to=(0, 0, 32, 32))
        for x in range(8, 14):
            y = x+6
            self.brand_icon.put("#FFFFFF", to=(x, y, x+2, y+3))
        for x in range(14, 25):
            y = 33-x
            self.brand_icon.put("#FFFFFF", to=(x, y, x+2, y+3))
        self.iconphoto(True, self.brand_icon)
        self.minsize(1060, 700)
        self.geometry("1280x830")
        try:
            self.store = TaskStore(Path(directory))
        except StoreError as error:
            messagebox.showerror("Uložené úkoly se nepodařilo načíst", str(error), parent=self)
            self.destroy()
            raise SystemExit(1)
        self.view = "all"
        self.category = ""
        self.on_date = ""
        self.selected_id = ""
        self.search = tk.StringVar()
        self.sort = tk.StringVar(value="Vlastní pořadí")
        self.priority = tk.StringVar(value="Všechny priority")
        self.quick = tk.StringVar()
        self.quick_due = ""
        self.editor_job = None
        self.dirty = False
        self.editor_building = False
        self.tip = None
        self.page_size = 80
        self.today = date.today()
        self.calendar_month = self.today.replace(day=1)
        self.celebration = None
        self._last_reminder_check = None
        self._delivered = set()
        self._tick_job = None
        self._desktop_job = None
        self._shutting_down = False
        self.instance_guard = None
        self._hidden_start = hidden
        self.tray = DesktopBridge(directory, RESOURCE_DIRECTORY / "assets" / "todo.ico") if desktop else None
        if self.tray:
            self.tray.enabled = self.store.settings.get("notifications_enabled", True)
            self.tray.start()
        self._build()
        self.search.trace_add("write", lambda *_: self.render_tasks())
        self.sort.trace_add("write", lambda *_: self.render_tasks())
        self.priority.trace_add("write", lambda *_: self.render_tasks())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind_all("<Control-n>", self.focus_quick)
        self.bind_all("<Control-f>", self.focus_search)
        self.bind_all("<Control-z>", self.undo_shortcut)
        self.bind_all("<Control-s>", lambda _: self.save_editor(explicit=True) and "break")
        self.bind_all("<Control-q>", lambda _: self.quit_app() or "break")
        self.bind_all("<Escape>", self.escape)
        self.bind_all("<MouseWheel>", self.wheel)
        self._tick_job = self.after(1000, self.tick)
        if self.tray: self._desktop_job = self.after(250, self.process_desktop_events)
        self.update_idletasks()
        self.geometry(f"1280x830+{max(0, (self.winfo_screenwidth()-1280)//2)}+{max(0, (self.winfo_screenheight()-870)//2)}")
        if not hidden: self.deiconify()

    @property
    def p(self):
        return DARK if self.store.settings.get("theme") == "dark" else LIGHT

    def label(self, parent, text="", *, size=10, color=None, bg=None, bold=False, font=None, **kwargs):
        return tk.Label(parent, text=text, font=font or ("Segoe UI", size, "bold" if bold else "normal"),
                        fg=color or self.p["ink"], bg=bg or parent["bg"], bd=0, **kwargs)

    def button(self, parent, text, command, *, primary=False, small=False, bg=None, color=None):
        normal = self.p["green"] if primary else (bg or parent["bg"])
        foreground = (self.p["paper"] if self.p is DARK else "white") if primary else (color or self.p["muted"])
        return tk.Button(parent, text=text, command=command, font=("Segoe UI", 10 if small else 11, "bold" if primary else "normal"),
                         bg=normal, fg=foreground, activebackground=self.p["green_hover"] if primary else self.p["hover"],
                         activeforeground=foreground, bd=0, relief="flat", highlightthickness=0, cursor="hand2", padx=14 if small else 18, pady=7 if small else 10)

    def entry(self, parent, variable=None, *, font_size=11, bg=None):
        return tk.Entry(parent, textvariable=variable, font=("Segoe UI", font_size), bg=bg or self.p["field"],
                        fg=self.p["ink"], insertbackground=self.p["green"], relief="flat", bd=0,
                        highlightthickness=1, highlightbackground=self.p["line"], highlightcolor=self.p["green"],
                        selectbackground=self.p["selection"], selectforeground=self.p["ink"])

    def combo(self, parent, variable, values, width=16):
        widget = ttk.Combobox(parent, textvariable=variable, values=list(values), state="readonly", width=width, style="Focus.TCombobox", font=("Segoe UI", 10))
        return widget

    def _build(self):
        self.hide_tip()
        self.celebration = None
        for child in self.winfo_children():
            if not isinstance(child, tk.Toplevel): child.destroy()
        p = self.p
        self.configure(bg=p["paper"])
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Focus.TCombobox", fieldbackground=p["field"], background=p["panel"], foreground=p["ink"], arrowcolor=p["muted"], bordercolor=p["line"], lightcolor=p["line"], darkcolor=p["line"], padding=(8, 5), borderwidth=1)
        style.map("Focus.TCombobox", fieldbackground=[("readonly", p["field"])], foreground=[("readonly", p["ink"])], selectbackground=[("readonly", p["field"])], selectforeground=[("readonly", p["ink"])], background=[("active", p["hover"])])
        style.configure("Focus.Vertical.TScrollbar", background=p["line"], troughcolor=p["paper"], bordercolor=p["paper"], arrowcolor=p["muted"], width=9, arrowsize=9, relief="flat")
        self.option_add("*TCombobox*Listbox.background", p["field"])
        self.option_add("*TCombobox*Listbox.foreground", p["ink"])
        self.option_add("*TCombobox*Listbox.selectBackground", p["soft"])
        self.option_add("*TCombobox*Listbox.selectForeground", p["ink"])
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.sidebar = tk.Frame(self, bg=p["side"], width=228)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(5, weight=1)
        self._build_sidebar()
        self.main = tk.Frame(self, bg=p["paper"])
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(5, weight=1)
        self._build_main()
        self.detail = tk.Frame(self, bg=p["panel"], width=320, highlightthickness=1, highlightbackground=p["line"])
        self.detail.grid_propagate(False)
        self.toast_frame = None
        self.render_tasks()
        if self.selected_id and self.store.find(self.selected_id): self.build_editor()

    def _build_sidebar(self):
        p = self.p
        brand = tk.Frame(self.sidebar, bg=p["side"])
        brand.grid(row=0, column=0, sticky="ew", padx=24, pady=(31, 26))
        mark = tk.Canvas(brand, width=30, height=30, bg=p["green"], highlightthickness=0)
        mark.pack(side="left")
        draw_icon(mark, "check", 4, 3, p["paper"] if p is DARK else p["white"], 23, 2)
        self.label(brand, "To-do list", size=15, bold=True).pack(side="left", padx=10)
        self.button(self.sidebar, "+   Nový úkol", self.focus_quick, primary=True).grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 25))
        self.nav = tk.Frame(self.sidebar, bg=p["side"])
        self.nav.grid(row=2, column=0, sticky="ew", padx=12)
        self.nav_buttons = {}
        for key, (text, icon) in VIEWS.items():
            row = tk.Frame(self.nav, bg=p["side"], cursor="hand2", height=39)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)
            image = tk.Canvas(row, width=22, height=24, bg=p["side"], highlightthickness=0)
            image.pack(side="left", padx=(13, 10))
            draw_icon(image, icon, 2, 3, p["muted"])
            title = self.label(row, text, size=11)
            title.pack(side="left")
            count = self.label(row, "", size=9, color=p["muted"])
            count.pack(side="right", padx=14)
            for widget in (row, image, title, count):
                widget.bind("<Button-1>", lambda _, v=key: self.set_view(v))
            self.nav_buttons[key] = (row, image, title, count)
        lists = tk.Frame(self.sidebar, bg=p["side"])
        lists.grid(row=3, column=0, sticky="ew", padx=25, pady=(30, 0))
        self.label(lists, "SEZNAMY", size=8, bold=True, color=p["faint"]).pack(anchor="w", pady=(0, 12))
        self.category_buttons = {}
        colors = ("#789083", "#C29C73", "#939B70", "#8798A2")
        categories = {**CATEGORIES, **{task.category: task.category for task in self.store.tasks if task.category not in CATEGORIES}}
        for i, (key, title) in enumerate(categories.items()):
            row = tk.Frame(lists, bg=p["side"], cursor="hand2", height=32)
            row.pack(fill="x")
            row.pack_propagate(False)
            dot = tk.Canvas(row, width=10, height=12, bg=p["side"], highlightthickness=0)
            dot.pack(side="left", padx=(0, 12))
            dot.create_oval(1, 3, 8, 10, fill=colors[i%4], outline="")
            name = self.label(row, title, size=10, color=p["muted"])
            name.pack(side="left")
            number = self.label(row, "", size=9, color=p["faint"])
            number.pack(side="right")
            for widget in (row, dot, name, number): widget.bind("<Button-1>", lambda _, c=key: self.set_view("all", c))
            self.category_buttons[key] = (name, number)
        bottom = tk.Frame(self.sidebar, bg=p["side"])
        bottom.grid(row=6, column=0, sticky="ew", padx=25, pady=(18, 22))
        tk.Frame(bottom, height=1, bg=p["line"]).pack(fill="x", pady=(0, 18))
        self.progress_title = self.label(bottom, "DNEŠNÍ PŘEHLED", size=8, color=p["muted"], bold=True)
        self.progress_title.pack(anchor="w")
        self.completed_total = self.label(bottom, "", size=13, bold=True, color=p["green_text"])
        self.completed_total.pack(anchor="w", pady=(6, 1))
        self.progress_text = self.label(bottom, "", size=10)
        self.progress_text.pack(anchor="w", pady=(6, 10))
        self.progress = tk.Canvas(bottom, height=3, width=178, bg=p["line"], highlightthickness=0)
        self.progress.pack(fill="x")
        self.progress.bind("<Configure>", lambda _: self.update_counts())
        profile = tk.Frame(bottom, bg=p["side"])
        profile.pack(fill="x", pady=(22, 0))
        name = str(self.store.settings.get("name", "Moje úkoly")) or "Moje úkoly"
        badge = self.label(profile, name[0].upper(), size=10, bg=p["soft"], color=p["green_text"], width=3, height=2, bold=True)
        badge.pack(side="left")
        self.label(profile, name, size=10).pack(side="left", padx=9)
        IconButton(profile, self, "settings", self.show_settings, bg=p["side"], tip="Nastavení").pack(side="right")

    def _build_main(self):
        p = self.p
        utility = tk.Frame(self.main, bg=p["paper"])
        utility.grid(row=0, column=0, sticky="ew", padx=43, pady=(27, 0))
        self.label(utility, "MOJE ÚKOLY", size=8, color=p["muted"], bold=True).pack(side="left")
        IconButton(utility, self, "sun" if p is DARK else "moon", self.toggle_theme, tip="Světlý / tmavý režim").pack(side="right")
        today = date.today()
        self.button(utility, f"{WEEKDAYS[today.weekday()]} {today.day}. {MONTHS_SHORT[today.month-1]}", self.show_calendar, small=True).pack(side="right", padx=8)
        header = tk.Frame(self.main, bg=p["paper"])
        header.grid(row=1, column=0, sticky="ew", padx=43, pady=(34, 25))
        self.title_label = self.label(header, "Všechny úkoly", font=("Georgia", 30), anchor="w")
        self.title_label.pack(fill="x")
        self.subtitle = self.label(header, "", size=10, color=p["muted"], anchor="w")
        self.subtitle.pack(fill="x", pady=(11, 0))
        self.composer = tk.Frame(self.main, bg=p["field"], highlightthickness=1, highlightbackground=p["line"])
        self.composer.grid(row=2, column=0, sticky="ew", padx=43, pady=(0, 25))
        self.composer.grid_columnconfigure(1, weight=1)
        plus = tk.Canvas(self.composer, width=22, height=28, bg=p["field"], highlightthickness=0)
        plus.grid(row=0, column=0, padx=(15, 10))
        draw_icon(plus, "plus", 1, 5, p["green"])
        self.quick_entry = self.entry(self.composer, self.quick, bg=p["field"])
        self.quick_entry.configure(highlightthickness=0)
        self.quick_entry.grid(row=0, column=1, sticky="ew", pady=17)
        self.quick_placeholder = self.label(self.composer, "Přidat úkol…", size=11, bg=p["field"], color=p["faint"], cursor="xterm")
        self.quick_placeholder.place(in_=self.quick_entry, x=2, y=0)
        self.quick_placeholder.bind("<Button-1>", lambda _: self.quick_entry.focus_set())
        self.quick_entry.bind("<FocusIn>", lambda _: self.quick_placeholder.place_forget())
        self.quick_entry.bind("<FocusOut>", lambda _: self.update_quick_placeholder())
        self.quick_entry.bind("<Return>", self.add_task)
        if not hasattr(self, "quick_trace"):
            self.quick_trace = self.quick.trace_add("write", lambda *_: self.update_quick_placeholder())
        self.quick_date = IconButton(self.composer, self, "calendar", self.quick_calendar, bg=p["field"], tip="Nastavit termín")
        self.quick_date.grid(row=0, column=2, padx=5)
        self.add_button = self.button(self.composer, "Přidat úkol", self.add_task, primary=True, small=True)
        self.add_button.grid(row=0, column=3, padx=(7, 9), pady=9)
        tools = tk.Frame(self.main, bg=p["paper"])
        tools.grid(row=3, column=0, sticky="ew", padx=43, pady=(0, 21))
        tools.grid_columnconfigure(0, weight=1)
        search_box = tk.Frame(tools, bg=p["paper"])
        search_box.grid(row=0, column=0, sticky="ew", padx=(0, 16))
        icon = tk.Canvas(search_box, width=22, height=27, bg=p["paper"], highlightthickness=0)
        icon.pack(side="left")
        draw_icon(icon, "search", 1, 4, p["faint"], 17)
        self.search_entry = self.entry(search_box, self.search, font_size=10, bg=p["paper"])
        self.search_entry.configure(highlightthickness=0, width=12)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self.search_placeholder = self.label(search_box, "Hledat úkoly", size=10, color=p["faint"], cursor="xterm")
        self.search_placeholder.place(in_=self.search_entry, x=0, y=0)
        self.search_placeholder.bind("<Button-1>", lambda _: self.search_entry.focus_set())
        self.search_entry.bind("<FocusIn>", lambda _: self.search_placeholder.place_forget())
        self.search_entry.bind("<FocusOut>", lambda _: self.update_search_placeholder())
        self.combo(tools, self.priority, ("Všechny priority", "Vysoká", "Střední", "Nízká"), width=12).grid(row=0, column=1, padx=(0, 8))
        self.combo(tools, self.sort, SORTS, width=14).grid(row=0, column=2)
        heading = tk.Frame(self.main, bg=p["paper"])
        heading.grid(row=4, column=0, sticky="ew", padx=43)
        self.section_label = self.label(heading, "ÚKOLY", size=8, color=p["muted"], bold=True)
        self.section_label.pack(side="left", pady=(0, 13))
        self.clear_filter = self.button(heading, "Zrušit filtry", self.reset_filters, small=True)
        self.list = ScrollFrame(self.main, self)
        self.list.grid(row=5, column=0, sticky="nsew", padx=(37, 32), pady=(0, 5))
        footer = tk.Frame(self.main, bg=p["paper"])
        footer.grid(row=6, column=0, sticky="ew", padx=43, pady=(14, 22))
        tk.Frame(footer, height=1, bg=p["line"]).pack(fill="x", pady=(0, 13))
        self.save_status = self.label(footer, "Uloženo v tomto počítači", size=9, color=p["faint"])
        self.save_status.pack(side="left")
        self.label(footer, "Ctrl N  Nový úkol     ·     Ctrl F  Hledat", size=9, color=p["faint"]).pack(side="right")

    def update_quick_placeholder(self):
        if not hasattr(self, "quick_entry") or not self.quick_entry.winfo_exists(): return
        if self.quick.get() or self.focus_get() == self.quick_entry:
            self.quick_placeholder.place_forget()
        else:
            text = f"Přidat úkol · {self.pretty_due(self.quick_due)}…" if self.quick_due else "Přidat úkol…"
            self.quick_placeholder.configure(text=text)
            self.quick_placeholder.place(in_=self.quick_entry, x=2, y=0)

    def update_search_placeholder(self):
        if self.search.get() or self.focus_get() == self.search_entry: self.search_placeholder.place_forget()
        else: self.search_placeholder.place(in_=self.search_entry, x=0, y=0)

    def focus_quick(self, _=None):
        if self.celebration: self.dismiss_celebration()
        self.quick_entry.focus_set()
        return "break"

    def focus_search(self, _=None):
        self.search_entry.focus_set()
        self.search_entry.select_range(0, "end")
        return "break"

    def escape(self, _=None):
        if self.celebration: self.dismiss_celebration()
        elif self.search.get(): self.search.set("")
        elif self.selected_id: self.close_editor()
        else: self.focus_quick()
        return "break"

    def wheel(self, event):
        widget = event.widget
        # Only scroll the pane under the pointer; preserve native Text scrolling.
        if isinstance(widget, (tk.Text, ttk.Combobox)): return
        while widget:
            if widget is self.detail:
                if hasattr(self, "editor_scroll"): self.editor_scroll.wheel(event)
                return
            if widget is self.list:
                self.list.wheel(event)
                return
            widget = getattr(widget, "master", None)

    def set_view(self, view, category="", on_date=""):
        if not self.save_editor(): return
        self.view, self.category, self.on_date = view, category, on_date
        self.selected_id = ""
        self.detail.grid_forget()
        self.page_size = 80
        self.list.canvas.yview_moveto(0)
        self.render_tasks()

    def reset_filters(self):
        self.search.set("")
        self.priority.set("Všechny priority")
        if self.on_date:
            self.on_date = ""
            self.render_tasks()

    def visible_tasks(self):
        priority = next((key for key, title in PRIORITIES.items() if title == self.priority.get()), "")
        tasks = self.store.visible(self.view, search=self.search.get(), category=self.category, priority=priority, sort=self.sort.get(), on_date=self.on_date, include_completed=self.view in ("all", "today"))
        return sorted(tasks, key=lambda task: task.completed)

    def update_counts(self):
        if not hasattr(self, "nav_buttons"): return
        p = self.p
        for key, (row, icon, label, count) in self.nav_buttons.items():
            selected = self.view == key and not self.category and not self.on_date
            bg = p["soft"] if selected else p["side"]
            fg = p["green_text"] if selected else p["muted"]
            row.configure(bg=bg)
            icon.configure(bg=bg); icon.delete("all")
            draw_icon(icon, VIEWS[key][1], 2, 3, fg)
            label.configure(bg=bg, fg=fg, font=("Segoe UI", 11, "bold" if selected else "normal"))
            number = len(self.store.visible(key))
            count.configure(text=str(number) if number else "", bg=bg, fg=fg)
        for key, (name, number) in self.category_buttons.items():
            name.configure(fg=p["green_text"] if key == self.category else p["muted"], font=("Segoe UI", 10, "bold" if key == self.category else "normal"))
            number.configure(text=str(sum(not t.completed and t.category == key for t in self.store.tasks)) or "")
        today = date.today().isoformat()
        done = sum(t.completed and t.completed_at.startswith(today) for t in self.store.tasks)
        due = sum(1 for t in self.store.tasks if not t.completed and t.due_date and t.due_date <= today)
        self.progress_text.configure(text=f"Dnes splněno: {done} · Zbývá: {due}")
        total = sum(task.completed for task in self.store.tasks)
        self.completed_total.configure(text=f"Splněno celkem: {total}")
        self.progress.delete("all")
        if done:
            self.progress.create_rectangle(0, 0, max(3, self.progress.winfo_width()*done/max(1, done+due)), 4, fill=p["green"], outline="")

    def render_tasks(self):
        if not hasattr(self, "list"): return
        self.update_counts()
        tasks = self.visible_tasks()
        title = CATEGORIES.get(self.category, self.category) if self.category else VIEWS[self.view][0]
        if self.on_date:
            selected = date.fromisoformat(self.on_date)
            title = f"{selected.day}. {selected.month}. {selected.year}"
        self.title_label.configure(text=title)
        total = len(tasks)
        active = sum(not task.completed for task in tasks)
        finished = total - active
        overdue = sum(1 for t in tasks if not t.completed and t.due_date and t.due_date < date.today().isoformat())
        if self.view == "completed": subtitle = f"Splněné úkoly: {total}"
        elif self.search.get(): subtitle = f"Nalezeno: {total} · „{self.search.get()}“"
        else: subtitle = f"K dokončení: {active}  ·  Splněno: {finished}" + (f"  ·  Po termínu: {overdue}" if overdue else "")
        self.subtitle.configure(text=subtitle)
        self.section_label.configure(text=f"{'SPLNĚNO' if self.view == 'completed' else 'ÚKOLY'}    {total:02d}")
        if self.search.get() or self.priority.get() != "Všechny priority" or self.on_date:
            self.clear_filter.pack(side="right", pady=(0, 5))
        else: self.clear_filter.pack_forget()
        for child in self.list.inner.winfo_children(): child.destroy()
        self.row_widgets = {}
        if not tasks:
            self.empty_state()
        else:
            completed_heading = False
            for task in tasks[:self.page_size]:
                if task.completed and self.view != "completed" and not completed_heading:
                    self.label(self.list.inner, f"SPLNĚNO    {finished:02d}", size=8, color=self.p["faint"], bold=True, anchor="w").pack(fill="x", padx=7, pady=(25, 10))
                    completed_heading = True
                self.task_row(task)
            if total > self.page_size:
                self.button(self.list.inner, f"Zobrazit další úkoly: {min(80, total-self.page_size)}", self.load_more, small=True).pack(pady=18)
        self.update_search_placeholder()

    def load_more(self):
        self.page_size += 80
        self.render_tasks()

    def empty_state(self):
        p = self.p
        box = tk.Frame(self.list.inner, bg=p["paper"])
        box.pack(fill="both", expand=True, pady=(63, 50))
        drawing = tk.Canvas(box, width=116, height=100, bg=p["paper"], highlightthickness=0)
        drawing.pack()
        drawing.create_rectangle(27, 12, 89, 86, fill=p["panel"], outline=p["line"], width=1)
        drawing.create_line(42, 34, 49, 41, 61, 27, fill=p["green"], width=2, capstyle=tk.ROUND)
        for y, length in ((54, 29), (64, 37), (74, 21)):
            drawing.create_line(40, y, 40+length, y, fill=p["line"], width=2)
        filtered = bool(self.search.get() or self.priority.get() != "Všechny priority" or self.on_date)
        if filtered: title, copy = "Žádné odpovídající úkoly", "Zkus jiné hledání nebo zruš filtry."
        elif self.view == "today": title, copy = "Dnes nemáš nic naplánováno", "Tady uvidíš dnešní úkoly a úkoly po termínu."
        elif self.view == "upcoming": title, copy = "Volný výhled", "Nastav úkolu termín a objeví se tady."
        elif self.view == "important": title, copy = "To nejdůležitější na jednom místě", "Označ úkol hvězdičkou a objeví se tady."
        elif self.view == "completed": title, copy = "Tady bude vidět hotová práce", "Splněné úkoly tady zůstanou uložené."
        else: title, copy = "Čistý seznam", "Přidej první úkol a dej svému dni jasný plán."
        self.label(box, title, font=("Georgia", 20)).pack(pady=(17, 9))
        self.label(box, copy, size=10, color=p["muted"], wraplength=390, justify="center").pack(padx=22)
        if filtered: self.button(box, "Zrušit filtry", self.reset_filters, small=True).pack(pady=19)
        elif self.view != "completed": self.button(box, "+   Přidat úkol", self.focus_quick, small=True, color=p["green_text"]).pack(pady=19)

    def pretty_due(self, iso):
        if not iso: return "Bez data"
        due = date.fromisoformat(iso)
        delta = (due-date.today()).days
        if delta == 0: return "Dnes"
        if delta == 1: return "Zítra"
        if delta == -1: return "Včera"
        return f"{due.day}. {MONTHS_SHORT[due.month-1]}" + (f" {due.year}" if due.year != date.today().year else "")

    def task_row(self, task):
        p = self.p
        bg = p["hover"] if task.id == self.selected_id else p["paper"]
        row = tk.Frame(self.list.inner, bg=bg)
        row.pack(fill="x", padx=(6, 11))
        self.row_widgets[task.id] = row
        tk.Frame(row, height=1, bg=p["line"]).pack(fill="x", side="bottom")
        body = tk.Frame(row, bg=bg)
        body.pack(fill="x", pady=16, padx=(0, 6))
        body.grid_columnconfigure(2, weight=1)
        grip = tk.Canvas(body, width=16, height=24, bg=bg, highlightthickness=0, cursor="fleur")
        grip.grid(row=0, column=0, rowspan=2, padx=(0, 8))
        draw_icon(grip, "grip", 0, 3, p["line"], 15)
        grip.bind("<ButtonPress-1>", lambda e, t=task: self.start_drag(t))
        grip.bind("<ButtonRelease-1>", lambda e, t=task: self.end_drag(t, e))
        check = tk.Canvas(body, width=23, height=27, bg=bg, highlightthickness=0, cursor="hand2", takefocus=1)
        check.grid(row=0, column=1, rowspan=2, sticky="n", padx=(0, 13), pady=1)
        check.create_rectangle(2, 3, 20, 21, outline=p["green"] if task.completed else p["faint"], fill=p["green"] if task.completed else bg, width=1)
        if task.completed: draw_icon(check, "check", 3, 3, p["paper"] if p is DARK else "white", 17, 1.6)
        check.bind("<Button-1>", lambda _, t=task: self.toggle_task(t.id))
        check.bind("<space>", lambda _, t=task: self.toggle_task(t.id))
        check.bind("<Return>", lambda _, t=task: self.toggle_task(t.id))
        check.bind("<FocusIn>", lambda _: check.configure(highlightthickness=1, highlightbackground=p["green"]))
        check.bind("<FocusOut>", lambda _: check.configure(highlightthickness=0))
        title = self.label(body, task.text, size=11, color=p["muted"] if task.completed else p["ink"], anchor="w", justify="left", cursor="hand2", font=("Segoe UI", 11, "overstrike" if task.completed else "normal"))
        title.grid(row=0, column=2, sticky="ew")
        title.bind("<Configure>", lambda e: title.configure(wraplength=max(120, e.width-5)))
        title.bind("<Button-1>", lambda _, t=task: self.open_task(t.id))
        title.configure(takefocus=1)
        title.bind("<Return>", lambda _, t=task: self.open_task(t.id))
        meta = tk.Frame(body, bg=bg)
        meta.grid(row=1, column=2, sticky="w", pady=(6, 0))
        category = CATEGORIES.get(task.category, task.category)
        self.label(meta, category, size=9, color=p["muted"]).pack(side="left", padx=(0, 12))
        if task.due_date:
            due_color = p["red"] if not task.completed and task.due_date < date.today().isoformat() else p["green_text"] if task.due_date == date.today().isoformat() else p["muted"]
            self.label(meta, self.pretty_due(task.due_date)+(f" · {task.due_time}" if task.due_time else ""), size=9, color=due_color).pack(side="left", padx=(0, 12))
        if task.priority == "high": self.label(meta, "Vysoká priorita", size=9, color=p["red"]).pack(side="left", padx=(0, 12))
        if task.subtasks:
            self.label(meta, f"Kroky: {sum(item['completed'] for item in task.subtasks)}/{len(task.subtasks)}", size=9, color=p["muted"]).pack(side="left", padx=(0, 10))
        if task.notes:
            note = tk.Canvas(meta, width=17, height=18, bg=bg, highlightthickness=0)
            note.pack(side="left", padx=(0, 8)); draw_icon(note, "note", 0, 2, p["faint"], 14)
        if task.repeat != "none":
            repeat = tk.Canvas(meta, width=17, height=18, bg=bg, highlightthickness=0)
            repeat.pack(side="left"); draw_icon(repeat, "repeat", 0, 2, p["faint"], 14)
        if task.timer_end and not task.completed:
            self.label(meta, countdown(task), size=9, color=p["green_text"]).pack(side="left", padx=(8, 0))
        star = IconButton(body, self, "star", lambda t=task: self.star_task(t.id), bg=bg, color=p["green"] if task.starred else p["faint"], tip="Zrušit důležitost" if task.starred else "Označit jako důležité")
        star.grid(row=0, column=3, rowspan=2, padx=(9, 5))
        more = IconButton(body, self, "more", lambda t=task: self.task_menu(t.id), bg=bg, color=p["faint"], tip="Možnosti úkolu")
        more.grid(row=0, column=4, rowspan=2)
        for widget in (row, body, title, meta): widget.bind("<Button-3>", lambda e, t=task: self.task_menu(t.id, e))

    def start_drag(self, task):
        if self.sort.get() != "Vlastní pořadí": self.toast("Pro přesouvání vyber Vlastní pořadí.")

    def end_drag(self, task, event):
        if self.sort.get() != "Vlastní pořadí" or not self.save_editor(): return
        for task_id, row in self.row_widgets.items():
            if row.winfo_rooty() <= event.y_root < row.winfo_rooty()+row.winfo_height():
                self.safe(lambda: self.store.reorder(task.id, task_id))
                self.render_tasks()
                return

    def add_task(self, _=None):
        text = self.quick.get().strip()
        if not text: self.focus_quick(); return "break"
        if not self.save_editor(): return "break"
        values = {"category": self.category or "Osobní", "due_date": self.quick_due}
        if self.view == "today" and not self.quick_due: values["due_date"] = date.today().isoformat()
        if self.on_date and not self.quick_due: values["due_date"] = self.on_date
        if self.view == "important": values["starred"] = True
        task = self.safe(lambda: self.store.add(text, **values))
        if task:
            self.quick.set(""); self.quick_due = ""
            if self.view == "completed" or (self.view == "upcoming" and task.due_date <= date.today().isoformat()): self.view = "all"
            self.search.set(""); self.priority.set("Všechny priority")
            self.render_tasks()
            self.toast("Úkol přidán", undo=True)
        self.focus_quick()
        return "break"

    def toggle_task(self, task_id):
        if not self.save_editor(): return
        task = self.store.find(task_id)
        was_done = task.completed
        if self.safe(lambda: self.store.toggle(task_id), success=True):
            if self.selected_id == task_id: self.build_editor()
            self.render_tasks()
            self.toast("Úkol vrácen mezi aktivní" if was_done else "Úkol splněn" + (" · Další opakování naplánováno" if task.repeat != "none" else ""), undo=True)
            if not was_done: self.show_celebration(task)

    def show_celebration(self, task):
        self.dismiss_celebration()
        quote_id, palette_id = next_celebration(self.store.settings.get("last_quote", -1), self.store.settings.get("last_palette", -1))
        self.safe(lambda: self.store.save_settings(last_quote=quote_id, last_palette=palette_id))
        background, ink, muted = PALETTES[palette_id]
        overlay = tk.Frame(self, bg=background)
        self.celebration = overlay
        overlay.place(x=0, y=0, relwidth=1, relheight=1)
        overlay.lift()
        content = tk.Frame(overlay, bg=background)
        content.place(relx=.5, rely=.47, anchor="center", relwidth=.72)
        mark = tk.Canvas(content, width=62, height=62, bg=background, highlightthickness=0)
        mark.pack(pady=(0, 28))
        mark.create_oval(2, 2, 59, 59, outline=muted, width=1)
        draw_icon(mark, "check", 14, 14, ink, 34, 2.2)
        name = str(self.store.settings.get("name", "")).strip()
        greeting = f"Hotovo, {vocative_name(name)}!" if name else "Úkol splněn!"
        self.label(content, greeting, font=("Georgia", 34), bg=background, color=ink).pack(pady=(0, 15))
        self.label(content, task.text, size=12, bg=background, color=muted, wraplength=650, justify="center").pack(pady=(0, 42))
        self.label(content, f"„{QUOTES[quote_id]}“", font=("Georgia", 20), bg=background, color=ink, wraplength=680, justify="center").pack(pady=(0, 31))
        total = sum(item.completed for item in self.store.tasks)
        self.label(content, f"Splněno celkem: {total}", size=11, bg=background, color=muted).pack(pady=(0, 26))
        button = tk.Button(content, text="Pokračovat", command=self.dismiss_celebration, font=("Segoe UI", 11, "bold"), bg=ink, fg=background, activebackground=muted, activeforeground=background, bd=0, cursor="hand2", padx=30, pady=13)
        button.pack()
        button.bind("<Return>", lambda _: self.dismiss_celebration())
        button.focus_set()
        self.label(overlay, "TO-DO LIST", size=9, bold=True, bg=background, color=muted).place(relx=.5, rely=1, y=-35, anchor="s")

    def dismiss_celebration(self):
        if self.celebration is not None:
            if self.celebration.winfo_exists(): self.celebration.destroy()
            self.celebration = None

    def star_task(self, task_id):
        if not self.save_editor(): return
        task = self.store.find(task_id)
        if self.safe(lambda: self.store.update(task_id, starred=not task.starred), success=True):
            self.render_tasks()
            if self.selected_id == task_id: self.build_editor()

    def delete_task(self, task_id):
        if not self.save_editor(): return
        if self.safe(lambda: self.store.delete(task_id), success=True):
            if self.selected_id == task_id:
                self.selected_id = ""; self.detail.grid_forget()
            self.render_tasks(); self.toast("Úkol smazán", undo=True)

    def task_menu(self, task_id, event=None):
        task = self.store.find(task_id)
        if task is None: return
        menu = tk.Menu(self, tearoff=False, bg=self.p["field"], fg=self.p["ink"], activebackground=self.p["soft"], activeforeground=self.p["ink"], relief="flat", bd=1, font=("Segoe UI", 10))
        menu.add_command(label="Otevřít detail", command=lambda: self.open_task(task_id))
        menu.add_command(label="Zrušit důležitost" if task.starred else "Označit jako důležité", command=lambda: self.star_task(task_id))
        menu.add_command(label="Vrátit mezi aktivní" if task.completed else "Splnit úkol", command=lambda: self.toggle_task(task_id))
        menu.add_separator()
        menu.add_command(label="Termín dnes", command=lambda: self.reschedule(task_id, date.today().isoformat()))
        menu.add_command(label="Termín zítra", command=lambda: self.reschedule(task_id, (date.today()+timedelta(days=1)).isoformat()))
        menu.add_command(label="Zrušit termín", command=lambda: self.reschedule(task_id, ""))
        menu.add_separator()
        menu.add_command(label="Smazat úkol", command=lambda: self.delete_task(task_id), foreground=self.p["red"])
        try: menu.tk_popup(event.x_root if event else self.winfo_pointerx(), event.y_root if event else self.winfo_pointery())
        finally: menu.grab_release()

    def reschedule(self, task_id, iso):
        if not self.save_editor(): return
        if self.safe(lambda: self.store.update(task_id, due_date=iso, due_time=""), success=True):
            self.render_tasks()
            if self.selected_id == task_id: self.build_editor()
            self.toast("Termín změněn", undo=True)

    def open_task(self, task_id):
        if not self.save_editor(): return
        self.selected_id = task_id
        self.build_editor()
        self.render_tasks()

    def close_editor(self):
        if not self.save_editor(): return
        self.selected_id = ""
        self.detail.grid_forget()
        self.render_tasks()

    def build_editor(self):
        task = self.store.find(self.selected_id)
        if not task: return
        self.editor_building = True
        self.dirty = False
        if self.editor_job: self.after_cancel(self.editor_job); self.editor_job = None
        for child in self.detail.winfo_children(): child.destroy()
        p = self.p
        self.detail.grid(row=0, column=2, sticky="nsew")
        self.detail.grid_columnconfigure(0, weight=1)
        self.detail.grid_rowconfigure(1, weight=1)
        top = tk.Frame(self.detail, bg=p["panel"])
        top.grid(row=0, column=0, sticky="ew", padx=22, pady=(23, 16))
        self.label(top, "DETAIL ÚKOLU", size=8, color=p["muted"], bold=True).pack(side="left")
        IconButton(top, self, "close", self.close_editor, bg=p["panel"], tip="Zavřít detail · Esc").pack(side="right")
        self.editor_scroll = ScrollFrame(self.detail, self, p["panel"])
        self.editor_scroll.grid(row=1, column=0, sticky="nsew", padx=(22, 16))
        panel = self.editor_scroll.inner
        self.edit_title = tk.Text(panel, height=2, wrap="word", font=("Segoe UI", 15, "bold"), bg=p["panel"], fg=p["ink"], insertbackground=p["green"], relief="flat", bd=0, padx=0, pady=4, undo=True, selectbackground=p["selection"], selectforeground=p["ink"])
        self.edit_title.pack(fill="x", pady=(0, 15))
        self.edit_title.insert("1.0", task.text)
        self.edit_title.edit_modified(False)
        self.edit_title.bind("<<Modified>>", self.text_changed)
        self.button(panel, "✓   Splněno" if task.completed else "Splnit úkol", lambda: self.toggle_task(task.id), primary=not task.completed, small=True).pack(fill="x", pady=(0, 25))
        self.edit_category = tk.StringVar(value=CATEGORIES.get(task.category, task.category))
        self.edit_priority = tk.StringVar(value=PRIORITIES[task.priority])
        self.edit_date = tk.StringVar(value=date.fromisoformat(task.due_date).strftime("%d.%m.%Y") if task.due_date else "")
        self.edit_time = tk.StringVar(value=task.due_time)
        self.edit_repeat = tk.StringVar(value=REPEATS[task.repeat])
        self.field_label(panel, "SEZNAM")
        categories = list(dict.fromkeys([*CATEGORIES.values(), *[CATEGORIES.get(t.category, t.category) for t in self.store.tasks]]))
        self.combo(panel, self.edit_category, categories).pack(fill="x", pady=(5, 18))
        self.field_label(panel, "TERMÍN")
        due_row = tk.Frame(panel, bg=p["panel"])
        due_row.pack(fill="x", pady=(5, 4))
        self.edit_date_entry = self.entry(due_row, self.edit_date, font_size=10)
        self.edit_date_entry.pack(side="left", fill="x", expand=True, ipady=8)
        IconButton(due_row, self, "calendar", lambda: self.show_calendar(self.editor_pick_date), bg=p["panel"], tip="Vybrat datum").pack(side="right", padx=(5, 0))
        self.label(panel, "DD.MM.RRRR · nepovinné", size=8, color=p["faint"]).pack(anchor="w", pady=(0, 12))
        time_row = tk.Frame(panel, bg=p["panel"])
        time_row.pack(fill="x", pady=(0, 18))
        self.label(time_row, "Čas", size=10, color=p["muted"]).pack(side="left")
        self.edit_time_entry = self.entry(time_row, self.edit_time, font_size=10)
        self.edit_time_entry.configure(width=8)
        self.edit_time_entry.pack(side="right", ipady=5)
        self.label(time_row, "24h · HH:MM", size=8, color=p["faint"]).pack(side="right", padx=8)
        timer_row = tk.Frame(panel, bg=p["panel"])
        timer_row.pack(fill="x", pady=(0, 18))
        self.button(timer_row, "Časovač…", self.show_timer, small=True, color=p["green_text"]).pack(side="left")
        self.timer_label = self.label(timer_row, countdown(task) if task.timer_end else "", size=9, color=p["muted"])
        self.timer_label.pack(side="right")
        self.field_label(panel, "PRIORITA")
        self.combo(panel, self.edit_priority, PRIORITIES.values()).pack(fill="x", pady=(5, 18))
        self.field_label(panel, "OPAKOVÁNÍ")
        self.combo(panel, self.edit_repeat, REPEATS.values()).pack(fill="x", pady=(5, 22))
        self.field_label(panel, "DÍLČÍ KROKY")
        checklist = tk.Frame(panel, bg=p["panel"])
        checklist.pack(fill="x", pady=(9, 6))
        for item in task.subtasks:
            step = tk.Frame(checklist, bg=p["panel"])
            step.pack(fill="x", pady=3)
            var = tk.BooleanVar(value=item["completed"])
            check = tk.Checkbutton(step, text=item["text"], variable=var, command=lambda i=item, v=var: self.toggle_subtask(i["id"], v.get()), font=("Segoe UI", 10, "overstrike" if item["completed"] else "normal"), bg=p["panel"], fg=p["muted"] if item["completed"] else p["ink"], selectcolor=p["field"], activebackground=p["panel"], activeforeground=p["ink"], anchor="w", wraplength=205, bd=0, highlightthickness=0, cursor="hand2")
            check.pack(side="left", fill="x", expand=True)
            IconButton(step, self, "close", lambda i=item: self.remove_subtask(i["id"]), bg=p["panel"], size=24, tip="Smazat krok").pack(side="right")
        self.subtask_entry = self.entry(panel, font_size=10)
        self.subtask_entry.pack(fill="x", ipady=7, pady=(3, 0))
        self.subtask_entry.bind("<Return>", self.add_subtask)
        self.button(panel, "+   Přidat krok", self.add_subtask, small=True, color=p["green_text"]).pack(anchor="w", pady=(2, 19))
        self.field_label(panel, "POZNÁMKY")
        self.edit_notes = tk.Text(panel, height=5, wrap="word", font=("Segoe UI", 10), bg=p["field"], fg=p["ink"], insertbackground=p["green"], relief="flat", bd=0, highlightthickness=1, highlightbackground=p["line"], highlightcolor=p["green"], padx=10, pady=9, undo=True, selectbackground=p["selection"], selectforeground=p["ink"])
        self.edit_notes.pack(fill="x", pady=(7, 8))
        self.edit_notes.insert("1.0", task.notes)
        self.edit_notes.edit_modified(False)
        self.edit_notes.bind("<<Modified>>", self.text_changed)
        self.editor_error = self.label(panel, "", size=9, color=p["red"], wraplength=265, justify="left")
        self.editor_error.pack(fill="x", pady=(0, 10))
        for variable in (self.edit_category, self.edit_priority, self.edit_date, self.edit_time, self.edit_repeat): variable.trace_add("write", self.mark_dirty)
        footer = tk.Frame(self.detail, bg=p["panel"])
        footer.grid(row=2, column=0, sticky="ew", padx=22, pady=18)
        self.editor_status = self.label(footer, "Změny uloženy", size=9, color=p["faint"])
        self.editor_status.pack(side="left")
        IconButton(footer, self, "trash", lambda: self.delete_task(task.id), bg=p["panel"], color=p["red"], tip="Smazat úkol · lze vrátit").pack(side="right")
        self.revert_button = self.button(footer, "Zahodit", self.revert_editor, small=True)
        self.editor_building = False

    def field_label(self, parent, text):
        self.label(parent, text, size=8, bold=True, color=self.p["muted"]).pack(anchor="w")

    def text_changed(self, event):
        if event.widget.edit_modified():
            self.mark_dirty()
            event.widget.edit_modified(False)

    def mark_dirty(self, *_):
        if self.editor_building: return
        self.dirty = True
        self.editor_status.configure(text="Upravuji…")
        self.revert_button.pack(side="right", padx=5)
        if self.editor_job: self.after_cancel(self.editor_job)
        self.editor_job = self.after(900, self.save_editor)

    def editor_values(self):
        title = self.edit_title.get("1.0", "end-1c").strip().replace("\n", " ")
        if not title: raise ValueError("Zadej název úkolu.")
        raw_date, raw_time = self.edit_date.get().strip(), self.edit_time.get().strip()
        due = ""
        if raw_date:
            parsed = None
            for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
                try: parsed = datetime.strptime(raw_date, fmt).date(); break
                except ValueError: pass
            if parsed is None: raise ValueError("Datum zadej ve formátu DD.MM.RRRR.")
            due = parsed.isoformat()
        if raw_time:
            if not due: raise ValueError("Nejprve vyber datum a potom přidej čas.")
            try: raw_time = datetime.strptime(raw_time, "%H:%M").strftime("%H:%M")
            except ValueError: raise ValueError("Čas zadej ve formátu HH:MM (24 hodin).")
        return dict(text=title, category=next((k for k, v in CATEGORIES.items() if v == self.edit_category.get()), self.edit_category.get()),
                    priority=next(k for k, v in PRIORITIES.items() if v == self.edit_priority.get()), due_date=due, due_time=raw_time,
                    repeat=next(k for k, v in REPEATS.items() if v == self.edit_repeat.get()), notes=self.edit_notes.get("1.0", "end-1c").strip())

    def save_editor(self, explicit=False):
        if self.editor_job: self.after_cancel(self.editor_job); self.editor_job = None
        if not self.selected_id or not self.dirty or self.editor_building: return True
        try: values = self.editor_values()
        except ValueError as error:
            self.editor_error.configure(text=str(error)); self.editor_status.configure(text="Neuloženo")
            if explicit: self.toast(str(error))
            return False
        if not self.safe(lambda: self.store.update(self.selected_id, **values), success=True): return False
        self.dirty = False
        self.editor_error.configure(text="")
        self.editor_status.configure(text="Změny uloženy")
        self.revert_button.pack_forget()
        self.render_tasks()
        return True

    def revert_editor(self):
        self.dirty = False
        self.build_editor()

    def editor_pick_date(self, iso):
        self.edit_date.set(date.fromisoformat(iso).strftime("%d.%m.%Y") if iso else "")
        if not iso: self.edit_time.set("")

    def add_subtask(self, _=None):
        text = self.subtask_entry.get().strip()
        if not text: self.subtask_entry.focus_set(); return "break"
        if not self.save_editor(): return "break"
        task = self.store.find(self.selected_id)
        items = copy.deepcopy(task.subtasks)
        from uuid import uuid4
        items.append({"id": str(uuid4()), "text": text, "completed": False})
        if self.safe(lambda: self.store.update(task.id, subtasks=items), success=True):
            self.build_editor(); self.render_tasks(); self.subtask_entry.focus_set()
        return "break"

    def toggle_subtask(self, subtask_id, completed):
        if not self.save_editor(): return
        task = self.store.find(self.selected_id)
        items = [{**item, "completed": completed if item["id"] == subtask_id else item["completed"]} for item in task.subtasks]
        if self.safe(lambda: self.store.update(task.id, subtasks=items), success=True): self.build_editor(); self.render_tasks()

    def remove_subtask(self, subtask_id):
        if not self.save_editor(): return
        task = self.store.find(self.selected_id)
        items = [item for item in task.subtasks if item["id"] != subtask_id]
        if self.safe(lambda: self.store.update(task.id, subtasks=items), success=True): self.build_editor(); self.render_tasks(); self.toast("Krok smazán", undo=True)

    def undo_shortcut(self, event=None):
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, tk.Text, ttk.Combobox)): return None
        self.undo()
        return "break"

    def undo(self):
        if not self.save_editor(): return
        label = self.safe(self.store.undo)
        if label:
            self.selected_id = ""; self.detail.grid_forget()
            self.render_tasks(); self.toast("Změna vrácena")
        else: self.toast("Žádná změna k vrácení")

    def safe(self, action, success=False):
        try:
            result = action()
            if hasattr(self, "save_status"): self.save_status.configure(text="Uloženo v tomto počítači", fg=self.p["faint"])
            return True if success else result
        except (StoreError, ValueError, OSError) as error:
            messagebox.showerror("Změnu se nepodařilo uložit", str(error), parent=self)
            if hasattr(self, "save_status"): self.save_status.configure(text="Změna neuložena", fg=self.p["red"])
            return False if success else None

    def toast(self, text, undo=False):
        if self.toast_frame and self.toast_frame.winfo_exists(): self.toast_frame.destroy()
        if hasattr(self, "toast_job"): self.after_cancel(self.toast_job)
        p = self.p
        self.toast_frame = tk.Frame(self.main, bg=p["toast"], padx=17, pady=11)
        self.toast_frame.place(relx=.5, rely=1, y=-66, anchor="s")
        self.label(self.toast_frame, text, size=10, color=p["paper"], bg=p["toast"]).pack(side="left")
        if undo:
            tk.Button(self.toast_frame, text="Vrátit", command=self.undo, font=("Segoe UI", 10, "bold"), bg=p["toast"], fg=p["paper"], activebackground=p["toast"], activeforeground=p["paper"], cursor="hand2", bd=0, padx=15).pack(side="left")
        self.toast_job = self.after(5500, self.toast_frame.destroy)

    def show_tip(self, widget, text):
        self.hide_tip()
        def show():
            if not widget.winfo_exists(): return
            self.tip = tk.Toplevel(self)
            self.tip.overrideredirect(True)
            self.tip.attributes("-topmost", True)
            self.label(self.tip, text, size=9, bg=self.p["toast"], color=self.p["paper"], padx=9, pady=6).pack()
            self.tip.update_idletasks()
            x = min(widget.winfo_rootx(), self.winfo_screenwidth()-self.tip.winfo_reqwidth()-15)
            self.tip.geometry(f"+{x}+{widget.winfo_rooty()+widget.winfo_height()+5}")
        self.tip_job = self.after(600, show)

    def hide_tip(self):
        if hasattr(self, "tip_job"):
            self.after_cancel(self.tip_job); del self.tip_job
        if self.tip and self.tip.winfo_exists(): self.tip.destroy()
        self.tip = None

    def quick_calendar(self):
        self.show_calendar(self.set_quick_date)

    def set_quick_date(self, iso):
        self.quick_due = iso
        self.update_quick_placeholder()
        self.focus_quick()

    def show_calendar(self, callback=None):
        p = self.p
        dialog = tk.Toplevel(self)
        dialog.title("Vybrat datum" if callback else "Kalendář")
        dialog.resizable(False, False)
        dialog.configure(bg=p["paper"])
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry(f"340x445+{self.winfo_rootx()+max(20, (self.winfo_width()-340)//2)}+{self.winfo_rooty()+100}")
        month = [date.today().replace(day=1)]
        self.label(dialog, "Vybrat datum" if callback else "Úkoly podle data", font=("Georgia", 19)).pack(anchor="w", padx=25, pady=(23, 17))
        top = tk.Frame(dialog, bg=p["paper"]); top.pack(fill="x", padx=20)
        title = self.label(top, "", size=11, bold=True); title.pack(side="left", padx=5)
        grid = tk.Frame(dialog, bg=p["paper"]); grid.pack(padx=20, pady=(15, 8))
        def choose(iso):
            dialog.destroy()
            if callback: callback(iso)
            else: self.set_view("all", on_date=iso)
        def change(delta):
            index = month[0].year*12+month[0].month-1+delta
            if not 1 <= index//12 <= 9999: return
            month[0] = date(index//12, index%12+1, 1); render()
        def render():
            for child in grid.winfo_children(): child.destroy()
            title.configure(text=f"{MONTHS[month[0].month-1]} {month[0].year}")
            for col, text in enumerate(WEEKDAYS):
                self.label(grid, text, size=9, color=p["faint"], width=4).grid(row=0, column=col, pady=(0, 8))
            pending = {task.due_date for task in self.store.tasks if not task.completed}
            for row, week in enumerate(calendar.monthcalendar(month[0].year, month[0].month), 1):
                for col, day in enumerate(week):
                    if not day: continue
                    iso = date(month[0].year, month[0].month, day).isoformat()
                    today = iso == date.today().isoformat()
                    button = tk.Button(grid, text=f"{day}" + ("·" if iso in pending else ""), width=3, height=1, font=("Segoe UI", 10), bd=0, bg=p["green"] if today else p["paper"], fg=(p["paper"] if p is DARK else "white") if today else p["ink"], activebackground=p["soft"], activeforeground=p["ink"], cursor="hand2", command=lambda d=iso: choose(d))
                    button.grid(row=row, column=col, padx=1, pady=3, ipady=3)
        IconButton(top, self, "right", lambda: change(1)).pack(side="right")
        IconButton(top, self, "left", lambda: change(-1)).pack(side="right", padx=3)
        render()
        bottom = tk.Frame(dialog, bg=p["paper"]); bottom.pack(fill="x", padx=20, pady=5)
        self.button(bottom, "Dnes", lambda: choose(date.today().isoformat()), small=True, color=p["green_text"]).pack(side="left")
        self.button(bottom, "Zítra", lambda: choose((date.today()+timedelta(days=1)).isoformat()), small=True).pack(side="left")
        self.button(bottom, "Bez data" if callback else "Všechny úkoly", lambda: choose(""), small=True).pack(side="right")
        dialog.bind("<Escape>", lambda _: dialog.destroy())

    def toggle_theme(self):
        if not self.save_editor(): return
        if self.safe(lambda: self.store.save_settings(theme="light" if self.p is DARK else "dark"), success=True): self._build()

    def show_timer(self):
        if not self.save_editor(): return
        task = self.store.find(self.selected_id)
        if task is None: return
        p = self.p
        dialog = tk.Toplevel(self)
        dialog.title("Časovač úkolu")
        dialog.configure(bg=p["paper"])
        dialog.resizable(False, False)
        dialog.transient(self); dialog.grab_set()
        dialog.geometry(f"400x335+{self.winfo_rootx()+190}+{self.winfo_rooty()+130}")
        body = tk.Frame(dialog, bg=p["paper"])
        body.pack(fill="both", expand=True, padx=28, pady=24)
        self.label(body, "Kolik času potřebuješ?", font=("Georgia", 20)).pack(anchor="w", pady=(0, 12))
        self.label(body, "Po zavření okna časovač pokračuje na pozadí.", size=10, color=p["muted"], wraplength=340).pack(anchor="w", pady=(0, 20))
        presets = tk.Frame(body, bg=p["paper"]); presets.pack(fill="x")
        def start(minutes):
            if self.start_timer(task.id, minutes): dialog.destroy()
        for label, minutes in (("10 minut", 10), ("1 hodina", 60), ("1 den", 1440)):
            self.button(presets, label, lambda m=minutes: start(m), small=True, bg=p["hover"]).pack(side="left", padx=(0, 7))
        custom = tk.Frame(body, bg=p["paper"]); custom.pack(fill="x", pady=(20, 17))
        self.label(custom, "Vlastní počet minut", size=10, color=p["muted"]).pack(side="left")
        value = tk.StringVar(value="60")
        entry = self.entry(custom, value); entry.configure(width=8)
        entry.pack(side="right", ipady=6)
        def custom_start():
            try:
                minutes = float(value.get().replace(",", "."))
                if not 1/60 <= minutes <= 525600: raise ValueError()
            except ValueError:
                self.toast("Zadej dobu od 1 sekundy do 365 dní.")
                return
            start(minutes)
        actions = tk.Frame(body, bg=p["paper"]); actions.pack(fill="x")
        self.button(actions, "Spustit časovač", custom_start, primary=True, small=True).pack(side="right")
        if task.timer_end:
            self.button(actions, "Zrušit časovač", lambda: self.cancel_timer(task.id, dialog), small=True).pack(side="left")
        if not self.store.settings.get("notifications_enabled", True):
            self.label(body, "Oznámení jsou vypnutá v nastavení.", size=9, color=p["red"]).pack(anchor="w", pady=(14, 0))
        dialog.bind("<Escape>", lambda _: dialog.destroy())
        dialog.bind("<Return>", lambda _: custom_start())

    def start_timer(self, task_id, minutes):
        if not self.save_editor(): return False
        if not 1/60 <= minutes <= 525600: return False
        now = datetime.now().replace(microsecond=0)
        end = now + timedelta(seconds=round(minutes*60))
        if self.safe(lambda: self.store.update(task_id, timer_started_at=now.isoformat(), timer_end=end.isoformat(), due_date=end.date().isoformat(), due_time=end.strftime("%H:%M"), completed=False, completed_at=""), success=True):
            if self.selected_id == task_id: self.build_editor()
            self.render_tasks()
            self.toast("Časovač běží. Okno můžeš zavřít.")
            return True
        return False

    def cancel_timer(self, task_id, dialog=None):
        if self.safe(lambda: self.store.update(task_id, timer_end="", timer_started_at="", due_date="", due_time=""), success=True):
            if dialog: dialog.destroy()
            if self.selected_id == task_id: self.build_editor()
            self.render_tasks()
            self.toast("Časovač zrušen", undo=True)

    def show_settings(self):
        if not self.save_editor(): return
        p = self.p
        dialog = tk.Toplevel(self)
        dialog.title("Nastavení")
        dialog.configure(bg=p["paper"])
        dialog.resizable(False, False)
        dialog.transient(self); dialog.grab_set()
        dialog.geometry(f"455x478+{self.winfo_rootx()+150}+{self.winfo_rooty()+100}")
        body = tk.Frame(dialog, bg=p["paper"]); body.pack(fill="both", expand=True, padx=30, pady=28)
        dialog.geometry(f"485x695+{self.winfo_rootx()+130}+{max(20, self.winfo_rooty()+35)}")
        self.label(body, "Nastavení", font=("Georgia", 23)).pack(anchor="w", pady=(0, 22))
        self.field_label(body, "TVOJE JMÉNO")
        name = tk.StringVar(value=self.store.settings.get("name", ""))
        self.entry(body, name).pack(fill="x", ipady=9, pady=(7, 20))
        self.field_label(body, "OZNÁMENÍ A POZADÍ")
        notifications = tk.BooleanVar(value=self.store.settings.get("notifications_enabled", True))
        background = tk.BooleanVar(value=self.store.settings.get("run_in_background", True))
        sound = tk.BooleanVar(value=self.store.settings.get("notification_sound", True))
        for label, variable in (("Posílat systémová oznámení", notifications), ("Zvuk oznámení", sound), ("Po zavření okna pokračovat na pozadí", background)):
            tk.Checkbutton(body, text=label, variable=variable, font=("Segoe UI", 10), bg=p["paper"], fg=p["ink"], selectcolor=p["field"], activebackground=p["paper"], activeforeground=p["ink"], bd=0, highlightthickness=0, anchor="w", cursor="hand2").pack(anchor="w", pady=4)
        lead_options = {"V termínu": "due", "Hodinu předem + v termínu": "hour", "Den předem + v termínu": "day", "Den i hodinu předem + v termínu": "both"}
        lead = tk.StringVar(value=next((title for title, value in lead_options.items() if value == self.store.settings.get("reminder_lead", "both")), list(lead_options)[-1]))
        self.combo(body, lead, lead_options).pack(fill="x", pady=(9, 7))
        self.label(body, "Časovač upozorní při doběhnutí. Úkol bez času v 9:00.\nAplikaci ukončíš přes ikonu u hodin nebo tlačítkem níže.", size=9, color=p["muted"], justify="left", wraplength=420).pack(anchor="w", pady=(0, 20))
        self.field_label(body, "TVOJE ÚKOLY")
        self.label(body, "Úkoly zůstávají v tomto počítači. Exportem si je\nzálohuješ nebo přeneseš na jiné zařízení.", size=10, color=p["muted"], justify="left").pack(anchor="w", pady=(8, 12))
        actions = tk.Frame(body, bg=p["paper"]); actions.pack(fill="x")
        self.button(actions, "Export úkolů", self.export_tasks, small=True, bg=p["hover"]).pack(side="left", padx=(0, 8))
        self.button(actions, "Import úkolů", self.import_tasks, small=True, bg=p["hover"]).pack(side="left")
        tk.Frame(body, height=1, bg=p["line"]).pack(fill="x", pady=18)
        self.label(body, "KLÁVESOVÉ ZKRATKY", size=8, color=p["muted"], bold=True).pack(anchor="w")
        self.label(body, "Ctrl N   Nový úkol     Ctrl F   Hledat\nCtrl Z   Vrátit změnu   Ctrl S   Uložit detail", size=10, color=p["muted"], justify="left").pack(anchor="w", pady=(8, 18))
        def save():
            if self.safe(lambda: self.store.save_settings(name=name.get().strip(), notifications_enabled=notifications.get(), notification_sound=sound.get(), run_in_background=background.get(), reminder_lead=lead_options[lead.get()]), success=True):
                if self.tray:
                    self.tray.enabled = notifications.get()
                    if not notifications.get(): self.tray.dismiss_notification()
                dialog.destroy(); self._build(); self.toast("Nastavení uloženo")
        buttons = tk.Frame(body, bg=p["paper"]); buttons.pack(fill="x")
        self.button(buttons, "Ukončit aplikaci", self.quit_app, small=True).pack(side="left")
        self.button(buttons, "Uložit nastavení", save, primary=True, small=True).pack(side="right")
        dialog.bind("<Escape>", lambda _: dialog.destroy())

    def export_tasks(self):
        if not self.save_editor(): return
        path = filedialog.asksaveasfilename(parent=self, title="Exportovat úkoly", defaultextension=".json", initialfile=f"to-do-list-{date.today().isoformat()}.json", filetypes=[("Úkoly v JSON", "*.json")])
        if path and self.safe(lambda: self.store.export(Path(path)), success=True): self.toast("Úkoly exportovány")

    def import_tasks(self):
        if not self.save_editor(): return
        path = filedialog.askopenfilename(parent=self, title="Import úkolů", filetypes=[("Úkoly v JSON", "*.json")])
        if path:
            result = self.safe(lambda: self.store.import_file(Path(path)))
            if result is not None:
                self._build(); self.toast(f"Importované úkoly: {result}", undo=bool(result))

    def tick(self):
        if self._shutting_down: return
        if date.today() != self.today:
            self.today = date.today(); self.render_tasks()
        now = datetime.now()
        if self.selected_id and hasattr(self, "timer_label") and self.timer_label.winfo_exists():
            task = self.store.find(self.selected_id)
            if task: self.timer_label.configure(text=countdown(task) if task.timer_end else "")
        if self._last_reminder_check is None or (now-self._last_reminder_check).total_seconds() >= 5:
            self._last_reminder_check = now
            self.check_reminders(now)
        self._tick_job = self.after(1000, self.tick)

    def check_reminders(self, now=None):
        reminders = [item for item in pending_reminders(self.store.tasks, self.store.settings, now) if (item.task_id, item.key) not in self._delivered]
        if not reminders: return []
        # Queue simultaneous tasks into one banner so Windows does not replace them.
        if len(reminders) == 1:
            title, text = reminders[0].title, reminders[0].message
        else:
            title = f"Připomínky úkolů: {len(reminders)}"
            text = "; ".join(item.message for item in reminders)
        delivered = bool(self.tray and self.tray.notify(title, text, sound=self.store.settings.get("notification_sound", True)))
        visible = self.state() != "withdrawn"
        if visible:
            self.toast(f"{title}: {text[:80]}")
            if not delivered and self.store.settings.get("notification_sound", True): self.bell()
        if delivered or visible:
            try: self.store.acknowledge_reminders(reminders)
            except StoreError:
                # Still avoid repeat popups this session; retry persistence on the next edit.
                for item in reminders:
                    task = self.store.find(item.task_id)
                    if task and item.key not in task.reminders_sent: task.reminders_sent.append(item.key)
            self._delivered.update((item.task_id, item.key) for item in reminders)
            return reminders
        return []

    def set_notifications(self, enabled):
        if self.safe(lambda: self.store.save_settings(notifications_enabled=bool(enabled)), success=True):
            if self.tray:
                self.tray.enabled = bool(enabled)
                if not enabled: self.tray.dismiss_notification()
            if self.state() != "withdrawn": self.toast("Oznámení zapnuta" if enabled else "Oznámení vypnuta")

    def process_desktop_events(self):
        if self._shutting_down: return
        try:
            while True:
                action, payload = self.tray.events.get_nowait()
                if action == "show": self.show_window()
                elif action == "quit": self.quit_app(); return
                elif action == "toggle_notifications": self.set_notifications(not self.store.settings.get("notifications_enabled", True))
        except queue.Empty:
            pass
        self._desktop_job = self.after(250, self.process_desktop_events)

    def show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()
        self.render_tasks()

    def close(self):
        if not self.save_editor(explicit=True): return
        self.hide_tip()
        if self.store.settings.get("run_in_background", True) and self.tray and self.tray.available:
            self.withdraw()
            return
        self.quit_app()

    def quit_app(self):
        if self._shutting_down or not self.save_editor(explicit=True): return
        self._shutting_down = True
        self.hide_tip()
        for job in (self._tick_job, self._desktop_job, self.editor_job):
            if job:
                try: self.after_cancel(job)
                except tk.TclError: pass
        if self.tray: self.tray.close()
        if self.instance_guard: self.instance_guard.close()
        self.destroy()


def demo_directory():
    directory = Path(tempfile.mkdtemp(prefix="todo-list-demo-"))
    today = date.today()
    atomic_json(directory / "settings.json", {"name": "Alex"})
    store = TaskStore(directory)
    store.add("Review the project brief", category="Práce", due_date=today.isoformat(), priority="high", starred=True,
              notes="Read the latest brief and note anything that needs clarification before the review.",
              subtasks=[{"text": "Read the updated brief", "completed": True}, {"text": "Write down open questions", "completed": False}])
    store.add("Sketch a first direction", category="Programování", due_date=today.isoformat(), notes="Keep it simple. Start with the essential interactions.")
    store.add("Book a dentist appointment", category="Osobní", due_date=(today+timedelta(days=1)).isoformat())
    store.add("Read chapter four", category="Škola", due_date=(today+timedelta(days=2)).isoformat(), subtasks=[{"text": "Take notes", "completed": False}])
    store.add("Send the final files", category="Práce", due_date=(today+timedelta(days=3)).isoformat(), starred=True)
    store.add("A walk before dinner", category="Osobní", due_date=today.isoformat(), repeat="daily", priority="low")
    task = store.add("Clear the inbox", category="Práce")
    store.toggle(task.id)
    store.history.clear()
    return directory


FocusListApp = ToDoListApp


def main():
    parser = argparse.ArgumentParser(description="To-do list — úkoly a časovače na tvém počítači.")
    parser.add_argument("--data-dir", type=Path, default=APP_DIRECTORY, help="Folder containing tasks.json and settings.json")
    parser.add_argument("--demo", action="store_true", help="Preview sample tasks in a separate temporary folder")
    parser.add_argument("--background", action="store_true", help="Start in the system tray without opening a window")
    parser.add_argument("--self-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--report", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.self_test:
        from self_test import run_self_test
        return run_self_test(args.report or APP_DIRECTORY / "self-test.json")
    directory = demo_directory() if args.demo else args.data_dir
    set_app_identity()
    guard = InstanceGuard(directory)
    if guard.already_running:
        if not args.background:
            import time
            for _ in range(25):
                if guard.request_open(): break
                time.sleep(.1)
        guard.close()
        return 0
    try:
        app = ToDoListApp(directory, hidden=args.background)
        app.instance_guard = guard
        if args.background and (not app.tray or not app.tray.available):
            # Never leave an inaccessible application running without its tray icon.
            app.quit_app()
            return 1
    except BaseException:
        guard.close()
        raise
    app.mainloop()
    guard.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
