import os
import sys

import pytest

from alu_gauntlet_helper.screen_recognition import ocr, tesseract_api

DLL = tesseract_api.DLL_NAME


@pytest.fixture(autouse=True)
def restore_engine_dir():
    """configure мутує глобальну теку движка — відновлюємо після тесту.

    Увага: тестові OCR-модулі викликають configure_tesseract на імпорті, тому
    original — це, як правило, реальна тека бандла."""
    original = tesseract_api._lib_dir
    yield
    if original:
        tesseract_api.configure(original)


def test_bundled_dir_points_to_installer_in_dev(monkeypatch):
    # Запуск із вихідників бере ту саму портативну копію з installer/tesseract/,
    # а не системний Tesseract (див. докстрінг _bundled_dir).
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert ocr._bundled_dir().endswith(os.path.join("installer", "tesseract"))


def test_bundled_dir_in_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Apps\ALU\ALU Gauntlet Helper.exe")
    assert ocr._bundled_dir() == os.path.join(r"C:\Apps\ALU", "tesseract")


def test_configure_uses_bundled_dir(monkeypatch, tmp_path):
    # вміст файлу неважливий — configure перевіряє лише наявність DLL
    fake = tmp_path / "tesseract" / DLL
    fake.parent.mkdir()
    fake.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "app.exe"))

    assert ocr.configure_tesseract() is True
    assert tesseract_api._lib_dir == str(fake.parent)


def test_configure_false_when_bundle_missing(monkeypatch, tmp_path):
    """Системні установки НЕ шукаються: немає бандла → одразу False."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "app.exe"))
    assert ocr.configure_tesseract() is False


def test_is_available_false_on_broken_dir(tmp_path):
    """Тека з DLL-пустушкою (або без tessdata): движок не ініціалізується."""
    (tmp_path / DLL).write_bytes(b"")
    tesseract_api.configure(str(tmp_path))
    assert ocr.is_available() is False


def test_is_available_true_with_bundled():
    if not ocr.configure_tesseract():
        pytest.skip("бандлений tesseract недоступний")
    assert ocr.is_available() is True
