@echo off
echo Building application...

pyinstaller --clean main.spec

if %errorlevel% neq 0 (
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Build complete.
echo EXE is in the dist folder.
pause