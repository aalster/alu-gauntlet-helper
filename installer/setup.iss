; ALU Gauntlet Helper — Inno Setup script.
; Версію передає скрипт збірки: ISCC /DAppVersion=x.y.z installer\setup.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "ALU Gauntlet Helper"
#define AppExe "ALU Gauntlet Helper.exe"

[Setup]
AppId={{8C0F4E2A-7D31-4B6E-9A54-D2E3F1A0C7B9}
AppName={#AppName}
AppVersion={#AppVersion}
VersionInfoVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\{#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=ALU-Gauntlet-Helper-Setup-{#AppVersion}
SetupIconFile=..\resources\logo.ico
UninstallDisplayIcon={app}\{#AppExe}
CloseApplications=yes
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
Name: "autostart"; Description: "Run at Windows startup (minimized to tray)"; Flags: unchecked

[Files]
Source: "..\dist\{#AppName}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "tesseract\*"; DestDir: "{app}\tesseract"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{userprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExe}"; Parameters: "--minimized"; WorkingDir: "{app}"; Tasks: autostart

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
