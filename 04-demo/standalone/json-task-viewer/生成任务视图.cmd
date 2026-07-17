@echo off
setlocal

cd /d "%~dp0"

node "scripts\build-task-view-html.mjs"
if errorlevel 1 (
  echo.
  echo Failed to generate the HTML page.
  pause
  exit /b 1
)

echo.
if /I "%~1"=="--no-open" (
  echo Done. The HTML page has been generated.
  exit /b 0
)

echo Done. Opening the generated HTML page...
for %%F in ("output\*.html") do (
  start "" "%%~fF"
  goto :opened
)

:opened
exit /b 0
