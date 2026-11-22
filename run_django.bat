@echo off
call "%~dp0.venv\Scripts\activate.bat"
python "%~dp0manage.py" runserver 127.0.0.1:8050
pause
