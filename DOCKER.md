# Docker - ACE Content Getter

Guía completa para ejecutar la aplicación en Docker y Docker Compose.

## Requisitos

- Docker 20.10+
- Docker Compose 2.0+ (para docker-compose)
- 256 MB de RAM mínimo

## Inicio Rápido con Docker Compose

### Opción 1: Ejecución simple

```bash
# 1. Clonar/descargar el proyecto
cd ace_content_getter

# 2. Copiar archivo de configuración
cp .env.docker .env

# 3. Editar .env si es necesario
# nano .env  (o usa tu editor favorito)

# 4. Ejecutar
docker-compose up -d

# 5. Verificar que funciona
curl http://localhost:8080/

# 6. Ver logs
docker-compose logs -f ace-content-getter

# 7. Detener
docker-compose down
```

### Opción 2: Ejecución con variables personalizadas

```bash
# Sin archivo .env, desde línea de comandos
docker-compose up -d \
  -e M3U_URL=http://tu-servidor.com/playlist.m3u \
  -e OLD_IP=192.168.1.50 \
  -e NEW_IP=192.168.1.100 \
  -e UPDATE_INTERVAL=6
```

### Opción 3: Usar la imagen pre-construida

Si tienes la imagen publicada en Docker Hub/Registry:

```bash
# Editar docker-compose.yml y descomentar:
# image: tu-usuario/ace-content-getter:latest

# Luego:
docker-compose pull
docker-compose up -d
```

## Compilar imagen personalmente

### Opción 1: Con Docker Compose (recomendado)

```bash
# Compila automáticamente y ejecuta
docker-compose up -d --build

# Solo compilar sin ejecutar
docker-compose build
```

### Opción 2: Con Docker CLI directamente

```bash
# Compilar
docker build -t ace-content-getter:latest .

# Ejecutar con variables de entorno
docker run -d \
  --name ace-getter \
  -p 8080:8080 \
  -e M3U_URL=http://tu-servidor.com/playlist.m3u \
  -e OLD_IP=127.0.0.1 \
  -e NEW_IP=192.168.1.151 \
  -e UPDATE_INTERVAL=12 \
  ace-content-getter:latest

# Ver logs
docker logs -f ace-getter

# Detener
docker stop ace-getter

# Remover
docker rm ace-getter
```

## Estructura del Dockerfile

El Dockerfile utiliza **multi-stage build** para optimizar:

1. **Builder stage**: Instala dependencias Python en un venv
2. **Runtime stage**: Copia solo lo necesario (imagen más pequeña ~150MB)

Beneficios:
- Imagen final pequeña (sin herramientas de desarrollo)
- Rápido de compilar tras cambios en app.py
- Seguro (usuario no-root, sin herramientas innecesarias)

## Variables de entorno en Docker

Todas estas se pueden configurar:

| Variable | Default | Descripción |
|----------|---------|-------------|
| `M3U_URL` | `http://ejemplo.com/playlist.m3u` | URL del m3u |
| `OLD_IP` | `127.0.0.1` | IP a reemplazar |
| `NEW_IP` | `192.168.1.151` | IP nueva |
| `UPDATE_INTERVAL` | `12` | Horas entre actualizaciones |

## Configuración de docker-compose.yml

### Puertos

```yaml
ports:
  - "8080:8080"  # acceso desde puerto 8080 del host
```

Cambiar a otro puerto:
```yaml
ports:
  - "9000:8080"  # acceso desde puerto 9000 del host
```

### Límites de recursos

```yaml
deploy:
  resources:
    limits:
      cpus: '0.5'      # máximo 50% de 1 CPU
      memory: 256M     # máximo 256 MB de RAM
    reservations:
      cpus: '0.25'     # reservar 25% de 1 CPU
      memory: 128M     # reservar 128 MB
```

Ajustar según tu host.

### Política de reinicio

```yaml
restart: unless-stopped
```

Opciones:
- `no`: No reiniciar (default)
- `always`: Siempre reiniciar
- `unless-stopped`: Reiniciar a menos que se haya detenido explícitamente
- `on-failure`: Reiniciar solo si sale con error

### Logs

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"    # Máximo 10MB por archivo de log
    max-file: "3"      # Guardar máximo 3 archivos
```

## Monitoreo

### Ver estado del contenedor

```bash
# Estado actual
docker-compose ps

# Salida:
# NAME                   STATUS             ...
# ace-content-getter     Up 2 minutes (healthy)
```

### Ver logs

```bash
# Últimas 50 líneas
docker-compose logs -n 50 ace-content-getter

# En tiempo real
docker-compose logs -f ace-content-getter

# Solo errores
docker-compose logs ace-content-getter | grep ERROR
```

### Healthcheck

El contenedor tiene un healthcheck integrado que verifica cada 30 segundos:

```bash
# Ver el state del healthcheck
docker-compose ps

