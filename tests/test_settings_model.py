from alu_gauntlet_helper.services.settings import Settings


def test_capture_defaults():
    s = Settings()
    assert s.capture_hotkey == "f8"
    assert s.overlay_hotkey == "f9"
    assert s.tesseract_path == ""
    assert s.capture_monitor == 1
    assert s.save_captures is False


def test_parses_string_values_from_db():
    # SettingsRepository зберігає все рядками
    s = Settings(capture_monitor="2", save_captures="True")
    assert s.capture_monitor == 2
    assert s.save_captures is True
