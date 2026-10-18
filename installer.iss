[Setup]
AppId={{5787BD17-7FE8-43E8-82B2-F18CC8AD287D}
AppName=EMS QUIZ
AppVersion=0.6.0
DefaultDirName={localappdata}\Programs\EMSQuiz
DefaultGroupName=EMS QUIZ
PrivilegesRequired=lowest
OutputDir=release
OutputBaseFilename=EMSQuiz-Setup-0.6.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\EMSQuiz.exe
[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
[Tasks]
Name: "desktopicon"; Description: "바탕화면 바로가기 만들기"; Flags: checkedonce
[Files]
Source: "dist\EMSQuiz\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\EMS QUIZ"; Filename: "{app}\EMSQuiz.exe"
Name: "{autodesktop}\EMS QUIZ"; Filename: "{app}\EMSQuiz.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\EMSQuiz.exe"; Description: "EMS QUIZ 실행"; Flags: nowait postinstall skipifsilent
