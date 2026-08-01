"""In-memory Tesseract через C API (ctypes) — без спавну процесу на виклик.

pytesseract на КОЖНЕ читання пише тимчасовий PNG, запускає новий tesseract.exe,
і той з нуля вантажить LSTM-модель з traineddata — левова частка часу
розпізнавання йшла на старт процесів (див. docs/optimizing-recognition-speed.md).
Тут той самий движок і ті самі traineddata з портативного бандла, але
libtesseract-5.dll вантажиться в процес один раз, а движок на мову
ініціалізується один раз і перевикористовується.

Жодних нових залежностей: DLL і tessdata вже їдуть з застосунком у теці
tesseract/ поруч з exe (у розробці — installer/tesseract/). Якщо DLL чи
tessdata недоступні чи не ініціалізуються — get_engine() повертає None,
ocr.is_available() стає False, і застосунок чесно повідомляє, що OCR немає.
"""
import ctypes
import os
import threading

from PIL import Image

DLL_NAME = "libtesseract-5.dll"

# Один глобальний lock: серіалізує і ініціалізацію, і самі виклики движка
# (розпізнавання в застосунку й так серіалізоване одним воркером).
_lock = threading.Lock()
_lib = None
_lib_dir: str | None = None      # тека з libtesseract-5.dll (= тека tesseract.exe)
_dll_dir_handle = None           # тримаємо, щоб каталог DLL не зняли з пошуку
_lib_failed = False              # DLL не завантажилась — більше не пробуємо
_engines: dict[str, "_Engine"] = {}
_failed_langs: set[str] = set()  # мови, для яких init не вдався


def configure(binary_dir: str) -> None:
    """Вказує теку tesseract (де лежать exe, DLL і tessdata/).

    Викликається з ocr.configure_tesseract(). Скидає движки при зміні теки."""
    global _lib_dir, _lib_failed
    binary_dir = os.path.abspath(binary_dir)
    with _lock:
        if binary_dir == _lib_dir:
            return
        for engine in _engines.values():
            engine.close()
        _engines.clear()
        _failed_langs.clear()
        _lib_dir = binary_dir
        _lib_failed = False  # нова тека — нова спроба (сама DLL лишається завантаженою)


def get_engine(lang: str) -> "_Engine | None":
    """Движок для мови або None (DLL/tessdata недоступні чи init не вдався)."""
    with _lock:
        engine = _engines.get(lang)
        if engine is not None or lang in _failed_langs:
            return engine
        lib = _load_lib_locked()
        if lib is None or _lib_dir is None:
            return None
        handle = lib.TessBaseAPICreate()
        tessdata = os.path.join(_lib_dir, "tessdata")
        if lib.TessBaseAPIInit3(handle, tessdata.encode("utf-8"), lang.encode()) != 0:
            lib.TessBaseAPIDelete(handle)
            _failed_langs.add(lang)
            return None
        # Діагностику ("Estimating resolution...") — геть з консолі, як робив
        # субпроцес; поведінка оцінки роздільності від цього не змінюється.
        lib.TessBaseAPISetVariable(handle, b"debug_file", os.devnull.encode())
        engine = _Engine(lib, handle)
        _engines[lang] = engine
        return engine


def _load_lib_locked():
    """Вантажить libtesseract-5.dll з _lib_dir (виклик під _lock)."""
    global _lib, _lib_failed, _dll_dir_handle
    if _lib is not None or _lib_failed or not _lib_dir:
        return _lib
    dll = os.path.join(_lib_dir, DLL_NAME)
    if not os.path.exists(dll):
        _lib_failed = True
        return None
    try:
        # залежні DLL (leptonica, libpng тощо) лежать поруч із головною
        _dll_dir_handle = os.add_dll_directory(_lib_dir)
        lib = ctypes.CDLL(dll)
        lib.TessBaseAPICreate.restype = ctypes.c_void_p
        lib.TessBaseAPIInit3.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        lib.TessBaseAPIInit3.restype = ctypes.c_int
        lib.TessBaseAPISetVariable.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        lib.TessBaseAPISetPageSegMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.TessBaseAPISetImage.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        lib.TessBaseAPIGetUTF8Text.argtypes = [ctypes.c_void_p]
        lib.TessBaseAPIGetUTF8Text.restype = ctypes.c_void_p  # звільняємо самі (TessDeleteText)
        lib.TessBaseAPIClear.argtypes = [ctypes.c_void_p]
        lib.TessDeleteText.argtypes = [ctypes.c_void_p]
        lib.TessBaseAPIDelete.argtypes = [ctypes.c_void_p]
        _lib = lib
    except OSError:
        _lib_failed = True
    return _lib


class _Engine:
    """Один ініціалізований движок tesseract на мову (перевикористовується)."""

    def __init__(self, lib, handle):
        self._lib = lib
        self._handle = handle

    def read(self, image: Image.Image, psm: int, whitelist: str) -> str:
        """OCR PIL-зображення (сірий/бінарний канал 'L')."""
        if image.mode != "L":
            image = image.convert("L")
        width, height = image.size
        data = image.tobytes()
        lib, h = self._lib, self._handle
        with _lock:
            if self._handle is None:
                return ""  # закрито конкурентним configure()
            lib.TessBaseAPISetPageSegMode(h, psm)
            # whitelist діє до наступної зміни — порожній рядок скидає обмеження
            lib.TessBaseAPISetVariable(h, b"tessedit_char_whitelist", whitelist.encode())
            lib.TessBaseAPISetImage(h, data, width, height, 1, width)
            ptr = lib.TessBaseAPIGetUTF8Text(h)
            try:
                text = ctypes.cast(ptr, ctypes.c_char_p).value or b""
            finally:
                if ptr:
                    lib.TessDeleteText(ptr)
                lib.TessBaseAPIClear(h)
        return text.decode("utf-8", errors="replace")

    def close(self):
        """Звільняє движок (виклик під _lock у configure())."""
        if self._handle is not None:
            self._lib.TessBaseAPIDelete(self._handle)
            self._handle = None
