@echo off
title Claude Multi-Account Switcher
cd /d "%~dp0"
python main.py %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred. Press any key to exit.
    pause >nul
)
