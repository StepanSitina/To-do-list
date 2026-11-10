"""Deterministic, restart-safe deadline and timer decisions."""
from dataclasses import dataclass
from datetime import datetime
import random

QUOTES = (
    "Každý hotový úkol uvolní místo pro něco dalšího.",
    "I malý krok má svůj směr.",
    "Dnešek je zase o jeden hotový úkol dál.",
    "Nemusíš zvládnout všechno najednou. Tohle už máš.",
    "To, co bylo v plánu, je teď hotové.",
    "Práce má svůj konec. Tohle je jeden z nich.",
    "Jedna starost méně. O trochu klidnější hlava.",
    "Pokrok se skládá z konkrétních kroků. Právě jsi jeden udělal.",
    "Malé dokončené věci tvoří velké výsledky.",
    "Na chvíli se zastav. I dokončení si zaslouží pozornost.",
    "Dobrý plán začíná nápadem a pokračuje činem.",
    "Dnes máš o jeden důvod k dobrému pocitu víc.",
)
PALETTES = (
    ("#E5EDDF", "#284E3C", "#526D57"),
    ("#F4E1D4", "#713D2B", "#8B6250"),
    ("#DEE9EF", "#2F5067", "#597488"),
    ("#F4EBCB", "#63531F", "#847440"),
    ("#EAE2ED", "#5D4468", "#7A6382"),
)


def next_celebration(previous_quote=-1, previous_palette=-1):
    quote = random.choice([i for i in range(len(QUOTES)) if i != previous_quote])
    palette = random.choice([i for i in range(len(PALETTES)) if i != previous_palette])
    return quote, palette


def due_datetime(task):
    if task.timer_end:
        return datetime.fromisoformat(task.timer_end)
    if task.due_date:
        return datetime.fromisoformat(f"{task.due_date}T{task.due_time or '09:00'}")
    return None


def countdown(task, now=None):
    due = due_datetime(task)
    if due is None or task.completed:
        return ""
    seconds = int((due-(now or datetime.now())).total_seconds())
    if seconds <= 0:
        return "Čas vypršel" if task.timer_end else "Po termínu"
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, seconds = divmod(rest, 60)
    if days:
        return f"Zbývá {days} d {hours} h"
    if hours:
        return f"Zbývá {hours} h {minutes:02d} min"
    return f"Zbývá {minutes:02d}:{seconds:02d}"


@dataclass(frozen=True)
class Reminder:
    task_id: str
    key: str
    title: str
    message: str


def pending_reminders(tasks, settings, now=None):
    if not settings.get("notifications_enabled", True):
        return []
    now = now or datetime.now()
    mode = settings.get("reminder_lead", "both")
    reminders = []
    for task in tasks:
        if task.completed:
            continue
        due = due_datetime(task)
        if due is None:
            continue
        seconds = (due-now).total_seconds()
        if -86400 <= seconds <= 0:
            phase = "due"
            title = "Časovač dokončen" if task.timer_end else "Úkol má právě termín"
            if seconds < -60:
                title = "Časovač doběhl" if task.timer_end else "Připomenutí po termínu"
        elif 0 < seconds <= 3600 and not task.timer_end and mode in ("both", "hour"):
            phase, title = "hour", "Úkol do hodiny"
        elif 3600 < seconds <= 86400 and not task.timer_end and mode in ("both", "day"):
            phase, title = "day", "Úkol do 24 hodin"
        else:
            continue
        key = f"{due.isoformat()}|{phase}"
        if key in task.reminders_sent:
            continue
        if phase == "hour" and task.last_reminded_at == due.isoformat():
            continue
        reminders.append(Reminder(task.id, key, title, task.text))
    return reminders
