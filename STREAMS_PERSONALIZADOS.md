# Streams Personalizados

## Descripción

La aplicación ahora permite a los usuarios agregar **streams individuales** directamente desde la interfaz web. En lugar de descargar múltiples archivos M3U completos, ahora puedes agregar URLs específicas de canales o streams con su información (nombre, logo, grupo).

Los streams se guardan de forma persistente y se incluyen automáticamente en el archivo M3U generado cada vez que se actualiza el caché.

## Características

✨ **Agregar streams individuales**: Interfaz intuitiva para agregar canales específicos
📺 **Información de streams**: Nombre, logo, categoría, y URL del stream
💾 **Persistencia**: Los streams se guardan en `custom_streams.json`
🔄 **Actualización automática**: Los streams se incluyen en cada actualización de caché
🗑️ **Gestión fácil**: Eliminar streams directamente desde el panel
🎨 **Interfaz moderna**: Panel web responsive y visualmente atractivo
📊 **API REST**: Endpoints completos para gestionar streams programáticamente

## Uso

### Interfaz Web

1. Abre la aplicación en tu navegador: `http://localhost:8082`
2. Ve a la sección "Agregar Nuevo Stream"
3. Rellena los campos:
   - **Nombre del Canal** (requerido): Ej. "HBO", "CNN", "Mi Stream Favorito"
   - **URL del Stream** (requerido): Ej. `http://streaming.ejemplo.com/canal.m3u8`
   - **Grupo/Categoría** (opcional): Ej. "Películas", "Deportes", "Noticias"
   - **URL del Logo** (opcional): Ej. `https://ejemplo.com/logos/hbo.png`
4. Haz clic en "Agregar Stream"
5. El caché se actualiza automáticamente
6. En la sección "Streams Personalizados" ve el stream agregado

### Gestión de Streams

- **Ver streams**: En la sección "Streams Personalizados" se muestra la lista completa
- **Eliminar stream**: Haz clic en el botón "🗑️ Eliminar" junto al stream
- **Editar stream**: La edición estará disponible en futuras versiones
- **Información**: Cada stream muestra nombre, categoría y fecha en que fue agregado

## API REST

### Obtener todos los streams

```bash
curl http://localhost:8082/api/streams
```

Respuesta:
```json
{
  "streams": [
    {
      "id": "stream_0_1710522600",
      "name": "HBO",
      "url": "http://streaming.ejemplo.com/hbo.m3u8",
      "logo": "https://ejemplo.com/logos/hbo.png",
      "group": "Películas",
      "added_at": "2026-03-15T10:30:00.123456"
    },
    {
      "id": "stream_1_1710522700",
      "name": "CNN",
      "url": "http://streaming.ejemplo.com/cnn.m3u8",
      "logo": "https://ejemplo.com/logos/cnn.png",
      "group": "Noticias",
      "added_at": "2026-03-15T10:35:00.654321"
    }
  ],
  "count": 2
}
```

### Agregar un nuevo stream

```bash
curl -X POST http://localhost:8082/api/streams \
  -H "Content-Type: application/json" \
  -d '{
    "name": "HBO",
    "url": "http://streaming.ejemplo.com/hbo.m3u8",
    "logo": "https://ejemplo.com/logos/hbo.png",
    "group": "Películas"
  }'
```

Respuesta exitosa:
```json
{
  "message": "Stream agregado exitosamente"
}
```

### Actualizar un stream existente

```bash
curl -X PUT http://localhost:8082/api/streams/stream_0_1710522600 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "HBO Latino",
    "url": "http://streaming.ejemplo.com/hbo-latino.m3u8",
    "logo": "https://ejemplo.com/logos/hbo-latino.png",
    "group": "Películas"
  }'
```

Respuesta:
```json
{
  "message": "Stream actualizado exitosamente"
}
```

### Eliminar un stream

```bash
curl -X DELETE "http://localhost:8082/api/streams/stream_0_1710522600"
```

