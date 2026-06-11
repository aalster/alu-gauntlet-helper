from alu_gauntlet_helper.capture import hotkey as hotkey_module
from alu_gauntlet_helper.capture.hotkey import GlobalHotkeyService


class FakeKeyboard:
    def __init__(self, fail=False):
        self.fail = fail
        self.registered = {}

    def add_hotkey(self, combo, callback):
        if self.fail:
            raise ValueError("bad combo")
        self.registered[combo] = callback
        return combo

    def remove_hotkey(self, handle):
        del self.registered[handle]


def test_register_success(monkeypatch):
    fake = FakeKeyboard()
    monkeypatch.setattr(hotkey_module, "keyboard", fake)
    service = GlobalHotkeyService()
    assert service.register("f8", lambda: None) is True
    assert "f8" in fake.registered


def test_register_failure_returns_false(monkeypatch):
    monkeypatch.setattr(hotkey_module, "keyboard", FakeKeyboard(fail=True))
    service = GlobalHotkeyService()
    assert service.register("f8", lambda: None) is False


def test_unregister_all(monkeypatch):
    fake = FakeKeyboard()
    monkeypatch.setattr(hotkey_module, "keyboard", fake)
    service = GlobalHotkeyService()
    service.register("f8", lambda: None)
    service.register("f9", lambda: None)
    service.unregister_all()
    assert fake.registered == {}
