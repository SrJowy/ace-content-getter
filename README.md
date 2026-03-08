# ACE Content Getter

Aplicación que descarga un archivo m3u desde una URL, reemplaza direcciones IP y sirve el contenido modificado mediante un servidor HTTP con **actualización automática cada 12 horas**.

## Características

- ✅ Descarga de archivos m3u desde URL HTTP
- ✅ Reemplazo automático de direcciones IP
- ✅ Servidor HTTP para servir el contenido modificado
- ✅ **Caché en memoria para respuestas rápidas**
- ✅ **Actualización automática cada 12 horas** (configurable)
- ✅ Configuración flexible mediante variables de entorno
- ✅ Logging detallado
- ✅ Validación de salud del servidor
- ✅ Monitoreo de estado del caché

## Instalación

1. **Clonar o descargar el proyecto**

2. **Instalar dependencias:**
```bash
pip install -r requirements.txt
```

3. **Configurar las variables de entorno:**
```bash
# Copiar el archivo de ejemplo
cp .env.example .env

# Editar .env con tus valores
```

Las variables de entorno disponibles son:

| Variable | Descripción | Valor por defecto |
|----------|-------------|-------------------|
| `M3U_URL` | URL del archivo m3u a descargar | `http://ejemplo.com/playlist.m3u` |
| `SERVER_PORT` | Puerto del servidor HTTP | `8080` |
| `OLD_IP` | IP a reemplazar | `127.0.0.1` |
| `NEW_IP` | IP nueva | `192.168.1.151` |
| `UPDATE_INTERVAL` | Horas entre actualizaciones automáticas | `12` |

## Uso

### Opción 1: Con variables de entorno desde línea de comandos (Windows)

```cmd
set M3U_URL=http://mi-servidor.com/playlist.m3u
set SERVER_PORT=8080
set OLD_IP=127.0.0.1
set NEW_IP=192.168.1.151
python app.py
```

### Opción 2: Usando archivo .env

```bash
python app.py
```

La aplicación se iniciará en `http://localhost:8080`

## Endpoints disponibles

### Página de inicio
```
GET http://localhost:8080/
```
Muestra la configuración actual, estado del caché y los endpoints disponibles.

### Descargar archivo m3u modificado
```
GET http://localhost:8080/stream.m3u
```
Descarga el archivo m3u con las IPs reemplazadas. Sirve desde caché en memoria.

### Obtener estado de la aplicación
```
GET http://localhost:8080/status
```
Retorna un JSON con:
- Estado del caché
- Hora de última actualización
- Si hay actualización en progreso
- Errores en la última actualización
- Configuración actual

Ejemplo:
```json
{
  "server": "running",
  "cache": {
    "available": true,
    "last_update": "2026-03-08T14:30:45.123456",
    "update_in_progress": false,
    "last_error": null
  },
  "configuration": {
    "update_interval_hours": 12,
    "m3u_url": "https://ejemplo.com/playlist.m3u",
    "old_ip": "127.0.0.1",
    "new_ip": "192.168.1.151"
  }
}
```

### Verificar estado del servidor
```
GET http://localhost:8080/health
```
Retorna estado simple:
```json
{
  "status": "ok",
  "cache": "ready"
}
```

## Flujo de funcionamiento

1. El cliente accede a `/stream.m3u`
2. La aplicación descarga el archivo m3u desde la URL configurada
3. Reemplaza todas las instancias de la IP antigua por la nueva
4. Retorna el archivo modificado al cliente

## Ejemplo de uso con VLC

Una vez que el servidor esté corriendo, puedes acceder desde VLC:

1. Archivo → Abrir ubicación de red
2. Escribe: `http://localhost:8080/stream.m3u`
3. El reproductor cargará el contenido con las IPs reemplazadas

## Actualización automática del caché

La aplicación descarga automáticamente el archivo m3u **cada 12 horas** (configurable). Esto significa:

✅ El archivo se mantiene actualizado sin intervención manual  
✅ Las respuestas son rápidas (seridas desde caché en memoria)  
✅ Si falla una descarga, se mantiene la última versión válida  
✅ Puedes cambiar el intervalo con la variable `UPDATE_INTERVAL`  

**Ver:** [CACHE_Y_ACTUALIZACIONES.md](CACHE_Y_ACTUALIZACIONES.md) para máss detalles sobre monitoreo y configuración avanzada.

## Requisitos del sistema

- Python 3.7 o superior
- Las dependencias especificadas en `requirements.txt`

## Notas importantes

- El reemplazo de IP es simple y reemplaza **todas** las instancias de la IP antigua
- El archivo m3u se cachea en memoria y se actualiza automáticamente cada 12 horas
- El caché se vacía al reiniciar la aplicación
- El servidor corre en `0.0.0.0` para aceptar conexiones de cualquier interfaz
- Consulta `/status` para monitorear el estado del caché

## Ejemplo de archivo m3u

```
#EXTM3U
#EXTINF:-1,Canal 1
http://127.0.0.1:8888/stream1
#EXTINF:-1,Canal 2
http://127.0.0.1:9999/stream2
```

Después del procesamiento:

```
#EXTM3U
#EXTINF:-1,Canal 1
http://192.168.1.151:8888/stream1
#EXTINF:-1,Canal 2
http://192.168.1.151:9999/stream2
```

## Troubleshooting

**Error: "Cannot connect to the server"**
- Verifica que `M3U_URL` apunte a una URL válida y accesible
- Comprueba la conectividad de red

**Error: "No module named 'flask'"**
- Ejecuta: `pip install -r requirements.txt`

**El archivo m3u no se modifica correctamente**
- Verifica que `OLD_IP` coincide exactamente con la IP en el archivo m3u
- Revisa los logs para más detalles

## Licencia

MIT
