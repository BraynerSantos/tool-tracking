@echo off
cd /d "%~dp0"
pushd client
call npm run build
if errorlevel 1 popd & exit /b 1
popd
.venv\Scripts\pyinstaller tooldb.spec --noconfirm
if errorlevel 1 exit /b 1
rem Ship the documentation with the app so it is always at hand on the server.
xcopy /e /i /y docs\guides dist\ToolDB\docs >nul
echo Done: dist\ToolDB\ToolDB.exe
