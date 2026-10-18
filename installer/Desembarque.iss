; Desembarque — Windows installer (Inno Setup 6.2 or newer, https://jrsoftware.org/isinfo.php)
;
; What it does, so a person never opens a terminal or edits PATH
; (docs/WINDOWS-TEST-2026-10-17.md §1):
;   1. copies the program into %LOCALAPPDATA%\Desembarque (per user, no admin)
;   2. downloads Python 3.12 from python.org when none is installed, and
;      installs it silently, per user, without touching PATH
;   3. puts "Desembarque" in the Start menu and on the Desktop; the first run
;      opens the launcher, whose check window installs the readers (~3 GB)
;      into .venv-ocr — the same code path as the ZIP (launcher/core.py)
;   4. the uninstaller (Add/Remove Programs) removes the program, .venv-ocr
;      and the handwriting model under %USERPROFILE%\.cache\kraken, and
;      leaves the PDFs and their "transcriptions" folders alone
;
; To build, on Windows: open this file in the Inno Setup Compiler and press
; Build (Ctrl+F9); or `iscc installer\Desembarque.iss` from the repo root.
; The output is installer\Output\Desembarque-Setup.exe (~2 MB: the readers
; are downloaded at first run, not bundled). Not built or run yet — the
; Linux side cannot; see installer/README.md for the checklist.

#define AppName "Desembarque"
#define AppVersion "2026.10.18"
#define PyVersion "3.12.10"
#define PyUrl "https://www.python.org/ftp/python/" + PyVersion + "/python-" + PyVersion + "-amd64.exe"

[Setup]
AppId={{7D1E2C4A-6B0F-4C5E-9A33-DESEMBARQUE01}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Allan Valin
AppPublisherURL=https://github.com/allan-valin/ocr-gene-docs
DefaultDirName={localappdata}\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=Desembarque-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
; the repository, minus what is not the program: data (gitignored, legal),
; the venvs, caches, tests, git
Source: "..\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion; \
  Excludes: ".git,.venv,.venv-ocr,.venv-kraken,data,indices,__pycache__,*.pyc,.pytest_cache,installer\Output,tests,docs\superpowers"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{code:PythonW}"; Parameters: """{app}\launcher\desembarque_launcher.py"""; WorkingDir: "{app}"; Comment: "listas de passageiros, lidas e pesquisáveis"
Name: "{autodesktop}\{#AppName}"; Filename: "{code:PythonW}"; Parameters: """{app}\launcher\desembarque_launcher.py"""; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na Área de trabalho"; GroupDescription: "Atalhos:"

[Run]
Filename: "{code:PythonW}"; Parameters: """{app}\launcher\desembarque_launcher.py"""; WorkingDir: "{app}"; \
  Description: "Abrir o {#AppName} agora (a janela instala os leitores, uns 3 GB)"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; everything the launcher installed: the venv (launcher/core.py VENV) and
; its settings; the model cache is removed in code below, with a question
Type: filesandordirs; Name: "{app}\.venv-ocr"
Type: files; Name: "{app}\launcher\settings.json"
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
var
  PyPath: string;

function PythonAt(Dir: string): Boolean;
begin
  Result := FileExists(Dir + '\pythonw.exe');
end;

{ python.org's per-user install, newest first; then all-users }
function FindPython(): string;
var
  v: Integer;
  Vers: array[0..2] of string;
  Dir: string;
begin
  Vers[0] := '313'; Vers[1] := '312'; Vers[2] := '311';
  Result := '';
  for v := 0 to 2 do begin
    Dir := ExpandConstant('{localappdata}') + '\Programs\Python\Python' + Vers[v];
    if (Result = '') and PythonAt(Dir) then Result := Dir;
    Dir := ExpandConstant('{commonpf64}') + '\Python' + Vers[v];
    if (Result = '') and PythonAt(Dir) then Result := Dir;
  end;
end;

function PythonW(Param: string): string;
begin
  if PyPath = '' then PyPath := FindPython();
  Result := PyPath + '\pythonw.exe';
end;

{ Inno Setup 6.1+: download python.org's installer and run it silently,
  per user, without touching PATH; the launcher finds it where it lands }
function InstallPython(): Boolean;
var
  DownloadPage: TDownloadWizardPage;
  Exe: string;
  ResultCode: Integer;
begin
  Result := False;
  DownloadPage := CreateDownloadPage('Instalando o Python', 'O Desembarque precisa do Python 3.12 (uns 25 MB). Baixando de python.org…', nil);
  DownloadPage.Clear;
  DownloadPage.Add('{#PyUrl}', 'python-installer.exe', '');
  DownloadPage.Show;
  try
    try
      DownloadPage.Download;
      Exe := ExpandConstant('{tmp}\python-installer.exe');
      if Exec(Exe, '/quiet InstallAllUsers=0 PrependPath=0 Include_launcher=1 Include_test=0 Include_doc=0 SimpleInstall=1', '', SW_SHOW, ewWaitUntilTerminated, ResultCode) then
        Result := (ResultCode = 0) and (FindPython() <> '');
      if not Result then
        MsgBox('A instalação do Python não terminou (código ' + IntToStr(ResultCode) + '). Instale o Python 3.12 em https://www.python.org/downloads/ e rode este instalador de novo.', mbError, MB_OK);
    except
      MsgBox('Não consegui baixar o Python: ' + GetExceptionMessage + #13#10 + 'Instale o Python 3.12 em https://www.python.org/downloads/ e rode este instalador de novo.', mbError, MB_OK);
    end;
  finally
    DownloadPage.Hide;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  PyPath := FindPython();
  if PyPath = '' then begin
    if not InstallPython() then
      Result := 'O Python não foi instalado; o Desembarque não pode continuar.'
    else
      PyPath := FindPython();
  end;
end;

{ the handwriting model lives outside the program folder (launcher/core.py
  MODEL); it is the person's choice to keep it for a reinstall }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Model: string;
begin
  if CurUninstallStep = usPostUninstall then begin
    Model := ExpandConstant('{%USERPROFILE}') + '\.cache\kraken\ppocrv6-hist';
    if DirExists(Model) then
      if MsgBox('Apagar também o modelo de letra manuscrita baixado (~60 MB, em ' + Model + ')?' + #13#10 + 'Não: ele fica para uma reinstalação não baixar de novo.', mbConfirmation, MB_YESNO) = IDYES then
        DelTree(Model, True, True, True);
  end;
end;
