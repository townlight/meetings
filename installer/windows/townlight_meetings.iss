#ifndef MyAppVersion
  #error MyAppVersion must be supplied with /DMyAppVersion=<semver>
#endif

#define MyAppName "Townlight Meetings"
#define MyAppPublisher "Townlight"
#define MyAppExeName "install.ps1"

[Setup]
AppId={{7B10E5DE-4329-4A18-AB31-33A9A93F5EA1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Townlight\Townlight Meetings
DefaultGroupName=Townlight\Townlight Meetings
DisableProgramGroupPage=yes
OutputDir=build
OutputBaseFilename=Townlight Meetings-{#MyAppVersion}-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayName=Townlight Meetings

[Files]
Source: "..\..\install.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\docker-compose.yml"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\.dockerignore"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\Dockerfile.backend"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\Dockerfile.frontend"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\pyproject.toml"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\USER-MANUAL.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE-CODE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE-DOCS"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\townlight_meetings\*"; DestDir: "{app}\townlight_meetings"; Flags: ignoreversion recursesubdirs; Excludes: "__pycache__\*,*.pyc"
Source: "..\..\prompts\*"; DestDir: "{app}\prompts"; Flags: ignoreversion recursesubdirs
Source: "..\..\docker\*"; DestDir: "{app}\docker"; Flags: ignoreversion recursesubdirs
Source: "..\..\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs; Excludes: "playwright-report\*"
Source: "..\..\scripts\*"; DestDir: "{app}\scripts"; Flags: ignoreversion recursesubdirs; Excludes: "__pycache__\*,*.pyc,policy\*"
Source: "..\..\frontend\*"; DestDir: "{app}\frontend"; Flags: ignoreversion recursesubdirs; Excludes: "node_modules\*,dist\*,.vite\*,test-results\*,playwright-report\*"
Source: "README.md"; DestDir: "{app}\installer\windows"; Flags: ignoreversion
Source: "prereq-check.ps1"; DestDir: "{app}\installer\windows"; Flags: ignoreversion
Source: "launch-install.ps1"; DestDir: "{app}\installer\windows"; Flags: ignoreversion
Source: "launch-start.ps1"; DestDir: "{app}\installer\windows"; Flags: ignoreversion

[Icons]
Name: "{group}\Start Townlight Meetings"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\windows\launch-start.ps1"""; WorkingDir: "{app}"
Name: "{group}\Install or Repair Townlight Meetings"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\windows\launch-install.ps1"""; WorkingDir: "{app}"
Name: "{group}\Stop Townlight Meetings"; Filename: "docker"; Parameters: "compose down"; WorkingDir: "{app}"
Name: "{group}\Open Townlight Meetings Staff App"; Filename: "http://127.0.0.1:8080/"
Name: "{group}\Installer README"; Filename: "{app}\installer\windows\README.md"
Name: "{group}\Uninstall Townlight Meetings"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Start Townlight Meetings"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\windows\launch-start.ps1"""; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\windows\launch-install.ps1"""; WorkingDir: "{app}"; Description: "Install or repair Townlight Meetings now"; Flags: postinstall skipifsilent

[UninstallRun]
Filename: "docker"; Parameters: "compose down"; WorkingDir: "{app}"; Flags: runhidden; RunOnceId: "StopTownlight MeetingsStack"

[Code]
function InitializeSetup(): Boolean;
begin
  if WizardSilent then
  begin
    Result := True;
    Exit;
  end;
  Result := MsgBox(
    'Townlight Meetings is a small free open-source project, so this Windows installer is unsigned. Windows SmartScreen may show "Unknown Publisher" or "Windows protected your PC" because Windows cannot verify a paid publisher certificate. This warning is expected. It is OK to choose "More info" and "Run anyway" when this installer came from the official Townlight release source or your IT team built it from verified Townlight source.',
    mbInformation,
    MB_OKCANCEL
  ) = IDOK;
end;

function InitializeUninstall(): Boolean;
begin
  Result := MsgBox(
    'Uninstalling Townlight Meetings will stop the Docker Compose stack and remove installed source files. Docker volumes are preserved so meeting data is not erased accidentally. To intentionally delete local rehearsal data, run docker compose down -v from the install directory.',
    mbInformation,
    MB_OKCANCEL
  ) = IDOK;
end;
