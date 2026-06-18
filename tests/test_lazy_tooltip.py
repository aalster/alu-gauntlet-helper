from PyQt6.QtCore import QEvent, QPoint
from PyQt6.QtGui import QHelpEvent
from PyQt6.QtWidgets import QApplication, QLabel

from alu_gauntlet_helper.views.components import common

# віджети потребують екземпляра застосунку; один на весь модуль
app = QApplication.instance() or QApplication([])


def _send_tooltip(widget):
    event = QHelpEvent(QEvent.Type.ToolTip, QPoint(1, 1), QPoint(1, 1))
    app.sendEvent(widget, event)


def test_lazy_tooltip_defers_until_hover(monkeypatch):
    calls = []
    monkeypatch.setattr(common, "image_preview_html",
                        lambda path, width=360: calls.append((path, width)) or "<img>")

    label = QLabel()
    common.set_lazy_image_tooltip(label, "some/icon.png")
    # побудова рядка не має генерувати превʼю — саме це домінувало час старту
    assert calls == []

    _send_tooltip(label)
    # превʼю генерується лише коли користувач реально наводить курсор
    assert calls == [("some/icon.png", 360)]


def test_lazy_tooltip_noop_for_empty_path(monkeypatch):
    calls = []
    monkeypatch.setattr(common, "image_preview_html",
                        lambda *a, **k: calls.append(1) or "")

    label = QLabel()
    common.set_lazy_image_tooltip(label, "")
    _send_tooltip(label)
    assert calls == []


def test_lazy_tooltip_custom_width(monkeypatch):
    calls = []
    monkeypatch.setattr(common, "image_preview_html",
                        lambda path, width=360: calls.append((path, width)) or "<img>")

    label = QLabel()
    common.set_lazy_image_tooltip(label, "icon.png", width=120)
    _send_tooltip(label)
    assert calls == [("icon.png", 120)]
