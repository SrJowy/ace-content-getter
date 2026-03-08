# Guía de uso avanzada - ACE Content Getter

## Ejecución desde línea de comandos

### Windows CMD

```cmd
:: Opción 1: Ejecutar con configuración por defecto
python app.py

:: Opción 2: Establecer variables antes de ejecutar
set M3U_URL=http://tu-servidor.com/playlist.m3u
set SERVER_PORT=8080
set OLD_IP=127.0.0.1
set NEW_IP=192.168.1.151
python app.py

:: Opción 3: Usar el script batch
run.bat
```

### Windows PowerShell

```powershell
# Establecer variables de entorno
$env:M3U_URL = "http://tu-servidor.com/playlist.m3u"
$env:SERVER_PORT = "8080"
$env:OLD_IP = "127.0.0.1"
$env:NEW_IP = "192.168.1.151"
python app.py
```

### Linux / Mac

```bash
# Opción 1: Ejecutar con configuración por defecto
python3 app.py

# Opción 2: Establecer variables en la misma línea
M3U_URL=http://tu-servidor.com/playlist.m3u SERVER_PORT=8080 python3 app.py

# Opción 3: Usar el script bash
chmod +x run.sh
./run.sh

# Opción 4: Ejecutar en background
nohup python3 app.py > app.log 2>&1 &
```

## Casos de uso comunes

### Caso 1: Servidor IPTV local que necesita cambiar IP

Tu servidor IPTV original genera un m3u con URLs como:
```
http://127.0.0.1:8888/stream
http://127.0.0.1:8889/stream
```

Necesitas servir este m3u a otros dispositivos de la red (Smart TV, Kodi, etc.) pero con la IP de la máquina.

Configuración:
```
M3U_URL=http://localhost:8888/playlist.m3u
OLD_IP=127.0.0.1
NEW_IP=192.168.1.100    (IP de la máquina en la red)
SERVER_PORT=9000        (Puerto diferente para evitar conflicto)
```

Desde la Smart TV o Kodi:
```
http://192.168.1.100:9000/stream.m3u
```

### Caso 2: Proxy inverso para múltiples fuentes

Si tienes múltiples servidores m3u, podrías crear múltiples instancias de esta aplicación:

**Instancia 1:**
```
M3U_URL=http://servidor1.com/playlist.m3u
SERVER_PORT=8001
```

**Instancia 2:**
```
M3U_URL=http://servidor2.com/playlist.m3u
SERVER_PORT=8002
```

Acceso:
```
http://localhost:8001/stream.m3u
http://localhost:8002/stream.m3u
```

### Caso 3: Actualizar a través de firewall

Si el reproductor no puede acceder directamente a la URL original:

Configuración:
```
M3U_URL=http://192.168.1.50:8888/playlist.m3u    (servidor original)
OLD_IP=192.168.1.50
NEW_IP=192.168.1.100
```

### Caso 4: Ejecutar como servicio en Windows

Crear un archivo `run_service.vbs`:

```vbscript
Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Cambiar al directorio de la aplicación
strPath = objFSO.GetParentFolderName(WScript.ScriptFullName)
objShell.CurrentDirectory = strPath

' Ejecutar la aplicación sin mostrar ventana
objShell.Run "python app.py", 0, False
```

Luego crear una tarea programada:
1. Presionar `Win + R`
2. Digite `taskschd.msc`
3. Crear tarea básica
4. Asignar a inicio de sesión
5. Accionar: explorar y seleccionar `run_service.vbs`

## Gestión del caché

Por defecto, el archivo se descarga en cada acceso. Para versiones posteriores que implementen caché:

```
# Descargar cada vez (default)
CACHE_ENABLED=false

# Cachear durante 5 minutos
CACHE_ENABLED=true
CACHE_TTL=300
```

## Monitoreo

Ver los logs:

**Windows:**
```cmd
python app.py > app.log 2>&1
type app.log
```

**Linux:**
```bash
python3 app.py > app.log 2>&1 &
tail -f app.log
```

## Seguridad

Para producción, considere:

1. **HTTPS:** Usar un proxy reverso (nginx, Apache)
2. **Autenticación:** Agregar token/API key a `/stream.m3u`
3. **Rate limiting:** Limitar accesos por IP
4. **Validación:** Validar que el m3u es válido

## Troubleshooting

**La aplicación no inicia:**
```
- Verificar que Python está instalado: python --version
- Verificar que las dependencias están instaladas: pip list
- Revisar si el puerto ya está en uso
```

**No descarga el m3u:**
```
- Verificar que M3U_URL es accesible: curl http://...
- Verificar firewall/proxy
- Revisar logs para más detalles
```

**El reemplazo no funciona:**
```
- Asegurarse que OLD_IP exacta está en el archivo
- Considerar mayúsculas/minúsculas
- Descargar el m3u manualmente para ver su contenido
```

## Ejemplo completo en Docker (opcional)

Si queremos ejecutar en Docker en el futuro:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV M3U_URL=http://ejemplo.com/playlist.m3u
ENV SERVER_PORT=8080
ENV OLD_IP=127.0.0.1
ENV NEW_IP=192.168.1.151

EXPOSE 8080

CMD ["python", "app.py"]
```

Ejecutar:
```bash
docker build -t ace-content-getter .
docker run -e M3U_URL=http://... -p 8080:8080 ace-content-getter
```

## Contacto y soporte

Para reportar problemas o sugerencias, contacta al desarrollador.
