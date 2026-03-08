::
:: Script para preparar el entorno Docker en Windows
:: Ejecuta este script una única vez para configurar todo
::

@echo off
setlocal enabledelayedexpansion

echo.
echo ╔════════════════════════════════════════════════════════════════════╗
echo ║          ACE Content Getter - Docker Setup para Windows            ║
echo ╚════════════════════════════════════════════════════════════════════╝
echo.

REM Verificar si Docker está instalado
docker --version >nul 2>&1
if !errorlevel! neq 0 (
    echo ✗ ERROR: Docker no está instalado
    echo.
    echo Por favor instala Docker Desktop desde:
    echo https://www.docker.com/products/docker-desktop
    echo.
    pause
    exit /b 1
)

echo ✓ Docker detectado
docker --version

echo.

REM Verificar si docker-compose está disponible
docker-compose --version >nul 2>&1
if !errorlevel! neq 0 (
    docker compose version >nul 2>&1
    if !errorlevel! neq 0 (
        echo ✗ ERROR: Docker Compose no está disponible
        echo.
        echo Asegúrate de tener la última versión de Docker Desktop
        echo.
        pause
        exit /b 1
    ) else (
        echo ✓ Docker Compose v2 detectado
        docker compose version
    )
) else (
    echo ✓ Docker Compose detectado
    docker-compose --version
)

echo.

REM Crear archivo .env si no existe
if not exist .env (
    echo Creando archivo .env...
    (
        echo # URL del archivo m3u a descargar
        echo M3U_URL=https://ipfs.io/ipns/k2k4r8oqlcjxsritt5mczkcn4mmvcmymbqw7113fz2flkrerfwfps004/data/listas/lista_iptv.m3u
        echo.
        echo # IP original a reemplazar
        echo OLD_IP=127.0.0.1
        echo.
        echo # IP nueva
        echo NEW_IP=192.168.1.151
        echo.
        echo # Intervalo de actualización
        echo UPDATE_INTERVAL=12
    ) > .env
    echo ✓ Archivo .env creado
    echo.
    echo IMPORTANTE: Edita .env con tus valores
    echo.
) else (
    echo ✓ Archivo .env ya existe
    echo.
    echo Para cambiar la configuración, edita el archivo .env
    echo.
)

REM Compilar la imagen
echo.
echo ╔════════════════════════════════════════════════════════════════════╗
echo ║                        Compilando imagen...                         ║
echo ╚════════════════════════════════════════════════════════════════════╝
echo.

docker-compose build

if !errorlevel! equ 0 (
    echo.
    echo ╔════════════════════════════════════════════════════════════════════╗
    echo ║                     ¡Setup completado!                             ║
    echo ╚════════════════════════════════════════════════════════════════════╝
    echo.
    echo Próximos pasos:
    echo.
    echo 1. Edita el archivo .env si quieres cambiar la configuración
    echo.
    echo 2. Inicia el contenedor con uno de estos comandos:
    echo.
    echo    docker-compose up -d
    echo    o
    echo    docker-docker.bat up
    echo.
    echo 3. Accede a http://localhost:8080/
    echo.
    echo 4. Ver logs con:
    echo.
    echo    docker-compose logs -f
    echo    o
    echo    docker-docker.bat logs
    echo.
    echo Comandos útiles:
    echo.
    echo   docker-docker.bat up          - Iniciar
    echo   docker-docker.bat down        - Detener
    echo   docker-docker.bat logs        - Ver logs
    echo   docker-docker.bat status      - Estado
    echo   docker-docker.bat restart     - Reiniciar
    echo   docker-docker.bat clean       - Limpiar todo
    echo.
) else (
    echo.
    echo ✗ ERROR durante la compilación
    echo.
    pause
    exit /b 1
)

echo.
pause
