@echo off
setlocal
cd /d "%~dp0"

python -m pip install --upgrade pip
python -m pip install pyinstaller
pyinstaller --onefile --name csv-sensitive-checker check_sensitive_accounts.py

echo.
echo 打包完成，输出目录：
echo %~dp0dist
pause
