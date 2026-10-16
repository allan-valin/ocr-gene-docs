@echo off
rem Double-click to open the Desembarque launcher (Windows).
cd /d "%~dp0"
where pyw >nul 2>nul && (start "" pyw launcher\desembarque_launcher.py & exit /b)
where pythonw >nul 2>nul && (start "" pythonw launcher\desembarque_launcher.py & exit /b)
where py >nul 2>nul && (py -3 launcher\desembarque_launcher.py & exit /b)
where python >nul 2>nul && (python launcher\desembarque_launcher.py & exit /b)
echo Python nao encontrado. Instale o Python 3.11 ou 3.12 em https://www.python.org/downloads/
echo e marque "Add python.exe to PATH" no instalador. Depois volte a abrir este ficheiro.
pause
