#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif
#ifndef BundleDir
  #define BundleDir "..\release\portable\LSC-Control"
#endif
#ifndef OutputDir
  #define OutputDir "..\release"
#endif

[Setup]
AppId={{2B1F5F9C-3261-445A-92B8-747E362EF04E}
AppName=LSC Control
AppVersion={#AppVersion}
AppPublisher=BLK185
AppPublisherURL=https://github.com/BLK185/lsc-control
AppSupportURL=https://github.com/BLK185/lsc-control/issues
AppUpdatesURL=https://github.com/BLK185/lsc-control/releases
DefaultDirName={localappdata}\Programs\LSC Control
DefaultGroupName=LSC Control
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\LSC-Control.exe
OutputDir={#OutputDir}
OutputBaseFilename=LSC-Control-{#AppVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
#ifdef IconFile
SetupIconFile={#IconFile}
#endif

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le bureau"; Flags: unchecked

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "private\*,portable-identity.json,client-identity.json,settings.json,devices.json,tinytuya.json,snapshot.json,*.log"

[Icons]
Name: "{group}\LSC Control"; Filename: "{app}\LSC-Control.exe"
Name: "{autodesktop}\LSC Control"; Filename: "{app}\LSC-Control.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\LSC-Control.exe"; Description: "Lancer LSC Control"; Flags: nowait postinstall skipifsilent
