@echo off
setlocal

cd /d "%~dp0.."

set "APP_NAME=sayhey"
set "DIST_DIR=dist"
set "RAW_DIST_DIR=%DIST_DIR%\main.dist"
set "FINAL_DIST_DIR=%DIST_DIR%\%APP_NAME%"
set "ZIP_PATH=%DIST_DIR%\%APP_NAME%-windows.zip"

echo [SayHey] Building SayHey with Nuitka...

python -m nuitka ^
    --mode=standalone ^
    --windows-console-mode=disable ^
    --output-dir=%DIST_DIR% ^
    --output-filename=%APP_NAME% ^
    --windows-icon-from-ico=resource\app-icon.ico ^
    --plugin-enable=pyside6 ^
    --include-package=app_core ^
    --include-package=gui ^
    --include-package=core ^
    --include-package=python_protogen ^
    --include-data-dir=resource=resource ^
    --include-data-dir=hotwords=hotwords ^
    --include-module=sounddevice ^
    --include-module=soundcard ^
    --include-package-data=soundcard ^
    --include-package=websockets ^
    --include-module=google.protobuf ^
    --include-module=numpy ^
    --include-module=numpy.core ^
    --follow-imports ^
    --assume-yes-for-downloads ^
    --lto=no ^
    --jobs=4 ^
    main.py

if errorlevel 1 (
    echo [SayHey] Build FAILED.
    pause
    exit /b 1
)

if exist "%FINAL_DIST_DIR%" rmdir /s /q "%FINAL_DIST_DIR%"
if exist "%ZIP_PATH%" del /f /q "%ZIP_PATH%"
if exist "%RAW_DIST_DIR%" ren "%RAW_DIST_DIR%" "%APP_NAME%"

echo [SayHey] Building updater.exe...
call "%~dp0..\tools\updater\build_updater.bat"
if errorlevel 1 (
    echo [SayHey] Updater build FAILED.
    pause
    exit /b 1
)
cd /d "%~dp0.."
copy /Y "%~dp0..\tools\updater\build_out\updater.exe" "%FINAL_DIST_DIR%\updater.exe"
if errorlevel 1 (
    echo [SayHey] Copy updater.exe FAILED.
    pause
    exit /b 1
)

echo [SayHey] Packaging into zip...
powershell -NoProfile -Command "Compress-Archive -Path '%FINAL_DIST_DIR%\*' -DestinationPath '%ZIP_PATH%' -Force"

echo [SayHey] Done: %ZIP_PATH%
echo [SayHey] Folder: %FINAL_DIST_DIR%
pause
