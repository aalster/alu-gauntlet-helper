from contextlib import contextmanager
from typing import Callable

from PyQt6.QtCore import Qt, QTimer, QObject, QEvent, QRectF, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QIcon, QImageReader
from PyQt6.QtWidgets import QVBoxLayout, QLineEdit, QHBoxLayout, QLayout, QWidget, QListWidget, QListWidgetItem, \
    QToolButton, QLabel

from alu_gauntlet_helper.utils.utils import get_resource_path, load_pixmap_cover
from alu_gauntlet_helper.views import style


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

@contextmanager
def preserved_scroll(list_widget: QListWidget):
    """Перебудова списку всередині блока не скидає вертикальний скрол."""
    bar = list_widget.verticalScrollBar()
    value = bar.value()
    yield
    # без doItemsLayout діапазон скролбара ще нульовий і value обріжеться
    list_widget.doItemsLayout()
    bar.setValue(value)


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

    # vertical space consumed by the QSS ::item chrome (margins + border), see style.APP_STYLE
    ITEM_CHROME_HEIGHT = 16

    def add_to_list(self, list_widget: QListWidget):
        self._attach(list_widget, QListWidgetItem(list_widget))

    def replace_in_list(self, list_widget: QListWidget, index: int):
        """Підміняє віджет наявного рядка — список не перебудовується і не блимає."""
        self._attach(list_widget, list_widget.item(index))

    def _attach(self, list_widget: QListWidget, list_item: QListWidgetItem):
        list_item.setData(Qt.ItemDataRole.UserRole, self.item)

        # setItemWidget сам видаляє попередній віджет рядка
        list_widget.setItemWidget(list_item, self)
        # size hint only after the widget is polished, so QSS fonts are applied
        self.ensurePolished()
        hint = self.sizeHint()
        hint.setHeight(hint.height() + self.ITEM_CHROME_HEIGHT)
        list_item.setSizeHint(hint)

class RankClassBadge(QWidget):
    """Game-style badge: dark plate with the rank next to a white plate with the class letter."""
    def __init__(self, rank: int, max_rank: int, car_class: str, rank_color: str = "", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        rank_text = ""
        if rank and max_rank and rank != max_rank:
            rank_text = f"{rank:,} / {max_rank:,}"
        elif rank:
            rank_text = f"{rank:,}"
        elif max_rank:
            rank_text = f"{max_rank:,}"

        over_max = bool(rank and max_rank and rank > max_rank)
        if rank_text:
            if over_max:
                oc_label = QLabel(self)
                oc_label.setPixmap(res_to_pixmap("icons/ocActive.webp", 14))
                oc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                oc_label.setStyleSheet(
                    f"background-color: {style.TEXT_DARK}; border-top-left-radius: 3px;"
                    " border-bottom-left-radius: 3px; padding: 2px 0 2px 8px;")
                layout.addWidget(oc_label)
            rank_label = QLabel(rank_text, self)
            left_radius = "" if over_max else " border-top-left-radius: 3px; border-bottom-left-radius: 3px;"
            right_radius = "" if car_class else " border-top-right-radius: 3px; border-bottom-right-radius: 3px;"
            rank_label.setStyleSheet(
                f"background-color: {style.TEXT_DARK}; color: {rank_color or style.TEXT}; font-weight: bold;"
                f"{left_radius}{right_radius} padding: 2px 8px;")
            layout.addWidget(rank_label)

        if car_class:
            class_label = QLabel(car_class, self)
            left_radius = "" if rank_text else " border-top-left-radius: 3px; border-bottom-left-radius: 3px;"
            class_label.setStyleSheet(
                f"background-color: {style.TEXT}; color: {style.TEXT_DARK}; font-weight: bold;"
                f" border-top-right-radius: 3px; border-bottom-right-radius: 3px;{left_radius} padding: 2px 7px;")
            layout.addWidget(class_label)


def image_preview_html(icon_path: str, width: int = 360) -> str:
    """Rich-text <img> для hover-тултипа, масштабований до `width` (без збільшення)."""
    size = QImageReader(icon_path).size()  # reads the header only, no full decode
    if not size.isValid() or size.width() <= 0:
        return ""
    scale = min(width / size.width(), 1)
    return (f'<img src="{icon_path.replace(chr(92), "/")}"'
            f' width="{round(size.width() * scale)}" height="{round(size.height() * scale)}">')


class CarInfoWidget(QWidget):
    """Car icon, brand/model and rank badge combined on a darkened plate.
    Hovering shows the car image enlarged in a tooltip."""

    PREVIEW_WIDTH = 360

    def __init__(self, icon_path: str, brand: str, model: str, rank_badge: QWidget, parent=None):
        super().__init__(parent)
        # plain QWidget ignores QSS background without this attribute; стилі — у глобальному QSS
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("carInfoPlate")

        self.icon_label = QLabel()
        self.icon_label.setObjectName("carIconLabel")
        self.icon_label.setFixedSize(80, 40)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if icon_path:
            pixmap = load_pixmap_cover(icon_path, w=self.icon_label.width(), h=self.icon_label.height())
            if pixmap:
                self.icon_label.setPixmap(pixmap)
            preview = image_preview_html(icon_path, self.PREVIEW_WIDTH)
            if preview:
                self.icon_label.setToolTip(preview)

        self.brand_label = QLabel(brand.upper())
        self.brand_label.setObjectName("carBrandLabel")
        self.model_label = QLabel(model)
        self.model_label.setObjectName("carModelLabel")

        # brand left, rank badge right; the model line below uses the full width
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(6)
        brand_row.addWidget(self.brand_label)
        brand_row.addStretch(1)
        brand_row.addWidget(rank_badge)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)
        layout.addWidget(self.icon_label)
        layout.addLayout(vbox([brand_row, self.model_label], spacing=3), stretch=1)


