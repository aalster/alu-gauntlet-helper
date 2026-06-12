# Інсталятор (PyInstaller onedir + Inno Setup) — план імплементації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Перевести дистрибуцію з одного `--onefile` .exe на інсталятор: PyInstaller `--onedir` + Inno Setup, per-user, дані поруч з exe.

**Architecture:** На старті frozen-збірки процес робить `os.chdir(<тека exe>)` — усі наявні відносні шляхи (`app.db`, `data/`, шляхи іконок у БД) працюють без змін. Tesseract пакується в підтеку `tesseract/` і використовується як фолбек, якщо шлях у налаштуваннях порожній. Inno Setup пакує onedir-збірку в один сетап-файл.

**Tech Stack:** PyInstaller 6 (onedir), Inno Setup 6 (ISCC), PowerShell-скрипт збірки, pytest.

**Спека:** `docs/superpowers/specs/2026-06-12-installer-design.md`

> **ВАЖЛИВО (правило користувача):** git-коміти НЕ робити — користувач комітить сам. Кроки «Commit» у плані відсутні навмисно.

---

### Task 1: Хелпер `app_dir_if_frozen` + `os.chdir` у `main()`

**Files:**
- Modify: `alu_gauntlet_helper/utils/utils.py` (після `get_resource_path`, ~рядок 19)
- Modify: `main.py:14-15`
- Test: `tests/test_app_dir.py` (новий)

- [ ] **Step 1: Написати тест, що падає**

Створити `tests/test_app_dir.py`:

```python
import sys

from alu_gauntlet_helper.utils.utils import app_dir_if_frozen


def test_dev_mode_returns_none(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert app_dir_if_frozen() is None


def test_frozen_returns_exe_dir(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Apps\ALU\ALU Gauntlet Helper.exe")
    assert app_dir_if_frozen() == r"C:\Apps\ALU"
```

- [ ] **Step 2: Переконатися, що тест падає**

Run: `pytest tests/test_app_dir.py -v`
Expected: FAIL, `ImportError: cannot import name 'app_dir_if_frozen'`

- [ ] **Step 3: Реалізація**

У `alu_gauntlet_helper/utils/utils.py` одразу після `get_resource_path` додати:

```python
def app_dir_if_frozen() -> str | None:
    """Тека exe для PyInstaller-збірки; None при запуску з сирців."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return None
```

(`os` і `sys` у файлі вже імпортовані.)

- [ ] **Step 4: Переконатися, що тест проходить**

Run: `pytest tests/test_app_dir.py -v`
Expected: 2 passed

- [ ] **Step 5: Підключити в main.py**

У `main.py` додати імпорти та chdir першими рядками `main()`:

```python
import os
import sys

from PyQt6.QtWidgets import QApplication

from alu_gauntlet_helper.app_context import APP_CONTEXT
from alu_gauntlet_helper.services.cars_sync import update_cars_if_needed
from alu_gauntlet_helper.services.initial_data import init_data
from alu_gauntlet_helper.utils.single_instance_lock import single_instance_lock
from alu_gauntlet_helper.utils.utils import app_dir_if_frozen
from alu_gauntlet_helper.views.main_window import MainWindow
from alu_gauntlet_helper.views.style import apply_style
from alu_gauntlet_helper.database import init_db


def main():
    app_dir = app_dir_if_frozen()
    if app_dir:
        # cwd = тека застосунку: всі відносні шляхи (app.db, data/, іконки в БД)
        # розв'язуються відносно exe; після цього cwd ніде не змінювати
        os.chdir(app_dir)

    start_minimized = "--minimized" in sys.argv
    ...
```

(решта `main()` без змін)

- [ ] **Step 6: Прогнати весь сьют і запустити застосунок**

Run: `pytest -q`
Expected: усе зелене

Run: `python main.py` — застосунок стартує, `app.db` як і раніше в корені проєкту.

---

### Task 2: Фолбек на бандлений Tesseract

**Files:**
- Modify: `alu_gauntlet_helper/screen_recognition/ocr.py:1-32`
- Test: `tests/test_tesseract_config.py` (новий; НЕ в `test_ocr.py` — той модуль скіпається без установленого Tesseract)

- [ ] **Step 1: Написати тести, що падають**

Створити `tests/test_tesseract_config.py`:

```python
import os
import sys

import pytesseract
import pytest

from alu_gauntlet_helper.screen_recognition import ocr


@pytest.fixture(autouse=True)
def restore_tesseract_cmd():
    """configure_tesseract мутує глобальний tesseract_cmd — відновлюємо після тесту."""
    original = pytesseract.pytesseract.tesseract_cmd
    yield
    pytesseract.pytesseract.tesseract_cmd = original


def test_bundled_path_empty_in_dev(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert ocr._bundled_tesseract() == ""


def test_bundled_path_in_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Apps\ALU\ALU Gauntlet Helper.exe")
    assert ocr._bundled_tesseract() == os.path.join(r"C:\Apps\ALU", "tesseract", "tesseract.exe")


def test_configure_prefers_bundled_over_system(monkeypatch, tmp_path):
    fake = tmp_path / "tesseract" / "tesseract.exe"
    fake.parent.mkdir()
    fake.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "app.exe"))

    assert ocr.configure_tesseract() is True
    assert pytesseract.pytesseract.tesseract_cmd == str(fake)


def test_explicit_path_beats_bundled(monkeypatch, tmp_path):
    bundled = tmp_path / "tesseract" / "tesseract.exe"
    bundled.parent.mkdir()
    bundled.write_bytes(b"")
    explicit = tmp_path / "custom.exe"
    explicit.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "app.exe"))

    assert ocr.configure_tesseract(str(explicit)) is True
    assert pytesseract.pytesseract.tesseract_cmd == str(explicit)
```

