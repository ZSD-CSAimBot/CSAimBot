[Setup]
AppName=CsAimBot
AppVersion=1.0
AppPublisher=CsAimBot Team
DefaultDirName={pf}\CsAimBot
DefaultGroupName=CsAimBot
OutputBaseFilename=CsAimBot_Installer
Compression=none
SolidCompression=no
DiskSpanning=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin

[Files]
Source: "env_setup.ps1"; DestDir: "{tmp}"; Flags: dontcopy
Source: "dist\CsAimBot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "application\simulation\gazebo_sim.tar"; DestDir: "{app}\_internal\application\simulation"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\CsAimBot"; Filename: "{app}\CsAimBot.exe"
Name: "{commondesktop}\CsAimBot"; Filename: "{app}\CsAimBot.exe"

[Run]
Filename: "{app}\CsAimBot.exe"; Parameters: "--export-only"; StatusMsg: "Eksportowanie modelu YOLO do formatu TensorRT (moze to potrwac kilka minut)..."; Flags: waituntilterminated
Filename: "wsl.exe"; Parameters: "-d Ubuntu -e bash -c ""docker load -i $(wslpath '{app}\_internal\application\simulation\gazebo_sim.tar')"""; StatusMsg: "Wczytywanie obrazu Gazebo do Dockera na WSL..."; Flags: waituntilterminated skipifdoesntexist

[Code]
procedure InitializeWizard;
var
  InfoPage: TOutputMsgWizardPage;
begin
  InfoPage := CreateOutputMsgPage(wpWelcome,
    'Konfiguracja Srodowiska (Prerekwizyty)',
    'Zanim rozpocznie sie wlasciwe kopiowanie plikow, instalator sprawdzi Twoje srodowisko.',
    'Aplikacja CsAimBot wymaga do prawidlowego dzialania:' + #13#10 + #13#10 +
    '1. Srodowiska WSL z dystrybucja Ubuntu' + #13#10 +
    '2. Dockera dzialajacego natywnie wewnatrz Ubuntu' + #13#10 +
    '3. Natywnego NVIDIA CUDA Toolkit 12.8' + #13#10 + #13#10 +
    'Po kliknieciu "Dalej", specjalny skrypt sprawdzi obecnosc tych komponentow ' +
    'i w razie potrzeby automatycznie je pobierze i zainstaluje.' + #13#10 + #13#10 +
    'UWAGA: Instalacja moze potrwac od kilku do kilkunastu minut. Ponadto, jesli to Twoja pierwsza instalacja WSL, ' +
    'po jej zakonczeniu moze byc wymagany restart komputera.');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  ExtractTemporaryFile('env_setup.ps1');
  Exec('powershell.exe', 
       '-ExecutionPolicy Bypass -NoLogo -File "' + ExpandConstant('{tmp}\env_setup.ps1') + '"', 
       '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;