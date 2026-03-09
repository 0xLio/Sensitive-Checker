@echo off
setlocal
cd /d "%~dp0"
python check_sensitive_accounts.py
pause
