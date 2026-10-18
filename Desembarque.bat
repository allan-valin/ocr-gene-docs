@echo off
rem Double-click to open the Desembarque launcher (Windows).
rem Finds a Python 3 without the person touching PATH; installs one from
rem python.org, silently and per-user, when there is none. (Windows test,
rem 2026-10-17: "Add python.exe to PATH" is the step a non-programmer cannot do.)
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "PYW="

rem 1. python.org's per-user install, where its installer puts it by default
rem    (PATH or not); newest first
for %%v in (313 312 311) do (
  if not defined PYW if exist "%LOCALAPPDATA%\Programs\Python\Python%%v\pythonw.exe" set "PYW=%LOCALAPPDATA%\Programs\Python\Python%%v\pythonw.exe"
)
rem 2. an all-users install
for %%v in (313 312 311) do (
  if not defined PYW if exist "%ProgramFiles%\Python%%v\pythonw.exe" set "PYW=%ProgramFiles%\Python%%v\pythonw.exe"
)
rem 3. the py launcher, which python.org installs on the PATH on its own
if not defined PYW (
  py -3 -c "import tkinter" >nul 2>nul && set "PYW=pyw -3"
)
rem 4. whatever pythonw is on the PATH, but not the Microsoft Store's stub,
rem    which opens the Store instead of running anything
if not defined PYW (
  for /f "delims=" %%p in ('where pythonw 2^>nul') do call :found "%%p"
)
if defined PYW goto :run

rem 5. none: install Python 3.12 from python.org, per user, silently, without
rem    touching PATH (this file finds it under %LOCALAPPDATA% next time)
echo Python nao encontrado. Vou baixar e instalar o Python 3.12 (uns 25 MB, 1 a 2 minutos)...
set "PYURL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
set "PYEXE=%TEMP%\python-3.12.10-amd64.exe"
curl.exe -L -# -o "%PYEXE%" "%PYURL%"
if not exist "%PYEXE%" (
  echo Nao consegui baixar. Instale o Python 3.12 em https://www.python.org/downloads/
  echo e abra este arquivo de novo. Nao precisa marcar "Add python.exe to PATH".
  pause
  exit /b 1
)
"%PYEXE%" /quiet InstallAllUsers=0 PrependPath=0 Include_launcher=1 Include_test=0 Include_doc=0 SimpleInstall=1
del "%PYEXE%" >nul 2>nul
if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" (
  set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
  echo Python instalado.
  goto :run
)
echo A instalacao do Python nao terminou. Instale-o em https://www.python.org/downloads/
echo e abra este arquivo de novo.
pause
exit /b 1

:run
rem pythonw: no console window behind the launcher
if "%PYW%"=="pyw -3" (
  start "" pyw -3 "launcher\desembarque_launcher.py"
) else (
  start "" "%PYW%" "launcher\desembarque_launcher.py"
)
endlocal
exit /b 0

:found
if defined PYW exit /b 0
echo %~1 | find /i "WindowsApps" >nul && exit /b 0
set "PYW=%~1"
exit /b 0
