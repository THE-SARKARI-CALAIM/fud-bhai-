@echo off
cd /d "C:\Users\PRINCE YADAV\OneDrive\Desktop\OpenJarvis-main"
taskkill /F /IM python.exe 2>nul
del devil_bot.db 2>nul
start /B python bot.py
echo Bot started!
pause
