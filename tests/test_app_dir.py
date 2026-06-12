import sys

from alu_gauntlet_helper.utils.utils import app_dir_if_frozen


def test_dev_mode_returns_none(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert app_dir_if_frozen() is None


def test_frozen_false_returns_none(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert app_dir_if_frozen() is None


def test_frozen_returns_exe_dir(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Apps\ALU\ALU Gauntlet Helper.exe")
    assert app_dir_if_frozen() == r"C:\Apps\ALU"
