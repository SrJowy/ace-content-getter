# Etapa 1: Builder - Instalar dependencias
FROM python:3.11-slim as builder

WORKDIR /app

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias en una carpeta venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# Etapa 2: Runtime - Imagen final más pequeña
FROM python:3.11-slim

WORKDIR /app

# Crear usuario no-root para seguridad
RUN useradd -m -u 1000 appuser

# Copiar venv de la etapa builder
COPY --from=builder /opt/venv /opt/venv

# Copiar código de la aplicación
COPY app.py .

# Configurar variables de entorno
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    M3U_URL=http://ejemplo.com/playlist.m3u \
    SERVER_PORT=8080 \
    OLD_IP=127.0.0.1 \
    NEW_IP=192.168.1.151 \
    UPDATE_INTERVAL=12

# Cambiar al usuario no-root
USER appuser

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${SERVER_PORT}/health')" || exit 1

# Exponer puerto
EXPOSE 8080

# Comando de inicio
CMD ["python", "app.py"]
