; -- PortfolioX Setup Script --
[Setup]
AppName=PortfolioX
AppVersion=1.0.0
WizardStyle=modern dynamic
DefaultDirName={localappdata}\PortfolioX
DefaultGroupName=PortfolioX
UninstallDisplayIcon={app}\PortfolioX.exe
PrivilegesRequired=lowest
Compression=lzma2
SolidCompression=yes
OutputDir=..\installer_output

[Tasks]
name: "desktopicon"; description: "Create Desktop Icon"
name: "startmenu"; description: "Create Start Menu Folder"

[Files]
; Source: the built application folder. Run PyInstaller (portfoliox.spec)
; before building the installer so dist\PortfolioX\ exists.
Source: "..\dist\PortfolioX\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Create Start Menu icon
Name: "{group}\PortfolioX"; Filename: "{app}\PortfolioX.exe"
; Create Desktop icon
Name: "{commondesktop}\PortfolioX"; Filename: "{app}\PortfolioX.exe"

[Run]
; Run application after installation
Filename: "{app}\PortfolioX.exe"; Description: "Launch PortfolioX"; Flags: nowait
