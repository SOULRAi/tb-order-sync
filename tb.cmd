@echo off
setlocal
set "DIR=%~dp0"
node "%DIR%bin\tb.js" %*
