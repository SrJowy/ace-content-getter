@echo off
REM Script para gestionar Docker Compose fácilmente en Windows

setlocal enabledelayedexpansion

if "%1%"=="" (
    goto show_help
)

if /i "%1%"=="up" (
    echo Iniciando contenedor...
    docker-compose up -d
    if !errorlevel! equ 0 (
        echo.
        echo ✓ Contenedor iniciado exitosamente
        echo.
        echo Accede a: http://localhost:8080/
        echo.
        echo Para ver logs: docker-docker.bat logs
    )
    goto end
)

if /i "%1%"=="down" (
    echo Deteniendo contenedor...
    docker-compose down
    if !errorlevel! equ 0 (
        echo ✓ Contenedor detenido
    )
    goto end
)

if /i "%1%"=="logs" (
    echo Mostrando logs en tiempo real (presiona Ctrl+C para salir)...
    docker-compose logs -f ace-content-getter
    goto end
)

if /i "%1%"=="status" (
    echo Estado del contenedor:
    docker-compose ps
    goto end
)

if /i "%1%"=="build" (
    echo Compilando imagen...
    docker-compose build
    if !errorlevel! equ 0 (
        echo ✓ Imagen compilada exitosamente
    )
    goto end
)

if /i "%1%"=="rebuild" (
    echo Recompilando imagen sin caché...
    docker-compose build --no-cache
    if !errorlevel! equ 0 (
        echo ✓ Imagen recompilada exitosamente
    )
    goto end
)

if /i "%1%"=="restart" (
    echo Reiniciando contenedor...
    docker-compose restart ace-content-getter
    if !errorlevel! equ 0 (
        echo ✓ Contenedor reiniciado
    )
    goto end
)

if /i "%1%"=="shell" (
    echo Abriendo shell dentro del contenedor...
    docker-compose exec ace-content-getter /bin/bash
    goto end
)

if /i "%1%"=="clean" (
    echo Limpiando contenedores y volúmenes...
    docker-compose down -v
    if !errorlevel! equ 0 (
        echo ✓ Limpieza completada
    )
    goto end
)

if /i "%1%"=="test" (
    echo Probando conectividad...
    for /f %%i in ('docker-compose ps -q ace-content-getter') do set "CONTAINER=%%i"
    if defined CONTAINER (
        docker-compose exec ace-content-getter curl -s http://localhost:8080/health
        echo.
        echo ✓ Servidor respondiendo
    ) else (
        echo ✗ Contenedor no está corriendo
    )
    goto end
)

:show_help
echo.
echo ╔════════════════════════════════════════════════════════════════════╗
echo ║        ACE Content Getter - Docker Management Scripts              ║
echo ╚════════════════════════════════════════════════════════════════════╝
echo.
echo Uso: docker-docker.bat [opción]
echo.
echo Opciones disponibles:
echo.
echo   up          - Iniciar el contenedor
echo   down        - Detener el contenedor
echo   restart     - Reiniciar el contenedor
echo   logs        - Ver logs en tiempo real
echo   status      - Ver estado del contenedor
echo   build       - Compilar la imagen Docker
echo   rebuild     - Recompilar sin caché
echo   shell       - Abrir shell dentro del contenedor
echo   test        - Probar conectividad
echo   clean       - Detener y eliminar todo (volúmenes incluidos)
echo.
echo Ejemplos:
echo.
echo   docker-docker.bat up              # Inicia el contenedor
echo   docker-docker.bat logs            # Ver logs del contenedor
echo   docker-docker.bat status          # Ver estado
echo.
echo Configuración:
echo   - Editar .env para cambiar variables
echo   - Editar docker-compose.yml para cambiar puertos/recursos
echo.
goto end

:end
endlocal
