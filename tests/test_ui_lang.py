import pytest

from alu_gauntlet_helper import ui_lang


@pytest.fixture(autouse=True)
def restore_language():
    original = ui_lang.current_ui_language()
    yield
    ui_lang.set_ui_language(original)


def test_default_language_is_en():
    assert ui_lang.current_ui_language() == ui_lang.EN


def test_set_ui_language_uk():
    ui_lang.set_ui_language(ui_lang.UK)
    assert ui_lang.current_ui_language() == ui_lang.UK


def test_unknown_language_normalizes_to_en():
    ui_lang.set_ui_language("zz")
    assert ui_lang.current_ui_language() == ui_lang.EN


def test_t_returns_current_language_string():
    ui_lang.set_ui_language(ui_lang.EN)
    assert ui_lang.t("settings.save") == "Save"
    ui_lang.set_ui_language(ui_lang.UK)
    assert ui_lang.t("settings.save") == "Зберегти"


def test_t_returns_key_when_missing():
    assert ui_lang.t("nonexistent.key") == "nonexistent.key"


def test_translation_dicts_have_identical_keys():
    en_keys = set(ui_lang.TRANSLATIONS["en"])
    uk_keys = set(ui_lang.TRANSLATIONS["uk"])
    assert en_keys == uk_keys, f"key mismatch: {en_keys ^ uk_keys}"


@pytest.mark.parametrize("locale_name,expected", [
    ("uk_UA", "uk"),
    ("ru_RU", "uk"),
    ("en_US", "en"),
    ("de_DE", "en"),
    ("", "en"),
    ("C", "en"),
])
def test_system_to_ui_language(locale_name, expected):
    assert ui_lang.system_to_ui_language(locale_name) == expected
