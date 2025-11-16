import cv2
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QCheckBox, QFormLayout, QLabel, QFileDialog

from alu_gauntlet_helper.app_context import APP_CONTEXT


class AttrRange:
    def __init__(self, _min: float, _max: float):
        self.min = _min
        self.max = _max

    def contains(self, value: float) -> bool:
        return self.min <= value <= self.max

    def scale(self, value: float) -> 'AttrRange':
        return AttrRange(self.min * value, self.max * value)

    @staticmethod
    def tolerance(value: float, tolerance: float) -> 'AttrRange':
        return AttrRange(value - tolerance, value + tolerance)

class RectAttrs:
    def __init__(self, area_ratio: AttrRange, aspect_ratio: AttrRange, canny: AttrRange):
        self.area_ratio = area_ratio
        self.aspect_ratio = aspect_ratio
        self.canny = canny

race_box_attrs = RectAttrs(
    AttrRange(0.05, 0.1),
    AttrRange.tolerance(0.5, 0.1),
    AttrRange(50, 150)
)


def find_race_boxes(image_bytes):
    return find_rectangles(image_bytes, race_box_attrs)


def find_rectangles(image_bytes, attrs: RectAttrs):
    # 1. Загрузка изображения
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    # if image is None:
    #     print(f"Ошибка: Не удалось загрузить изображение по пути {image_path}")
    #     return None

    output_image = image.copy()

    # 2. Преобразование в оттенки серого
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 3. Применение детектора краев Canny
    # Canny лучше всего подходит для поиска сильных градиентов (контрастов)
    # на границах, игнорируя при этом плавные градиенты внутри объектов и фона.
    # Значения (50, 150) — это нижний и верхний пороги. Их, возможно, придется настроить.
    edges = cv2.Canny(gray, attrs.canny.min, attrs.canny.max, apertureSize=3)
    #

    # --- Опциональный Шаг: Морфологические операции ---
    # Небольшое закрытие (close) может помочь соединить разрывы в краях,
    # вызванные градиентом или обводкой.
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1) # Расширение
    edges = cv2.erode(edges, kernel, iterations=1)  # Сжатие
    # ---

    # 4. Поиск контуров
    # Ищем внешние контуры на изображении, содержащем только края
    contours, hierarchy = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    height, width = image.shape[:2]
    area_range = attrs.area_ratio.scale(height * width)

    rectangles_found = []

    # 5. Обход, фильтрация и аппроксимация
    for contour in contours:
        if not area_range.contains(cv2.contourArea(contour)):
            continue

        perimeter = cv2.arcLength(contour, True)
        # Аппроксимация. Коэффициент 0.04 - типичное начальное значение.
        approx = cv2.approxPolyDP(contour, 0.04 * perimeter, True)

        # Проверка, что контур имеет 4 вершины (прямоугольник)
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(contour)
            if w < 10 or h < 10 or not attrs.aspect_ratio.contains(float(w) / h):
                continue

            cv2.rectangle(output_image, (x, y), (x + w, y + h), (0, 255, 0), 3)
            rectangles_found.append({"x": x, "y": y, "w": w, "h": h})
            print(f"Найден прямоугольник: x={x}, y={y}, w={w}, h={h}")

    cv2.imshow("Canny Edges", edges)
    cv2.imshow("Detected Rectangles", output_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    return rectangles_found
