; -- PortfolioX Setup Script --
; Demonstrates copying application files and creating icons.

; SEE THE DOCUMENTATION FOR DETAILS ON CREATING .ISS SCRIPT FILES!

[Setup]
AppName=PortfolioX
AppVersion=1.0.0
WizardStyle=modern dynamic
DefaultDirName={commonpf}\PortfolioX
DefaultGroupName=PortfolioX
UninstallDisplayIcon={app}\app.exe
Compression=lzma2
SolidCompression=yes
OutputDir=userdocs:PortfolioX Output

[Tasks]
name: "desktopicon"; description: "Create Desktop Icon"
name: "startmenu"; description: "Create Start Menu Folder"

[Files]
; Source files - copy application files
Source: "<repo>\app.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "<repo>\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "<repo>\start.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "<repo>\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "<repo>\referance\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Create Start Menu icon
Name: "{group}\PortfolioX"; Filename: "{app}\app.py"; IconFileName: "{app}\icon.ico"
; Create Desktop icon
Name: "{commondesktop}\PortfolioX"; Filename: "{app}\start.bat"; IconFileName: "{app}\icon.ico"

[Run]
; Run application after installation
Filename: "{app}\start.bat"; Description: "Launch PortfolioX"; Flags: nowait