; Inno Setup Script for Radar
; Generates a professional installer and compresses the application.

[Setup]
AppId={{C7A9D2E5-7BFE-4D4F-9E3A-7B5D6E1A2B3C}
AppName=Radar
AppVersion=0.1.0
AppPublisher=ThatOneFBIAgent
AppPublisherURL=https://github.com/ThatOneFBIAgent/Radar
AppSupportURL=https://github.com/ThatOneFBIAgent/Radar/issues
AppUpdatesURL=https://github.com/ThatOneFBIAgent/Radar/releases
DefaultDirName={autopf}\Radar
DisableProgramGroupPage=yes
; The [Files] section below handles the contents.
; OutputDir is relative to this script.
OutputDir=dist
OutputBaseFilename=Radar_v0.1.0_Setup
SetupIconFile=assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main Executable
Source: "dist\radar\radar.exe"; DestDir: "{app}"; Flags: ignoreversion
; All bundled internal files
Source: "dist\radar\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
; EXPOSED CONFIGS: We place these directly in the {app} folder so users can edit them easily.
; Our code is already configured to prioritize these over the internal ones.
Source: "config.toml"; DestDir: "{app}"; Flags: ignoreversion
Source: "themes\*"; DestDir: "{app}\themes"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Radar"; Filename: "{app}\radar.exe"; Parameters: "--quiet"
Name: "{autodesktop}\Radar"; Filename: "{app}\radar.exe"; Parameters: "--quiet"; Tasks: desktopicon

[Run]
Filename: "{app}\radar.exe"; Parameters: "--quiet"; Description: "{cm:LaunchProgram,Radar}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\themes"
Type: files; Name: "{app}\config.toml"
