# Збірка інсталятора

## Передумови

1. **Inno Setup 6** — установка не потрібна: завантаж NuGet-пакет `Tools.InnoSetup`
   (https://www.nuget.org/api/v2/package/Tools.InnoSetup, це zip) і розпакуй у `installer/innosetup/`
   так, щоб існував `installer/innosetup/tools/ISCC.exe` (тека в .gitignore).
   Альтернатива: класична установка з https://jrsoftware.org/isinfo.php — скрипт знайде її сам.
2. **Портативний Tesseract** у `installer/tesseract/` (тека в .gitignore):
   - встанови Tesseract (UB Mannheim build) або візьми вже встановлений;
   - скопіюй вміст його теки (tesseract.exe, *.dll, tessdata/ з eng.traineddata) в `installer/tesseract/`;
   - перевір: `installer\tesseract\tesseract.exe --version` працює.
   Без цієї теки інсталятор збереться, але без бандленого OCR.

## Збірка

    powershell -File scripts/build_installer.ps1

Результат: `dist/installer/ALU-Gauntlet-Helper-Setup-<версія>.exe`.
Версія береться з `alu_gauntlet_helper/version.py`.
