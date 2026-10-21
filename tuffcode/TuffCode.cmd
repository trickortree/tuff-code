@echo off
setlocal DisableDelayedExpansion
rem Starts TuffCode from its source folder. Before that, and only when needed:
rem - npm install, when node_modules is missing or doesn't match package-lock.json (a fresh copy, a
rem   git pull, or an update that changed Electron, which Windows won't let npm replace while it runs);
rem - Electron's own download. Since Electron 42 npm install doesn't do it; Electron's install script
rem   does, and it does nothing when the right version is already there.
cd /d "%~dp0"
node -e "const l = require('./package-lock.json').packages, p = require('./package.json'); for (const n of Object.keys({ ...p.dependencies, ...p.devDependencies })) { let v; try { v = require('./node_modules/' + n + '/package.json').version; } catch {} if (v !== l['node_modules/' + n].version) process.exit(1); }" 2>nul || call npm install --no-fund --no-audit
node node_modules\electron\install.js
if not exist node_modules\electron\dist\electron.exe (
  where node >nul 2>nul || echo TuffCode needs Node.js. Install it from nodejs.org, then double-click TuffCode.cmd in the tuffcode folder to try again.
  where node >nul 2>nul && echo TuffCode couldn't download Electron, which it runs on. Check your internet connection, then double-click TuffCode.cmd in the tuffcode folder to try again.
  pause
  exit /b 1
)
start "" "%~dp0node_modules\electron\dist\electron.exe" "%~dp0."