# Ver detalles
docker inspect ace-content-getter | jq '.[] | .State.Health'
```

## Casos de uso

### Caso 1: Servidor IPTV en casa

```bash
# Crear .env
cat > .env << EOF
M3U_URL=http://192.168.1.100:8888/playlist.m3u
OLD_IP=127.0.0.1
NEW_IP=192.168.1.10
UPDATE_INTERVAL=24
EOF

# Ejecutar
docker-compose up -d

# Acceder desde cualquier dispositivo en la red:
# http://192.168.1.10:8080/stream.m3u
```

### Caso 2: Producción con logs persistentes

```bash
# Descomentar volumes en docker-compose.yml
# volumes:
#   - ./logs:/app/logs

# Crear carpeta
mkdir -p logs

# Ejecutar
docker-compose up -d

# Ver logs
tail -f logs/*.log
```

### Caso 3: Ejecutar en puerto diferente

```bash
# Editar docker-compose.yml:
ports:
  - "9090:8080"

# O desde CLI:
docker-compose up -d --publish 9090:8080
```

### Caso 4: Actualizar imagen sin perder configuración

```bash
# Compilar nueva imagen
docker-compose build --no-cache

# Recrear contenedor sin que pierda configuración
docker-compose up -d --force-recreate
```

## Problemas comunes

### Error: "Cannot bind to 0.0.0.0:8080"

El puerto 8080 ya está en uso. Soluciones:

**Opción 1**: Cambiar puerto en docker-compose.yml
```yaml
ports:
  - "8081:8080"
```

**Opción 2**: Detener lo que usa el puerto
```bash
# Windows
netstat -ano | findstr :8080
taskkill /PID <PID> /F

# Linux
lsof -i :8080
kill -9 <PID>
```

### Error: "Failed to download m3u"

Probables causas:
- URL inválida: Verifica `M3U_URL` en .env
- Red no disponible: El contenedor no tiene acceso a internet
- Host no disponible: El servicio m3u está caído

Soluciones:
```bash
# Ver logs detallados
docker-compose logs ace-content-getter

# Probar conectividad desde e contenedor
docker-compose exec ace-content-getter curl <tu_url>

# Rebuild y reinicial
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### La imagen es muy grande

Si compilaste sin multi-stage (Dockerfile antiguo):
```bash
# Limpiar imágenes antiguas
docker image prune -a

# Recompilar con Dockerfile nuevo
docker-compose build --no-cache

# Verificar tamaño
docker images ace-content-getter
```

### El contenedor se reinicia constantemente

```bash
# Ver logs del último reinicio
docker-compose logs --tail 100

# Verificar que el puerto está correcto
docker-compose exec ace-content-getter curl localhost:8080/health
```

## Publicar imagen a Docker Hub

```bash
# 1. Crear cuenta en hub.docker.com

# 2. Login
docker login

# 3. Compilar con tag
docker build -t tu-usuario/ace-content-getter:1.0.0 .
docker build -t tu-usuario/ace-content-getter:latest .

# 4. Push
docker push tu-usuario/ace-content-getter:1.0.0
docker push tu-usuario/ace-content-getter:latest

# 5. Otros pueden descargar con:
# docker pull tu-usuario/ace-content-getter:latest
```

## Docker en diferentes sistemas

### Windows

**Con Docker Desktop:**
```bash
docker-compose up -d

# Acceder en navegador
# http://localhost:8080
```

**Con WSL 2:**
```bash
# Abrir terminal WSL
wsl -d Ubuntu-20.04

cd /mnt/c/Users/usuario/ace_content_getter
docker-compose up -d
```

### Mac

```bash
# Instalar Docker Desktop para Mac
# Luego:
docker-compose up -d

# URL: http://localhost:8080
```

### Linux

```bash
# Instalar docker
sudo apt-get install docker.io docker-compose

# Ejecutar (sin sudo si agregaste tu usuario al grupo docker)
docker-compose up -d

# URL: http://localhost:8080
```

## Limpieza

```bash
# Detener contenedor
docker-compose stop

# Detener y remover
docker-compose down

# Remover volúmenes también
docker-compose down -v

# Limpiar imágenes sin usar
docker image prune

# Limpiar TODO (imágenes, contenedores, volúmenes, redes)
docker system prune -a
```

## Ejemplo .env completo

```bash
# .env
M3U_URL=https://ipfs.io/ipns/k2k4r8oqlcjxsritt5mczkcn4mmvcmymbqw7113fz2flkrerfwfps004/data/listas/lista_iptv.m3u
OLD_IP=127.0.0.1
NEW_IP=192.168.1.151
UPDATE_INTERVAL=12
```

## Recursos útiles

- [Documentación Docker](https://docs.docker.com/)
- [Documentación Docker Compose](https://docs.docker.com/compose/)
- [Referencia Dockerfile](https://docs.docker.com/engine/reference/builder/)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)

## Soporte

Si tienes problemas:

1. Revisa los logs: `docker-compose logs ace-content-getter`
2. Verifica la configuración en `.env`
3. Asegúrate de que Docker u Docker Desktop está corriendo
4. Intenta recompilar: `docker-compose build --no-cache`
