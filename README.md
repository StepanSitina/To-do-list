# To-Do List

A polished CustomTkinter desktop To-Do List and calendar dashboard with:

- first-launch personalized Czech greeting saved in `settings.json`
- conservative Czech 5th-case name addressing (unknown names stay unchanged)
- category and priority dropdowns
- editable DD.MM.YYYY date and HH:MM time fields with calendar/time pickers
- active/completed tabs, search, filters, editing, and a full-screen completion overlay
- live clock, calendar, JSON persistence, and one-hour reminders

## Run locally

Install the UI dependency and launch the app:

```powershell
python -m pip install customtkinter
python app.py
```

Tasks are stored in `tasks.json` beside the script (or beside the packaged executable).
Your name is stored in `settings.json` beside the task file.
Each record includes creation date, due date/time, completion state, completion
timestamp, and reminder state. New due dates must include a future date and time.
The reminder worker checks pending tasks every 15 seconds and raises a system bell
plus an inline banner during the one-hour-before-due window.

## Build a standalone Windows executable

Run these commands from the repository directory on a Windows development machine:

```powershell
python -m pip install customtkinter pyinstaller
pyinstaller --noconsole --onefile --collect-all customtkinter --name app app.py
```

The finished executable is created at `dist\app.exe`. It includes Python,
CustomTkinter, and the required runtime dependencies, so Python does not need to
be installed on the target PC.

Keep `tasks.json` in the same folder as `app.exe` after the first launch to
preserve task data between sessions.
