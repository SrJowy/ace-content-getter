@echo off
REM Script para ejecutar ACE Content Getter en Windows

setlocal

REM Cargar variables desde línea de comandos o usar valores por defecto
if not defined M3U_URL set M3U_URL=http://ejemplo.com/playlist.m3u
if not defined SERVER_PORT set SERVER_PORT=8080
if not defined OLD_IP set OLD_IP=127.0.0.1
if not defined NEW_IP set NEW_IP=192.168.1.151

echo.
echo ====================================
echo   ACE Content Getter
echo ====================================
echo.
echo Configuración:
echo   URL del m3u: %M3U_URL%
echo   Puerto: %SERVER_PORT%
echo   IP original: %OLD_IP%
echo   IP nueva: %NEW_IP%
echo.
echo Accede a http://localhost:%SERVER_PORT%/
echo.
echo ====================================
echo.

python app.py

pause
