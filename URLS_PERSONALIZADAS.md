# URLs Personalizadas

## Descripción

La aplicación ahora permite a los usuarios agregar URLs personalizadas de archivos M3U a través de la interfaz web. Las URLs se guardan de forma persistente en un archivo JSON y se incluyen automáticamente en cada actualización del caché.

## Características

✨ **Agregar URLs desde la web**: Interfaz intuitiva para agregar nuevas listas de reproducción
💾 **Persistencia**: Las URLs se guardan en `custom_urls.json`
🔄 **Actualización automática**: Las URLs personalizadas se incluyen en cada actualización de caché
🗑️ **Gestión fácil**: Eliminar URLs directamente desde el panel
📊 **API REST**: Endpoints para gestionar URLs programáticamente

## Uso

### Interfaz Web

1. Abre la aplicación en tu navegador: `http://localhost:8082`
2. Ve a la sección "Agregar URL Personalizada"
3. Ingresa la URL completa del archivo M3U (ej: `https://ejemplo.com/playlist.m3u`)
4. (Opcional) Agrega un nombre descriptivo
5. Haz clic en "Agregar URL"
6. El caché se actualizará automáticamente

### Gestión de URLs

- **Ver URLs**: En la sección "URLs Personalizadas" se muestra la lista completa
- **Eliminar URL**: Haz clic en el botón "Eliminar" junto a la URL que deseas quitar
- **Información**: Cada URL muestra la fecha en que fue agregada

## API REST

### Obtener URLs personalizadas

```bash
curl http://localhost:8082/api/custom-urls
```

Respuesta:
```json
{
  "urls": [
    {
      "url": "https://ejemplo.com/playlist.m3u",
      "name": "Mi lista personal",
      "added_at": "2026-03-15T10:30:00.123456"
    }
  ],
  "count": 1
}
```

### Agregar una URL

```bash
curl -X POST http://localhost:8082/api/custom-urls \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://ejemplo.com/playlist.m3u",
    "name": "Mi lista personal"
  }'
```

Respuesta exitosa:
```json
{
  "message": "URL agregada exitosamente",
  "url": "https://ejemplo.com/playlist.m3u"
}
```

### Eliminar una URL

```bash
curl -X DELETE "http://localhost:8082/api/custom-urls/https%3A%2F%2Fejemplo.com%2Fplaylist.m3u"
```

Respuesta:
```json
{
  "message": "URL eliminada exitosamente"
}
```

## Archivo de Almacenamiento

Las URLs se guardan en `custom_urls.json` en el directorio de la aplicación:

```json
[
  {
    "url": "https://ejemplo.com/playlist1.m3u",
    "name": "Lista 1",
    "added_at": "2026-03-15T10:30:00.123456"
  },
  {
    "url": "https://ejemplo.com/playlist2.m3u",
    "name": "Lista 2",
    "added_at": "2026-03-15T10:35:00.654321"
  }
]
```

## Cómo Funciona

1. **Descarga de múltiples fuentes**: 
   - La aplicación descarga la URL principal (M3U_URL)
   - Luego descarga todas las URLs personalizadas agregadas

2. **Combinación de contenido**:
   - Todos los contenidos se combinan en un solo archivo
   - Se evitan múltiples headers `#EXTM3U`
   - Se mantiene el orden de las listas

3. **Reemplazo de IPs**:
   - Se aplica el reemplazo de IPs al contenido combinado
   - Funciona igual que antes pero con múltiples fuentes

4. **Actualización del caché**:
   - El caché se actualiza automáticamente cada 12 horas (configurable)
   - También se actualiza cuando agregas o eliminas una URL
   - El archivo final se sirve desde `/stream.m3u`

## Ejemplo de Uso Completo

1. Usuario agrega URL: `https://cdn.ejemplo.com/hd-channels.m3u`
2. Usuario agrega URL: `https://otro-servidor.com/lista-deportes.m3u`
3. En la siguiente actualización de caché:
   - Se descarga contenido principal (M3U_URL)
   - Se descarga `hd-channels.m3u`
   - Se descarga `lista-deportes.m3u`
   - Se combinan los 3 contenidos
   - Se aplica reemplazo de IPs
   - Se guarda en caché
   - Se sirve desde `/stream.m3u`

## Validaciones

- Las URLs deben comenzar con `http://` o `https://`
- No se permiten URLs duplicadas
- Se valida que sea una URL válida antes de agregarla
- La aplicación maneja gracefully errores de descarga

## Notas Importantes

⚠️ **Persistencia**: Las URLs se guardan en `custom_urls.json`. Si eliminas este archivo, perderás todas las URLs personalizadas.

⚠️ **Errores de descarga**: Si una URL falla al descargar, se registra el error pero la aplicación sigue funcionando con las otras fuentes.

⚠️ **Tamaño**: El contenido combinado puede crecer significativamente con múltiples fuentes. Ten en cuenta el ancho de banda disponible.

✅ **Recomendación**: Regularmente revisa la sección de logs para asegurar que todas las URLs se descargan correctamente.
