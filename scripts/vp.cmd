@echo off
REM ============================================================================
REM  vp.cmd — Dev-env task launcher (Windows). MOT lenh giong nhau tren MOI may,
REM  tu thich nghi moi truong (interpreter/venv/GPU). Bam pattern capability-test.
REM
REM  BAN CHAT: doi may = lap lai tay (do Python K-052/K-057, dung venv K-013/K-047,
REM  chon extras theo GPU K-048/K-049, lint qua importlinter.api K-044). Launcher nay
REM  gom cac thao tac do thanh 1 giao dien on dinh, tu dieu chinh theo may.
REM
REM  GHI DE theo may bang bien moi truong (nap tu scripts\env.local.cmd neu co):
REM    VP_PYTHON  = interpreter base de dung venv (vd "py -3.11"); mac dinh: tu do.
REM    VP_EXTRAS  = pip extras (vd "dev,onnx,cv2,web,pt"); mac dinh: dev,onnx,cv2,web.
REM
REM  Dung: vp <env|setup|test|lint|check|verify|help>
REM  Thoat: 0 = OK · khac 0 = loi (propagate exit code cua buoc that bai).
REM ============================================================================
setlocal enabledelayedexpansion
set "HERE=%~dp0"
set "ROOT=%HERE%.."
set "VP=%ROOT%\vision-platform"
set "VENVPY=%VP%\.venv\Scripts\python.exe"

REM --- profile rieng theo may (gitignored), tuy chon ---
if exist "%HERE%env.local.cmd" call "%HERE%env.local.cmd"

REM --- resolve BASE python (de tao venv / chay stdlib) ---
if defined VP_PYTHON (
  set "BASEPY=%VP_PYTHON%"
) else (
  set "BASEPY="
  py -3 --version >nul 2>&1 && set "BASEPY=py -3"
  if not defined BASEPY ( python --version >nul 2>&1 && set "BASEPY=python" )
)

REM --- extras mac dinh (baseline da chung minh; KHONG auto-them torch: K-049) ---
if not defined VP_EXTRAS ( set "EXTRAS=dev,onnx,cv2,web" ) else ( set "EXTRAS=%VP_EXTRAS%" )

set "CMD=%~1"
if "%CMD%"=="" set "CMD=help"

if /i "%CMD%"=="env"    goto :env
if /i "%CMD%"=="setup"  goto :setup
if /i "%CMD%"=="test"   goto :test
if /i "%CMD%"=="lint"   goto :lint
if /i "%CMD%"=="check"  goto :check
if /i "%CMD%"=="verify" goto :verify
goto :help

:env
echo [vp] ROOT   = %ROOT%
echo [vp] BASEPY = %BASEPY%
if exist "%VENVPY%" ( echo [vp] VENV   = %VENVPY%  ^(exists^) ) else ( echo [vp] VENV   = ^(chua dung — chay: vp setup^) )
call :has_gpu
if not errorlevel 1 ( echo [vp] GPU    = co ^(nvidia-smi OK^) ) else ( echo [vp] GPU    = khong / khong co nvidia-smi )
echo [vp] EXTRAS = %EXTRAS%
exit /b 0

:setup
if not defined BASEPY ( echo [vp] ERROR: khong tim thay Python base ^(py/python^) de dung venv. & exit /b 9009 )
REM venv cu hong (python trong venv chay loi) -> doi ten de tao lai sach
if exist "%VENVPY%" (
  "%VENVPY%" --version >nul 2>&1
  if errorlevel 1 (
    echo [vp] venv cu HONG -^> doi sang .venv_broken
    if exist "%VP%\.venv_broken" rmdir /s /q "%VP%\.venv_broken"
    move "%VP%\.venv" "%VP%\.venv_broken" >nul 2>&1
  )
)
echo [vp] Dung venv bang: %BASEPY%  (extras=%EXTRAS%)
pushd "%VP%"
%BASEPY% -m venv .venv
if errorlevel 1 ( popd & echo [vp] ERROR: tao venv that bai & exit /b 1 )
"%VENVPY%" -m pip install --upgrade pip
"%VENVPY%" -m pip install -e ".[%EXTRAS%]"
set "RC=!errorlevel!"
popd
if not "!RC!"=="0" ( echo [vp] ERROR: pip install that bai RC=!RC! & exit /b !RC! )
echo [vp] setup XONG. Chay: vp verify
exit /b 0

:test
if not exist "%VENVPY%" ( echo [vp] ERROR: chua co venv — chay: vp setup & exit /b 1 )
pushd "%VP%"
"%VENVPY%" -m pytest -q %2 %3 %4 %5 %6
set "RC=!errorlevel!"
popd
exit /b !RC!

:lint
if not exist "%VENVPY%" ( echo [vp] ERROR: chua co venv — chay: vp setup & exit /b 1 )
pushd "%VP%"
"%VENVPY%" -c "import importlinter.api; from importlinter.application.use_cases import lint_imports; import sys; sys.exit(0 if lint_imports() else 1)"
set "RC=!errorlevel!"
popd
exit /b !RC!

:check
call "%ROOT%\tests\drift_check.cmd"
exit /b !errorlevel!

:verify
call "%~f0" test
set "T=!errorlevel!"
call "%~f0" lint
set "L=!errorlevel!"
call "%~f0" check
set "C=!errorlevel!"
echo [vp] verify: test=!T! lint=!L! drift-check=!C!
set /a SUM=T+L+C
if not "!SUM!"=="0" ( echo [vp] VERIFY FAIL & exit /b 1 )
echo [vp] VERIFY OK — test + lint + drift-check deu PASS
exit /b 0

:has_gpu
where nvidia-smi >nul 2>&1
if errorlevel 1 exit /b 1
nvidia-smi >nul 2>&1
exit /b %errorlevel%

:help
echo vp ^<task^> — dev-env launcher (tu do interpreter/GPU; ghi de: VP_PYTHON / VP_EXTRAS)
echo   env     : in moi truong da phat hien (Python/venv/GPU/extras)
echo   setup   : dung/sua venv + pip install -e .[EXTRAS]  (extras hien tai: %EXTRAS%)
echo   test    : pytest -q  (dung venv du an)
echo   lint    : import-linter qua importlinter.api (ne AV — K-044)
echo   check   : drift-check (nhat quan bo nho + RULES_VERSION)
echo   verify  : test + lint + check
echo.
echo Profile rieng may: copy scripts\env.local.cmd.example -^> scripts\env.local.cmd (gitignored)
exit /b 0
