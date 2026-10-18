from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel


class GoalButton(QLabel):
    """Кнопка режиму підбору 3/5 · 4/5 · 5/5. QLabel, а не QPushButton: текст —
    rich-text («3/5» кольору кнопки + «72%» кольору шансу), а QPushButton
    частину тексту не фарбує. Вибраність — динамічна властивість active для
    QSS (селектор [active="true"]); ховер — :hover (потрібен WA_Hover)."""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("active", False)

    def set_active(self, active: bool):
        if self.property("active") == active:
            return
        self.setProperty("active", active)
        # QSS не перечитує динамічні властивості сам
        self.style().unpolish(self)
        self.style().polish(self)

    def reserve_width(self, widest_html: str):
        """Мінімальна ширина під найширший підпис («5/5 100%»), щоб зміна
        кількості цифр відсотка не смикала ширину ряду/оверлея."""
        text = self.text()
        self.setText(widest_html)
        self.ensurePolished()  # без цього sizeHint не врахує QSS-паддінг
        self.setMinimumWidth(self.sizeHint().width())
        self.setText(text)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        if (e.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(e.position().toPoint())):
            self.clicked.emit()
