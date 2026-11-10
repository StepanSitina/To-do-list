# To-do list

Desktopová aplikace pro Windows: úkoly, dílčí kroky, termíny, časovače a připomínky. Přehledný vzhled ve světlém i tmavém režimu.

## Spuštění

Dvakrát klikni na **To-do list.exe**. Python ani další balíčky nepotřebuješ. EXE ponech ve složce, do které můžeš zapisovat.

Úkoly se ukládají do `tasks.json` vedle aplikace, nastavení do `settings.json`. Stávající soubory z předchozí verze fungují dál. Když přenášíš aplikaci na jiný počítač, zkopíruj také oba JSON soubory.

Pokud máš otevřenou předchozí verzi **Focus List**, před spuštěním nové verze ji zavři. Nová verze už hlídá, aby nad jednou složkou úkolů neběžela dvakrát.

## Úkoly a splnění

- Úkol přidáš do horního řádku a potvrdíš Enterem. Kalendář vedle řádku nastavuje termín.
- Kliknutím na název otevřeš detail. Najdeš v něm seznam, prioritu, datum a čas, opakování, dílčí kroky a poznámky. Změny se ukládají automaticky.
- Zaškrtnutý úkol zůstane v přehledu šedý a přeškrtnutý. Všechny dokončené úkoly najdeš také v části **Splněné**.
- Po každém dokončení se zobrazí gratulace, jiný citát a jiná barva obrazovky. Tlačítkem **Pokračovat** nebo Escape se vrátíš k seznamu.
- Počítadlo v levé části ukazuje celkový počet splněných úkolů a dnešní přehled.
- Úkol smažeš přes tři tečky, pravé tlačítko nebo koš v detailu. Poslední změny lze vrátit.
- Hledání prochází i poznámky a dílčí kroky. Vlastní pořadí měníš přetažením za tečkovaný úchyt.

Citáty jsou krátké původní motivační texty bez připisování cizím autorům. Dva stejné citáty ani dvě stejné barvy se bezprostředně neopakují, a to ani po restartu.

## Časovače a oznámení

V detailu úkolu klikni na **Časovač…**. Vyber 10 minut, 1 hodinu, 1 den nebo vlastní počet minut. Časovač končí v uloženém konkrétním čase; přežije zavření okna i restart aplikace. Při doběhnutí pošle systémové oznámení.

U běžných termínů můžeš zapnout připomenutí den předem, hodinu předem a v termínu. Datum bez času se připomíná v 9:00. Zmeškané připomenutí se po obnovení aplikace nebo probuzení počítače odešle jednou, pokud je nejvýše 24 hodin po termínu. Staré připomínky se nehromadí.

Křížek hlavního okna aplikaci ve výchozím nastavení schová k hodinám v liště. Nadále kontroluje termíny a časovače, aniž by otevírala okno. Dvojklik nebo nabídka ikony znovu otevře seznam. Volbou **Ukončit aplikaci** ji zcela vypneš.

**Oznámení vypneš v Nastavení nebo pravým tlačítkem na ikoně u hodin.** Samostatně lze vypnout zvuk i pokračování na pozadí. Aplikace respektuje nastavení oznámení ve Windows.

Připomínky vyžadují spuštěnou aplikaci, klidně schovanou v liště. Při úplném ukončení aplikace nebo vypnutém počítači běžet nemohou; po opětovném spuštění se termíny zkontrolují. Automatické spouštění po přihlášení ani probouzení počítače tato verze nezapíná.

## Klávesnice

| Zkratka | Akce |
| --- | --- |
| Ctrl N | Nový úkol |
| Ctrl F | Hledat |
| Ctrl S | Uložit detail |
| Ctrl Z | Vrátit akci mimo textové pole |
| Ctrl Q | Ukončit aplikaci |
| Escape | Zavřít gratulaci, hledání nebo detail |

## Ukládání a zálohy

Zápisy JSON používají atomickou výměnu souboru. `tasks.json.bak` obsahuje předchozí platnou verzi. Chyba čtení nebo zápisu původní data nepřepíše. Historie posledních 40 akcí pro vrácení změny platí pro aktuální spuštění. Export a import najdeš v Nastavení; import přidává nové úkoly bez duplikování existujících ID.

## Pro vývoj

Zdrojová verze potřebuje Python 3.10+ s Tkinterem a jinak používá standardní knihovnu:

```powershell
python app.py
python -m unittest -v test_task_store test_reminders
python app.py --self-test --report self-test.json
```

Skrytá kontrola neaktivuje okna ani neposílá skutečná oznámení. Ověří práci s úkoly, časovači, JSON, systémovou ikonu a obsah oznámení.

```powershell
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name "To-do list" --icon assets/todo.ico --add-data "assets;assets" app.py
```

`--data-dir CESTA` vybere jinou složku úkolů; `--background` spustí aplikaci přímo v liště. Soubor `index.html` v původním repozitáři je historická prohlížečová varianta. Aktuální desktopová aplikace je `To-do list.exe` / `app.py`.
