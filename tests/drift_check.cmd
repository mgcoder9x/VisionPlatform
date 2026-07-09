@echo off
REM ============================================================================
REM  drift-check launcher (Windows) — tim Python CHAY DUOC roi chay drift_check.py
REM
REM  BAN CHAT: hook/CI KHONG duoc hardcode ten interpreter. Theo may:
REM    - cai tu python.org -> co lenh `py` (Python Launcher), `python` co the thieu
REM    - cai tu scoop      -> co `python`, thuong THIEU `py`
REM    - Windows Store alias `python` -> TON TAI tren PATH nhung chay loi (exit 9009)
REM  => Thu theo thu tu tin cay + KIEM KHA NANG (`--version` exit 0), KHONG chi kiem
REM     ton tai (vi Store-alias ton tai ma chay hong). Dung interpreter dau tien chay duoc.
REM
REM  Thoat: 0 = ban ghi nhat quan · 1 = co drift · 9009 = khong Python nao chay duoc.
REM ============================================================================
setlocal enabledelayedexpansion
set "HERE=%~dp0"
set "SCRIPT=%HERE%drift_check.py"
set "VENV=%HERE%..\vision-platform\.venv\Scripts\python.exe"

REM 1) py -3 (Python Launcher chuan Windows)
py -3 --version >nul 2>&1
if not errorlevel 1 (
  py -3 "%SCRIPT%" %*
  exit /b !errorlevel!
)

REM 2) venv du an (luon dung neu da dung venv)
if exist "%VENV%" (
  "%VENV%" "%SCRIPT%" %*
  exit /b !errorlevel!
)

REM 3) python (may scoop / PATH that su co python.org)
python --version >nul 2>&1
if not errorlevel 1 (
  python "%SCRIPT%" %*
  exit /b !errorlevel!
)

echo [drift-check] ERROR: khong tim thay Python chay duoc ^(da thu: py -3, venv, python^). 1>&2
exit /b 9009
