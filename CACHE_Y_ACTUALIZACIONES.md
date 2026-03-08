# Caché y Actualización Automática

## ¿Cómo funciona el caché?

A partir de la versión 2.0, la aplicación incluye un sistema de caché automático que descarga el archivo m3u una única vez y lo guarda en memoria. Este caché se actualiza automáticamente cada 12 horas (configurable).

### Ventajas del caché

✅ **Reducción de carga**: No descarga el archivo en cada petición  
✅ **Respuesta más rápida**: Sirve el archivo desde memoria  
✅ **Actualizaciones automáticas**: Se descarga periódicamente sin intervención manual  
✅ **Manejo de errores**: Mantiene la última versión válida si falla una descarga  
✅ **Bajo uso de recursos**: Especialmente importante para servidores con muchos clientes  

### Desventajas (considerar)

⚠️ **Retraso en cambios**: Si el archivo m3u cambia, puede haber un retraso hasta la próxima actualización  
⚠️ **Consumo de memoria**: El archivo se mantiene en RAM en todo momento  

## Configuración del intervalo de actualización

### Cambiar el intervalo a través de variables de entorno

**Windows CMD:**
```cmd
set UPDATE_INTERVAL=6
python app.py
```

**Windows PowerShell:**
```powershell
$env:UPDATE_INTERVAL = "6"
python app.py
```

**Linux/Mac:**
```bash
UPDATE_INTERVAL=6 python3 app.py
```

### Valores recomendados

| Caso de uso | Intervalo | Razón |
|-------------|-----------|-------|
| Servidor muy estable | 24 horas | Menos descargas |
| Servidor normal | 12 horas (default) | Balance entre frescura y carga |
| Servidor con cambios frecuentes | 6 horas | Más actualizado |
| Servidor experimentando cambios | 1 hora | Muy fresco |
| En desarrollo/debugging | 0.5 horas (30 min) | Pruebas rápidas |

## Monitoreo del caché

### Endpoint de estado: `/status`

Accede a `http://localhost:8080/status` para obtener un JSON con todo el estado:

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

### Endpoint de salud: `/health`

```bash
curl http://localhost:8080/health
```

Respuesta cuando el caché está listo:
```json
{
  "status": "ok",
  "cache": "ready"
}
```

### Logs en la consola

La aplicación imprime logs detallados sobre las actualizaciones:

```
2026-03-08 14:30:45,123 - INFO - [ACTUALIZACIÓN PROGRAMADA] Descargando archivo m3u (cada 12h)
2026-03-08 14:30:47,456 - INFO - Descargando m3u desde: https://ejemplo.com/playlist.m3u
2026-03-08 14:30:48,789 - INFO - Reemplazo completado: 127.0.0.1 -> 192.168.1.151
2026-03-08 14:30:48,789 - INFO - Tamaño original: 5234 bytes
2026-03-08 14:30:48,789 - INFO - Tamaño modificado: 5234 bytes
2026-03-08 14:30:48,790 - INFO - [ACTUALIZACIÓN PROGRAMADA] Caché actualizado exitosamente
```

## Comportamiento en diferentes escenarios

### Escenario 1: Primera ejecución

1. La aplicación inicia
2. Descarga inmediatamente el archivo m3u
3. Lo almacena en caché
4. Programa la siguiente descarga en 12 horas
5. Sirve cliente desde el caché

### Escenario 2: Falla en descarga de actualización

Si falla una actualización programada:

1. Se registra el error en los logs
2. Se guarda el mensaje de error en `cache.last_error`
3. **El caché antiguo se mantiene** (sigue siendo válido)
4. Se intenta la descarga nuevamente en el próximo intervalo
5. Los clientes reciben la última versión válida conocida

### Escenario 3: Cliente accede con caché vacío

Si un cliente accede pero el caché aún no se ha descargado (muy poco probable):

1. El endpoint `/stream.m3u` detecta caché vacío
2. Desencadena una descarga inmediata
3. Almacena en caché
4. Sirve al cliente

## Monitoreo en producción

### Script para monitorear actualizaciones

```bash
#!/bin/bash
# monitor.sh - Monitorea las actualizaciones cada minuto

while true; do
    echo "=== $(date) ==="
    curl -s http://localhost:8080/status | jq '.cache'
    sleep 60
done
```

Ejecutar:
```bash
chmod +x monitor.sh
./monitor.sh
```

### Alertas por cambios de estado

```bash
#!/bin/bash
# Alerta si el caché tiene error

while true; do
    ERROR=$(curl -s http://localhost:8080/status | jq -r '.cache.last_error')
    if [ "$ERROR" != "null" ] && [ "$ERROR" != "" ]; then
        echo "⚠️ ERROR EN CACHÉ: $ERROR"
        # Aquí podrías enviar email, Telegram, etc.
    fi
    sleep 300  # Verificar cada 5 minutos
done
```

## Forzar actualización manual

Actualmente la actualización se produce automáticamente. En futuras versiones habrá un endpoint para forzar actualización:

```bash
# Próxima versión:
curl -X POST http://localhost:8080/update
```

Como alternativa, puedes reiniciar la aplicación para forzar una descarga inmediata.

## Desabilitar el caché (no recomendado)

Si deseas que el archivo se descargue en cada petición (útil solo para debugging), puedes:

1. Comentar la línea que inicializa el scheduler en `app.py`
2. Modificar `/stream.m3u` para llamar directamente a `download_and_modify_m3u()`

Pero **NO se recomienda esto en producción**.

## Limpieza de caché al reiniciar

El caché se vacía automáticamente cuando se reinicia la aplicación. Al iniciar:

1. Descarga inmediata del archivo m3u
2. Almacenamiento en caché
3. Programación de siguientes descargas

## Consumo de memoria

El consumo de memoria depende del tamaño del archivo m3u:

| Tamaño m3u | RAM aproximada |
|-----------|----------------|
| 1 MB | ~2 MB |
| 10 MB | ~20 MB |
| 100 MB | ~200 MB |

En máquinas modernas esto no es un problema, pero en dispositivos limitados (Raspberry Pi) considera usar un intervalo más amplio.

## Próximas características planeadas

- [ ] Endpoint para forzar actualización manual: `POST /update`
- [ ] Límite de size para el caché
- [ ] Almacenamiento en disco del caché (persistencia)
- [ ] Notificaciones cuando el archivo m3u cambia significativamente
- [ ] Historial de versiones
