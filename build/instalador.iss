; Instalador do Tradutor de Mangá (Inno Setup 6). Gere antes o executável com gerar_exe.bat.
#define Versao "0.1.0"

[Setup]
AppName=Tradutor de Mangá
AppVersion={#Versao}
DefaultDirName={autopf}\TradutorManga
DefaultGroupName=Tradutor de Mangá
OutputDir=dist
OutputBaseFilename=TradutorManga-{#Versao}-instalador
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\TradutorManga.exe

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\TradutorManga\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Tradutor de Mangá"; Filename: "{app}\TradutorManga.exe"
Name: "{autodesktop}\Tradutor de Mangá"; Filename: "{app}\TradutorManga.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\TradutorManga.exe"; Description: "{cm:LaunchProgram,Tradutor de Mangá}"; Flags: nowait postinstall skipifsilent
