@echo off
setlocal

cd /d "%~dp0"

set "HOST=127.0.0.1"
set "PORT=%~1"
if "%PORT%"=="" set "PORT=8000"
set "OPEN_BROWSER=1"
if /I "%~2"=="--no-browser" set "OPEN_BROWSER=0"

set "APP_URL=http://%HOST%:%PORT%/"
set "DOCS_URL=http://%HOST%:%PORT%/docs"
set "TMP_DIR=%CD%\.tmp"
set "VENV_DIR=%CD%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "BOOTSTRAP_PYTHON="

echo [1/5] Localizando Python...
where py >nul 2>&1
if not errorlevel 1 (
  set "BOOTSTRAP_PYTHON=py -3"
) else (
  where python >nul 2>&1
  if not errorlevel 1 set "BOOTSTRAP_PYTHON=python"
)

if not defined BOOTSTRAP_PYTHON goto :python_missing

call %BOOTSTRAP_PYTHON% -m pip --version >nul 2>&1
if errorlevel 1 goto :pip_missing

if not exist "uploads" (
  mkdir "uploads"
)

if not exist "%TMP_DIR%" (
  mkdir "%TMP_DIR%"
)

set "TMP=%TMP_DIR%"
set "TEMP=%TMP_DIR%"

if not exist "%VENV_PYTHON%" (
  echo [2/5] Criando ambiente virtual...
  call %BOOTSTRAP_PYTHON% -m venv --without-pip "%VENV_DIR%"
  if errorlevel 1 goto :error
)

if not exist "%VENV_PYTHON%" (
  echo A .venv foi criada, mas o interpretador local nao foi encontrado.
  goto :error
)

echo [3/5] Validando dependencias...
"%VENV_PYTHON%" -c "import fastapi, uvicorn, numpy, multipart" >nul 2>&1
if errorlevel 1 (
  echo Dependencias ausentes. Instalando requirements.txt...
  call %BOOTSTRAP_PYTHON% -m pip --python "%VENV_PYTHON%" install -r requirements.txt
  if errorlevel 1 goto :error
)

if "%OPEN_BROWSER%"=="1" (
  echo [4/5] Abrindo o frontend no navegador...
  start "tennis-xray-frontend" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process '%APP_URL%'"
) else (
  echo [4/5] Navegador desativado por parametro.
)

echo [5/5] Iniciando backend FastAPI...
echo.
echo Frontend: %APP_URL%
echo API docs: %DOCS_URL%
echo Para encerrar, use Ctrl+C nesta janela.
echo.

"%VENV_PYTHON%" -m uvicorn backend.app.main:app --reload --host %HOST% --port %PORT%
goto :end

:python_missing
echo Python nao encontrado. Instale Python 3.11+ e tente novamente.
exit /b 1

:pip_missing
echo O pip nao esta disponivel no Python base. Reinstale o Python com pip habilitado.
exit /b 1

:error
echo Falha ao preparar ou iniciar a aplicacao.
exit /b 1

:end
endlocal
