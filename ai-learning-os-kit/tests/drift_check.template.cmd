@echo off
REM ============================================================================
REM  TEMPLATE — drift-check launcher (Windows). Copy sang `tests\drift_check.cmd`.
REM
REM  BAN CHAT: hook/CI KHONG duoc hardcode ten interpreter. Theo may:
REM    - python.org -> co `py` (Python Launcher); `python` co the thieu
REM    - scoop      -> co `python`; thuong THIEU `py`
REM    - Windows Store alias `python` -> TON TAI tren PATH nhung chay loi (exit 9009)
REM  => Thu theo thu tu tin cay + KIEM KHA NANG (`--version` exit 0), KHONG chi kiem ton tai.
REM
REM  CHINH `VENV` cho dung vi tri venv cua du an (mac dinh: .venv o goc repo).
REM  Thoat: 0 = nhat quan · 1 = drift · 9009 = khong Python nao chay duoc.
REM ============================================================================
setlocal enabledelayedexpansion
set "HERE=%~dp0"
set "SCRIPT=%HERE%drift_check.py"
set "VENV=%HERE%..\.venv\Scripts\python.exe"

py -3 --version >nul 2>&1
if not errorlevel 1 (
  py -3 "%SCRIPT%" %*
  exit /b !errorlevel!
)

if exist "%VENV%" (
  "%VENV%" "%SCRIPT%" %*
  exit /b !errorlevel!
)

python --version >nul 2>&1
if not errorlevel 1 (
  python "%SCRIPT%" %*
  exit /b !errorlevel!
)

echo [drift-check] ERROR: khong tim thay Python chay duoc ^(da thu: py -3, venv, python^). 1>&2
exit /b 9009
