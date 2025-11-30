from typing import Callable

from PyQt6.QtCore import Qt, QTimer, QObject, QEvent
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QVBoxLayout, QLineEdit, QHBoxLayout, QLayout, QWidget, QListWidget, QListWidgetItem

from alu_gauntlet_helper.utils.utils import get_resource_path


class FocusWatcher(QObject):

    def __init__(self, on_focus_in = None, on_focus_out = None):
        super().__init__()
        self.on_focus_in = on_focus_in
        self.on_focus_out = on_focus_out

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.FocusIn and self.on_focus_in:
            self.on_focus_in()
        elif event.type() == QEvent.Type.FocusOut and self.on_focus_out:
            self.on_focus_out()
        return False

class InputDebounce:
    def __init__(self, input_: QLineEdit, on_change: Callable, debounce_time: int = 300):
        self.input_ = input_
        self.debounce_time = debounce_time

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(on_change) # type: ignore

        self.input_.textChanged.connect(self.start) # type: ignore

    def start(self):
        self.timer.start(self.debounce_time)


class ListItemWidget(QWidget):
    def __init__(self, item, parent=None):
        super().__init__(parent)
        self.item = item

    def add_to_list(self, list_widget: QListWidget):
        list_item = QListWidgetItem(list_widget)
        list_item.setData(Qt.ItemDataRole.UserRole, self.item)
        list_item.setSizeHint(self.sizeHint())

        list_widget.addItem(list_item)
        list_widget.setItemWidget(list_item, self)

class ClearOnEscEventFilter(QObject):
    def eventFilter(self, obj, event):
        if isinstance(obj, QLineEdit) and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                obj.clear()
                return True
        return super().eventFilter(obj, event)

CLEAR_ON_ESC_FILTER = ClearOnEscEventFilter()


def add_contents(layout, items, spacing=None, alignment=None):
    layout.setContentsMargins(0, 0, 0, 0)
    if spacing is not None:
        layout.setSpacing(spacing)

    kwargs = {}
    if alignment is not None:
        kwargs['alignment'] = alignment

    for item in items:
        if isinstance(item, QLayout):
            layout.addLayout(item, **kwargs)
        else:
            layout.addWidget(item, **kwargs)
    return layout

def vbox(items, spacing=None, alignment=None) -> QVBoxLayout:
    return add_contents(QVBoxLayout(), items, spacing=spacing, alignment=alignment)

def hbox(items, spacing=None, alignment=None) -> QHBoxLayout:
    return add_contents(QHBoxLayout(), items, spacing=spacing, alignment=alignment)

def res_to_pixmap(path: str, size: int | None = None):
    q_pixmap = QPixmap(get_resource_path(path))
    if size:
        q_pixmap = q_pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return q_pixmap