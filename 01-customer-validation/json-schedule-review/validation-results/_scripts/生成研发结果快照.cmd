@echo off
setlocal

cd /d "%~dp0\..\.."

node "validation-results\_scripts\build-engineering-result-snapshot.mjs"
if errorlevel 1 (
  echo.
  echo Failed to generate the engineering result snapshot.
  pause
  exit /b 1
)

echo.
if /I "%~1"=="--no-open" (
  echo Done. The snapshot files have been generated.
  exit /b 0
)

echo Done. Opening the generated HTML snapshot...
start "" "%CD%\validation-results\固定资源最小工期结果.v1.html"
exit /b 0