- [ ] **Step 2: Переконатися, що тести падають**

Run: `pytest tests/test_tesseract_config.py -v`
Expected: FAIL, `AttributeError: ... has no attribute '_bundled_tesseract'`

- [ ] **Step 3: Реалізація**

У `alu_gauntlet_helper/screen_recognition/ocr.py`:

Додати `import sys` до імпортів (після `import shutil`).

Після `DEFAULT_TESSERACT_PATHS` додати:

```python
def _bundled_tesseract() -> str:
    """Шлях до Tesseract, що йде в комплекті з інсталятором; "" поза frozen-збіркою."""
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "tesseract", "tesseract.exe")
    return ""
```

Оновити `configure_tesseract` (порядок: явний шлях → бандл → PATH → типові локації):

```python
def configure_tesseract(path: str = "") -> bool:
    """Виставляє tesseract_cmd: явний шлях → бандл → PATH → типові локації. True, якщо знайдено."""
    candidates = [path] if path else []
    bundled = _bundled_tesseract()
    if bundled:
        candidates.append(bundled)
    which = shutil.which("tesseract")
    if which:
        candidates.append(which)
    candidates += DEFAULT_TESSERACT_PATHS

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            return True
    return False
```

- [ ] **Step 4: Переконатися, що тести проходять**

Run: `pytest tests/test_tesseract_config.py -v`
Expected: 4 passed

- [ ] **Step 5: Повний сьют**

Run: `pytest -q`
Expected: усе зелене (зокрема `test_ocr.py` — фікстура відновлює `tesseract_cmd`)

---

### Task 3: Версія застосунку

**Files:**
- Create: `alu_gauntlet_helper/version.py`

- [ ] **Step 1: Створити файл** (константа, тест не потрібен)

```python
APP_VERSION = "1.0.0"
```

---

### Task 4: main.spec → onedir, повернути spec у git

**Files:**
- Modify: `main.spec` (повний перезапис)
- Modify: `.gitignore`

- [ ] **Step 1: Виправити .gitignore**

`*.spec` зараз ховає `main.spec` від git. Замінити вміст `.gitignore` на:

```gitignore
.idea
.venv
build
dist
*.iml
*.spec
!main.spec

app.db
data
installer/tesseract
```

- [ ] **Step 2: Переписати main.spec на onedir**

Повний новий вміст `main.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('resources', 'resources')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ALU Gauntlet Helper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['resources\\logo.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ALU Gauntlet Helper',
)
```

Ключові відмінності від старого: `exclude_binaries=True` в `EXE` + блок `COLLECT` (це і є onedir), `datas=[('resources', 'resources')]` (раніше ресурси додавалися лише прапорцем `--add-data` з командного рядка), ім'я `ALU Gauntlet Helper` замість `main`.

- [ ] **Step 3: Зібрати й перевірити**

Run: `.venv\Scripts\pyinstaller.exe main.spec --noconfirm`
Expected: тека `dist\ALU Gauntlet Helper\` з `ALU Gauntlet Helper.exe` і `_internal\` (всередині `_internal` — тека `resources`)

Run: `& "dist\ALU Gauntlet Helper\ALU Gauntlet Helper.exe"`
Expected: застосунок стартує; `app.db` і `data\` створюються в `dist\ALU Gauntlet Helper\` (підтвердження роботи chdir з Task 1). Закрити застосунок, видалити створені `app.db`/`data` з dist.

---

### Task 5: Скрипт Inno Setup

**Files:**
- Create: `installer/setup.iss`
- Create: `installer/README.md`

- [ ] **Step 1: Створити installer/setup.iss**

```iss
; ALU Gauntlet Helper — Inno Setup script.
; Версію передає скрипт збірки: ISCC /DAppVersion=x.y.z installer\setup.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "ALU Gauntlet Helper"
#define AppExe "ALU Gauntlet Helper.exe"

