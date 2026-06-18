# Збирає onedir-білд PyInstaller і пакує його в інсталятор Inno Setup.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

$versionLine = Select-String -Path "alu_gauntlet_helper\version.py" -Pattern 'APP_VERSION\s*=\s*"([^"]+)"'
if (-not $versionLine) { throw "APP_VERSION not found in alu_gauntlet_helper\version.py" }
$version = $versionLine.Matches[0].Groups[1].Value
Write-Host "Building ALU Gauntlet Helper $version"

if (-not (Test-Path "installer\tesseract\tesseract.exe")) {
    throw "installer\tesseract\tesseract.exe not found - bundled OCR is required (see installer\README.md)"
}
if (-not (Test-Path "installer\tesseract\tessdata\eng.traineddata")) {
    throw "installer\tesseract\tessdata\eng.traineddata not found - bundled OCR is required (see installer\README.md)"
}

& "$root\.venv\Scripts\pyinstaller.exe" main.spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw "pyinstaller failed" }

$iscc = "$root\installer\innosetup\tools\ISCC.exe"
if (-not (Test-Path $iscc)) { $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
if (-not (Test-Path $iscc)) { $iscc = "$env:ProgramFiles\Inno Setup 6\ISCC.exe" }
if (-not (Test-Path $iscc)) { $iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" }
if (-not (Test-Path $iscc)) { throw "Inno Setup 6 (ISCC.exe) not found - see installer\README.md" }

& $iscc "/DAppVersion=$version" "installer\setup.iss"
if ($LASTEXITCODE -ne 0) { throw "ISCC failed" }

Write-Host "Done: dist\installer\ALU-Gauntlet-Helper-Setup-$version.exe"
