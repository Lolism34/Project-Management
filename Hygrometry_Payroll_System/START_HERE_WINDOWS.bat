@echo off
setlocal
title Hygrometry Payroll System
cd /d "%~dp0"

where py >nul 2>&1
if not errorlevel 1 set "PAYROLL_PYTHON=py"
if defined PAYROLL_PYTHON goto python_found

where python >nul 2>&1
if not errorlevel 1 set "PAYROLL_PYTHON=python"
if defined PAYROLL_PYTHON goto python_found

echo Python was not found.
echo Install Python 3.10 or newer from https://www.python.org/downloads/
echo Select "Add Python to PATH" during installation.
pause
exit /b 1

:python_found
if exist ".venv\Scripts\python.exe" goto packages
echo Preparing the program for its first run...
%PAYROLL_PYTHON% -m venv .venv
if errorlevel 1 goto startup_error

:packages
echo Checking required packages...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto startup_error

echo Starting Hygrometry Payroll...
".venv\Scripts\python.exe" launch.py
if errorlevel 1 goto startup_error
exit /b 0

:startup_error
echo.
echo The program did not start. Keep this window open and copy the error shown above.
pause
exit /b 1
