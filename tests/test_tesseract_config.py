import os
import subprocess
import sys
from types import SimpleNamespace

import pytesseract
import pytest

from alu_gauntlet_helper.screen_recognition import ocr


@pytest.fixture(autouse=True)
def restore_tesseract_cmd():
    """configure_tesseract мутує глобальний tesseract_cmd — відновлюємо після тесту.

    Увага: test_ocr.py викликає configure_tesseract на імпорті, тому `original`
    може бути реальним шляхом, а не дефолтом бібліотеки — не покладатися на нього.
    """
    original = pytesseract.pytesseract.tesseract_cmd
    yield
    pytesseract.pytesseract.tesseract_cmd = original


def test_bundled_path_points_to_installer_in_dev(monkeypatch):
    # Запуск із вихідників бере ту саму портативну копію з installer/tesseract/,
    # а не системний Tesseract (див. докстрінг _bundled_tesseract).
    monkeypatch.delattr(sys, "frozen", raising=False)
    name = "tesseract.exe" if sys.platform == "win32" else "tesseract"
    assert ocr._bundled_tesseract().endswith(os.path.join("installer", "tesseract", name))


def test_bundled_path_in_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Apps\ALU\ALU Gauntlet Helper.exe")
    assert ocr._bundled_tesseract() == os.path.join(r"C:\Apps\ALU", "tesseract", "tesseract.exe")


def test_configure_prefers_bundled_over_system(monkeypatch, tmp_path):
    # вміст файлів неважливий — перевіряється лише існування та пріоритет кандидатів
    fake = tmp_path / "tesseract" / "tesseract.exe"
    fake.parent.mkdir()
    fake.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "app.exe"))

    assert ocr.configure_tesseract() is True
    assert pytesseract.pytesseract.tesseract_cmd == str(fake)


@pytest.fixture(autouse=True)
def clear_availability_cache():
    ocr._availability_cache.clear()
    yield
    ocr._availability_cache.clear()


def test_is_available_hides_console_window(monkeypatch):
    """У windowed-збірці дочірня консоль без CREATE_NO_WINDOW блимає вікном."""
    captured = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(ocr.subprocess, "run", fake_run)
    assert ocr.is_available() is True
    if sys.platform == "win32":
        assert captured.get("creationflags", 0) & subprocess.CREATE_NO_WINDOW


def test_is_available_caches_per_path(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(ocr.subprocess, "run", fake_run)
    assert ocr.is_available() is True
    assert ocr.is_available() is True
    assert len(calls) == 1


def test_is_available_false_when_probe_fails(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise OSError("not found")

    monkeypatch.setattr(ocr.subprocess, "run", fake_run)
    assert ocr.is_available() is False


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