[Setup]
AppId={{8C0F4E2A-7D31-4B6E-9A54-D2E3F1A0C7B9}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\{#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=ALU-Gauntlet-Helper-Setup-{#AppVersion}
SetupIconFile=..\resources\logo.ico
UninstallDisplayIcon={app}\{#AppExe}
CloseApplications=yes
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
Name: "autostart"; Description: "Run at Windows startup (minimized to tray)"; Flags: unchecked

[Files]
Source: "..\dist\{#AppName}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "tesseract\*"; DestDir: "{app}\tesseract"; Flags: recursesubdirs ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{userprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExe}"; Parameters: "--minimized"; WorkingDir: "{app}"; Tasks: autostart

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
```

Нотатки:
- `AppId` — постійний GUID: завдяки йому нові версії ставляться поверх старих як апгрейд.
- Деінсталятор видаляє лише файли, які ставив сам, — `app.db` і `data\` у `{app}` лишаються.
- `skipifsourcedoesntexist` — інсталятор збереться навіть без `installer\tesseract\` (тоді просто без OCR-бандла).

- [ ] **Step 2: Створити installer/README.md**

```markdown
# Збірка інсталятора

## Передумови

1. **Inno Setup 6** — https://jrsoftware.org/isinfo.php (ISCC.exe має бути у стандартному місці встановлення).
2. **Портативний Tesseract** у `installer/tesseract/` (тека в .gitignore):
   - встанови Tesseract (UB Mannheim build) або візьми вже встановлений;
   - скопіюй вміст його теки (tesseract.exe, *.dll, tessdata/ з eng.traineddata) в `installer/tesseract/`;
   - перевір: `installer\tesseract\tesseract.exe --version` працює.
   Без цієї теки інсталятор збереться, але без бандленого OCR.

## Збірка

    powershell -File scripts/build_installer.ps1

Результат: `dist/installer/ALU-Gauntlet-Helper-Setup-<версія>.exe`.
Версія береться з `alu_gauntlet_helper/version.py`.
```

---

### Task 6: Скрипт збірки + оновлення CLAUDE.md

**Files:**
- Create: `scripts/build_installer.ps1`
- Modify: `CLAUDE.md` (секція Commands і рядок про main.py в Architecture)

- [ ] **Step 1: Створити scripts/build_installer.ps1**

```powershell
# Збирає onedir-білд PyInstaller і пакує його в інсталятор Inno Setup.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

$versionLine = Select-String -Path "alu_gauntlet_helper\version.py" -Pattern 'APP_VERSION\s*=\s*"([^"]+)"'
$version = $versionLine.Matches[0].Groups[1].Value
Write-Host "Building ALU Gauntlet Helper $version"

& "$root\.venv\Scripts\pyinstaller.exe" main.spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw "pyinstaller failed" }

$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) { $iscc = "$env:ProgramFiles\Inno Setup 6\ISCC.exe" }
if (-not (Test-Path $iscc)) { throw "Inno Setup 6 (ISCC.exe) not found" }

& $iscc "/DAppVersion=$version" "installer\setup.iss"
if ($LASTEXITCODE -ne 0) { throw "ISCC failed" }

Write-Host "Done: dist\installer\ALU-Gauntlet-Helper-Setup-$version.exe"
```

- [ ] **Step 2: Оновити CLAUDE.md**

У секції `## Commands` замінити рядок збірки:

```bash
# Build installer (PyInstaller onedir + Inno Setup), see installer/README.md
powershell -File scripts/build_installer.ps1
```

(прибрати стару команду `pyinstaller --onefile ...`)

До секції `## Key Patterns` додати пункт:

```markdown
- **Data location**: frozen-збірка робить `os.chdir(<тека exe>)` на старті — `app.db` і `data/` живуть поруч з exe; cwd після старту не змінювати
```

- [ ] **Step 3: Спробувати повну збірку**

Run: `powershell -File scripts/build_installer.ps1`
Expected: `dist\installer\ALU-Gauntlet-Helper-Setup-1.0.0.exe` (якщо Inno Setup не встановлено — зупинитися і повідомити користувача, встановлення стороннього ПЗ потребує його підтвердження)

---

### Task 7: Ручна перевірка (разом із користувачем)

- [ ] Запустити сетап: ставиться без UAC у `%LOCALAPPDATA%\Programs\ALU Gauntlet Helper`
- [ ] Перший запуск: `app.db` і `data\` створюються в теці застосунку; розпізнавання працює з бандленим Tesseract при порожньому шляху в налаштуваннях
- [ ] Скопіювати наявні `app.db` + `data\` користувача в теку застосунку — статистика й іконки на місці
- [ ] Поставити сетап повторно поверх — дані не зникли
- [ ] Задача autostart: ярлик у `shell:startup`, запуск згорнуто в трей
- [ ] Деінсталяція: програма видалена, `app.db`/`data\` лишилися в теці

---

## Самоперевірка плану (виконано)

- Покриття спеки: chdir (Task 1), Tesseract-фолбек (Task 2), версія (Task 3), onedir-spec (Task 4), setup.iss з усіма пунктами спеки — GUID, per-user, ярлики, autostart з `--minimized`, postinstall run, CloseApplications (Task 5), скрипт збірки (Task 6), ручні перевірки (Task 7).
- Плейсхолдерів немає; типи й імена між тасками узгоджені (`app_dir_if_frozen`, `_bundled_tesseract`, `APP_VERSION`, ім'я збірки `ALU Gauntlet Helper` однакове в spec/iss/ps1).