Respuesta:
```json
{
  "message": "Stream eliminado exitosamente"
}
```

## Archivo de Almacenamiento

Los streams se guardan en `custom_streams.json` en el directorio `/app/data`:

```json
[
  {
    "id": "stream_0_1710522600",
    "name": "HBO",
    "url": "http://streaming.ejemplo.com/hbo.m3u8",
    "logo": "https://ejemplo.com/logos/hbo.png",
    "group": "Películas",
    "added_at": "2026-03-15T10:30:00.123456"
  },
  {
    "id": "stream_1_1710522700",
    "name": "CNN",
    "url": "http://streaming.ejemplo.com/cnn.m3u8",
    "logo": "https://ejemplo.com/logos/cnn.png",
    "group": "Noticias",
    "added_at": "2026-03-15T10:35:00.654321"
  }
]
```

## Cómo Funciona

1. **Descarga de la fuente principal**: 
   - Se descarga el archivo M3U configurado en `M3U_URL`

2. **Generación dinámica del M3U**:
   - Se parte de la fuente principal
   - Se agregan todos los streams personalizados
   - Cada stream incluye su información (nombre, logo, grupo)

3. **Formato de los streams**:
   - Se usa el formato estándar M3U con extensiones EXTINF
   - Incluye atributos `tvg-id`, `tvg-name`, `tvg-logo`, `group-title`
   - Compatible con todos los reproductores modernos

4. **Reemplazo de IPs**:
   - Se aplica el reemplazo de IPs al contenido final
   - Funciona igual que antes pero con múltiples fuentes

5. **Actualización del caché**:
   - El caché se actualiza automáticamente cada 12 horas
   - También se actualiza cuando agregas o eliminas un stream
   - El archivo final se sirve desde `/stream.m3u`

## Validaciones

- El **nombre** del stream es requerido
- La **URL** es requerida y debe comenzar con `http://`, `https://`, `rtmp://` o `rtmps://`
- No se permiten URLs duplicadas
- El **grupo** se establece como "Sin categoría" si no se proporciona
- La aplicación valida que la URL sea válida antes de agregarla

## Ejemplo de Uso Completo

1. Accedes a `http://localhost:8082`
2. Agregas varios streams:
   - HBO (http://streaming.ejemplo.com/hbo.m3u8, Películas)
   - CNN (http://streaming.ejemplo.com/cnn.m3u8, Noticias)
   - ESPN (http://streaming.ejemplo.com/espn.m3u8, Deportes)
3. En la siguiente actualización de caché:
   - Se descarga la URL principal (M3U_URL)
   - Se generan entradas para los 3 streams
   - Se aplica reemplazo de IPs
   - Se guarda en caché
4. Cargas `http://IP_SERVIDOR:8082/stream.m3u` en tu reproductor
5. Tienes todos los canales disponibles

## Notas Importantes

⚠️ **Persistencia**: Los streams se guardan en `/app/data/custom_streams.json`. Si eliminas este archivo, perderás todos los streams personalizados.

⚠️ **Errores de descarga**: Si la URL principal falla, la aplicación comienza con un M3U vacío pero incluye los streams personalizados.

✅ **Formato M3U**: Todos los streams se generan con formato M3U válido compatible con VLC, Kodi, Plex, etc.

✅ **Logos**: Si proporcionas URLs de logos, se incluyen automáticamente en el archivo M3U para que los reproductores las muestren.

✅ **Categorías**: Los grupos ayudan a organizar los canales en reproductores que lo soportan.

## Diferencias con la versión anterior

| Anterior | Nueva versión |
|----------|--------------|
| Agregar URLs de M3U completos | Agregar streams individuales |
| Un campo: URL | Múltiples campos: nombre, URL, logo, grupo |
| Descargar múltiples M3U | Generar M3U dinámicamente |
| Combinación simple | Formato M3U completo con metadatos |
| Sin información de canales | Información completa por canal |