class ClearOnEscEventFilter(QObject):
    def eventFilter(self, obj, event):
        if isinstance(obj, QLineEdit) and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                obj.clear()
                return True
        return super().eventFilter(obj, event)

CLEAR_ON_ESC_FILTER = ClearOnEscEventFilter()


class ClearButtonCursorFilter(QObject):
    """Pointing-hand cursor + click handling for the clear button. The internal
    QToolButton ignores its own cursor inside a styled QLineEdit, so the button is made
    mouse-transparent and both hover and click are handled on the line edit itself."""
    @staticmethod
    def over_button(line_edit: QLineEdit, pos):
        button = line_edit.findChild(QToolButton)
        return button is not None and bool(line_edit.text()) and button.geometry().contains(pos)

    def eventFilter(self, obj, event):
        if isinstance(obj, QLineEdit):
            if event.type() == QEvent.Type.MouseMove:
                hovering = self.over_button(obj, event.position().toPoint())
                obj.setCursor(Qt.CursorShape.PointingHandCursor if hovering else Qt.CursorShape.IBeamCursor)
            elif event.type() == QEvent.Type.Leave:
                obj.setCursor(Qt.CursorShape.IBeamCursor)
            elif (event.type() == QEvent.Type.MouseButtonPress
                  and event.button() == Qt.MouseButton.LeftButton
                  and self.over_button(obj, event.position().toPoint())):
                obj.clear()
                obj.setCursor(Qt.CursorShape.IBeamCursor)
                return True
        return False

CLEAR_BUTTON_CURSOR_FILTER = ClearButtonCursorFilter()


def enable_clear_button(line_edit: QLineEdit):
    line_edit.setClearButtonEnabled(True)
    button = line_edit.findChild(QToolButton)
    if button:
        # the button swallows mouse events but ignores setCursor when the line edit is
        # styled with QSS; let the line edit handle hover and click instead
        button.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    line_edit.setMouseTracking(True)
    line_edit.installEventFilter(CLEAR_BUTTON_CURSOR_FILTER)


def _search_pixmap(color: str, size: int = 16, dpr: float = 2.0) -> QPixmap:
    pixmap = QPixmap(int(size * dpr), int(size * dpr))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawEllipse(QRectF(2.5, 2.5, 7.5, 7.5))
    painter.drawLine(QPointF(10.2, 10.2), QPointF(13.2, 13.2))
    painter.end()
    return pixmap


def enable_search_icon(line_edit: QLineEdit):
    line_edit.addAction(QIcon(_search_pixmap(style.TEXT_MUTED)), QLineEdit.ActionPosition.LeadingPosition)


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