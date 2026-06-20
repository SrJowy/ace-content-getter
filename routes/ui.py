"""
UI routes - User interface and file serving endpoints
"""

from io import BytesIO
from flask import Blueprint, send_file, jsonify, render_template_string

from config import M3U_URL, OLD_IP, NEW_IP, UPDATE_INTERVAL
from core import M3UParser
from utils.logger import setup_logger

logger = setup_logger(__name__)

ui_bp = Blueprint('ui', __name__)

# Estas variables se inyectarán desde app.py
cache = None
stream_manager = None
m3u_modification_manager = None


def init_ui(c, sm, m3um):
    """Inicializa las dependencias del módulo UI"""
    global cache, stream_manager, m3u_modification_manager
    cache = c
    stream_manager = sm
    m3u_modification_manager = m3um


@ui_bp.route('/stream.m3u')
def serve_m3u():
    """Sirve el archivo m3u modificado desde caché"""
    try:
        # Si el caché no está disponible, retornar error
        if not cache.is_valid():
            return {'error': 'No se pudo obtener el archivo m3u'}, 503
        
        modified_content = cache.get()
        
        if modified_content is None:
            return {'error': 'No se pudo obtener el archivo m3u'}, 503
        
        # Crear un archivo en memoria
        file_stream = BytesIO(modified_content.encode('utf-8'))
        
        return send_file(
            file_stream,
            mimetype='application/vnd.apple.mpegurl',
            as_attachment=True,
            download_name='stream.m3u'
        )
    except Exception as e:
        logger.error(f"Error al servir el archivo: {e}")
        return {'error': str(e)}, 500


@ui_bp.route('/health')
def health():
    """Endpoint para verificar que el servidor está activo"""
    if cache.is_valid():
        return {'status': 'ok', 'cache': 'ready'}, 200
    else:
        return {'status': 'ok', 'cache': 'not-ready'}, 200


@ui_bp.route('/status')
def status():
    """Endpoint para obtener el estado de la aplicación"""
    status_info = {
        'server': 'running',
        'cache': {
            'available': cache.is_valid(),
            'last_update': cache.last_update.isoformat() if cache.last_update else None,
            'update_in_progress': cache.update_in_progress,
            'last_error': cache.last_error
        },
        'configuration': {
            'update_interval_hours': UPDATE_INTERVAL,
            'm3u_url': M3U_URL,
            'old_ip': OLD_IP,
            'new_ip': NEW_IP
        }
    }
    return jsonify(status_info), 200


@ui_bp.route('/')
def index():
    """Página de inicio"""
    cache_status = "✓ Disponible" if cache.is_valid() else "✗ No disponible"
    last_update = cache.last_update.strftime('%Y-%m-%d %H:%M:%S') if cache.last_update else "Nunca"
    
    # Obtener streams personalizados
    custom_streams = stream_manager.get_streams()
    
    # Obtener streams del M3U
    m3u_streams = []
    if cache.is_valid():
        m3u_content = cache.get()
        if m3u_content:
            m3u_streams = M3UParser.parse_m3u(m3u_content)
            # Filtrar streams eliminados
            deleted_ids = m3u_modification_manager.get_all_deleted_ids()
            m3u_streams = [s for s in m3u_streams if s['id'] not in deleted_ids]
            # Aplicar modificaciones
            for stream in m3u_streams:
                mod = m3u_modification_manager.get_modification(stream['id'])
                if mod:
                    stream['name'] = mod['name'] or stream['name']
                    stream['logo'] = mod['logo'] or stream['logo']
                    stream['group'] = mod['group'] or stream['group']
    
    # Generar HTML para streams del M3U
    m3u_streams_html = ""
    if m3u_streams:
        m3u_streams_html = "<div id='m3u_streams_list'>"
        for stream in m3u_streams:
            logo_html = f"<img src='{stream['logo']}' alt='logo' style='width: 50px; height: auto;'>" if stream.get('logo') else "<div style='width: 50px; text-align: center;'>📺</div>"
            
            m3u_streams_html += f"""
            <div class="stream-item" data-stream-id="{stream['id']}" data-stream-type="m3u">
                <div class="stream-logo">
                    {logo_html}
                </div>
                <div class="stream-info">
                    <strong><span data-field="name">{stream['name']}</span></strong>
                    <br><small>Grupo: <span data-field="group">{stream['group']}</span></small>
                    <br><small style='color: #666;'>{stream['url']}</small>
                    <small style='display: none;' data-field="logo">{stream.get('logo', '')}</small>
                </div>
                <div class="stream-actions">
                    <button onclick="openEditModalM3U('{stream['id']}')">✏️ Editar</button>
                    <button onclick="deleteM3UStream('{stream['id']}')">🗑️ Eliminar</button>
                </div>
            </div>
            """
        m3u_streams_html += "</div>"
    else:
        m3u_streams_html = "<p style='color: #999;'>No hay streams en el M3U o no se ha descargado aún.</p>"
    
    # Generar HTML para streams personalizados
    custom_streams_html = ""
    if custom_streams:
        custom_streams_html = "<div id='custom_streams_list'>"
        for stream in custom_streams:
            logo_html = f"<img src='{stream['logo']}' alt='logo' style='width: 50px; height: auto;'>" if stream.get('logo') else "<div style='width: 50px; text-align: center;'>📺</div>"
            
            custom_streams_html += f"""
            <div class="stream-item" data-stream-id="{stream['id']}" data-stream-type="custom">
                <div class="stream-logo">
                    {logo_html}
                </div>
                <div class="stream-info">
                    <strong><span data-field="name">{stream['name']}</span></strong>
                    <br><small>Grupo: <span data-field="group">{stream['group']}</span></small>
                    <br><small style='color: #666; display: none;' data-field="url">{stream['url']}</small>
                    <small style='color: #666; display: none;' data-field="logo">{stream.get('logo', '')}</small>
                </div>
                <div class="stream-actions">
                    <button onclick="openEditModal('{stream['id']}')">✏️ Editar</button>
                    <button onclick="deleteStream('{stream['id']}')">🗑️ Eliminar</button>
                </div>
            </div>
            """
        custom_streams_html += "</div>"
    else:
        custom_streams_html = "<p style='color: #999;'>No hay streams personalizados agregados. ¡Agrega uno para comenzar!</p>"
    
    return render_template_string(get_html_template(), 
        cache_status=cache_status,
        last_update=last_update,
        update_interval=UPDATE_INTERVAL,
        m3u_url=M3U_URL,
        old_ip=OLD_IP,
        new_ip=NEW_IP,
        m3u_streams_count=len(m3u_streams),
        m3u_streams_html=m3u_streams_html,
        custom_streams_count=len(custom_streams),
        custom_streams_html=custom_streams_html
    )


def get_html_template():
    """Retorna el template HTML para la página de inicio"""
    return """
    <html>
    <head>
        <title>M3U Content Getter - Gestor de Streams</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 1100px;
                margin: 0 auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }}
            h1 {{
                color: white;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
                margin-bottom: 5px;
            }}
            .header {{
                background: rgba(0,0,0,0.1);
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 20px;
                color: white;
            }}
            .header p {{
                opacity: 0.9;
                margin-top: 10px;
            }}
            h2 {{
                color: #333;
                margin-top: 25px;
                font-size: 1.3em;
                border-left: 4px solid #667eea;
                padding-left: 12px;
            }}
            .section {{
                background: white;
                padding: 25px;
                margin: 15px 0;
                border-radius: 8px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            }}
            .status-ok {{
                color: #28a745;
                font-weight: bold;
            }}
            .status-error {{
                color: #dc3545;
                font-weight: bold;
            }}
            ul {{
                list-style: none;
                padding: 0;
            }}
            li {{
                padding: 10px 0;
                border-bottom: 1px solid #eee;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            li:last-child {{
                border-bottom: none;
            }}
            code {{
                background: #f0f0f0;
                padding: 4px 8px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
                font-size: 0.9em;
            }}
            a {{
                color: #667eea;
                text-decoration: none;
                font-weight: bold;
            }}
            a:hover {{
                text-decoration: underline;
            }}
            .form-group {{
                margin-bottom: 15px;
            }}
            label {{
                display: block;
                margin-bottom: 8px;
                font-weight: 600;
                color: #333;
            }}
            input[type="text"],
            input[type="url"],
            select {{
                width: 100%;
                padding: 12px;
                border: 2px solid #ddd;
                border-radius: 6px;
                font-size: 14px;
                transition: border-color 0.3s;
            }}
            input[type="text"]:focus,
            input[type="url"]:focus,
            select:focus {{
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }}
            .form-row {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 15px;
            }}
            button {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 600;
                transition: transform 0.2s, box-shadow 0.2s;
            }}
            button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
            }}
            button:active {{
                transform: translateY(0);
            }}
            .btn-secondary {{
                background: #6c757d;
            }}
            .btn-secondary:hover {{
                background: #5a6268;
            }}
            .btn-delete {{
                background: #dc3545;
                padding: 6px 12px;
                font-size: 12px;
            }}
            .btn-delete:hover {{
                background: #c82333;
            }}
            .btn-edit {{
                background: #007bff;
                padding: 6px 12px;
                font-size: 12px;
            }}
            .btn-edit:hover {{
                background: #0056b3;
            }}
            .stream-item {{
                display: grid;
                grid-template-columns: 60px 1fr 200px;
                gap: 15px;
                align-items: center;
                padding: 15px;
                background: #f9f9f9;
                border-radius: 6px;
                margin-bottom: 12px;
                border: 1px solid #e9ecef;
                transition: all 0.3s;
            }}
            .stream-item:hover {{
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                background: #ffffff;
            }}
            .stream-logo {{
                display: flex;
                align-items: center;
                justify-content: center;
                height: 60px;
            }}
            .stream-logo img {{
                max-width: 100%;
                max-height: 100%;
                border-radius: 4px;
            }}
            .stream-info {{
                line-height: 1.6;
            }}
            .stream-info strong {{
                color: #333;
                display: block;
                margin-bottom: 4px;
            }}
            .stream-info small {{
                color: #666;
            }}
            .stream-actions {{
                display: flex;
                gap: 8px;
            }}
            .stream-actions button {{
                padding: 8px 12px;
                font-size: 12px;
                width: 100%;
            }}
            .loading {{
                display: none;
                color: #667eea;
                font-weight: bold;
                margin-top: 10px;
            }}
            .message {{
                padding: 12px 16px;
                margin: 10px 0;
                border-radius: 6px;
                display: none;
                border-left: 4px solid;
                animation: slideIn 0.3s ease;
            }}
            @keyframes slideIn {{
                from {{
                    opacity: 0;
                    transform: translateY(-10px);
                }}
                to {{
                    opacity: 1;
                    transform: translateY(0);
                }}
            }}
            .message.success {{
                background-color: #d4edda;
                color: #155724;
                border-color: #28a745;
            }}
            .message.error {{
                background-color: #f8d7da;
                color: #721c24;
                border-color: #dc3545;
            }}
            .required {{
                color: #dc3545;
            }}
            @media (max-width: 768px) {{
                .form-row {{
                    grid-template-columns: 1fr;
                }}
                .stream-item {{
                    grid-template-columns: 50px 1fr;
                }}
                .stream-actions {{
                    grid-column: 1 / -1;
                }}
                .stream-actions button {{
                    flex: 1;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📺 M3U Content Getter</h1>
            <p>Aplicación que descarga y modifica archivos m3u con actualización automática cada {{ update_interval }} horas</p>
        </div>
        
        <div class="section">
            <h2>📊 Estado del Sistema</h2>
            <ul>
                <li>
                    <span><strong>Caché:</strong></span>
                    <span class="status-ok">{{ cache_status }}</span>
                </li>
                <li>
                    <span><strong>Última actualización:</strong></span>
                    <span>{{ last_update }}</span>
                </li>
                <li>
                    <span><strong>Intervalo de actualización:</strong></span>
                    <span>{{ update_interval }} horas</span>
                </li>
            </ul>
        </div>
        
        <div class="section">
            <h2>⚙️ Configuración Principal</h2>
            <ul>
                <li>
                    <span><strong>URL de origen M3U:</strong></span>
                    <code>{{ m3u_url }}</code>
                </li>
                <li>
                    <span><strong>IP a reemplazar:</strong></span>
                    <code>{{ old_ip }}</code> → <code>{{ new_ip }}</code>
                </li>
            </ul>
        </div>
        
        <div class="section">
            <h2>➕ Agregar Nuevo Stream</h2>
            <div id="message" class="message"></div>
            
            <div class="form-row">
                <div class="form-group">
                    <label for="nameInput">Nombre del Canal <span class="required">*</span></label>
                    <input type="text" id="nameInput" placeholder="ej: HBO, CNN, TN, etc" />
                </div>
                <div class="form-group">
                    <label for="groupInput">Grupo/Categoría</label>
                    <input type="text" id="groupInput" placeholder="ej: Películas, Deportes, Noticias" />
                </div>
            </div>
            
            <div class="form-group">
                <label for="urlInput">URL del Stream <span class="required">*</span></label>
                <input type="url" id="urlInput" placeholder="ej: http://streaming.ejemplo.com/canal.m3u8" />
            </div>
            
            <div class="form-group">
                <label for="logoInput">URL del Logo (opcional)</label>
                <input type="url" id="logoInput" placeholder="ej: https://ejemplo.com/logo.png" />
            </div>
            
            <button onclick="addStream()">Agregar Stream</button>
            <span id="loading" class="loading">Agregando stream y actualizando caché...</span>
        </div>
        
        <!-- Modal de Edición -->
        <div id="editModal" style="display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5);">
            <div style="background-color: white; margin: auto; padding: 0; border-radius: 8px; width: 90%; max-width: 500px; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); box-shadow: 0 4px 20px rgba(0,0,0,0.3);">
                <div style="padding: 20px; border-bottom: 1px solid #ddd; display: flex; justify-content: space-between; align-items: center;">
                    <h2 style="margin: 0; font-size: 1.3em; color: #333;">✏️ Editar Stream</h2>
                    <button onclick="closeEditModal()" style="background: none; border: none; font-size: 24px; cursor: pointer; color: #666;">✕</button>
                </div>
                <div style="padding: 20px;">
                    <div id="editMessage" class="message" style="margin-bottom: 20px;"></div>
                    
                    <div class="form-row">
                        <div class="form-group">
                            <label for="editNameInput">Nombre del Canal <span class="required">*</span></label>
                            <input type="text" id="editNameInput" placeholder="ej: HBO, CNN, TN, etc" />
                        </div>
                        <div class="form-group">
                            <label for="editGroupInput">Grupo/Categoría</label>
                            <input type="text" id="editGroupInput" placeholder="ej: Películas, Deportes, Noticias" />
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label for="editUrlInput">URL del Stream <span class="required">*</span></label>
                        <input type="url" id="editUrlInput" placeholder="ej: http://streaming.ejemplo.com/canal.m3u8" />
                    </div>
                    
                    <div class="form-group">
                        <label for="editLogoInput">URL del Logo (opcional)</label>
                        <input type="url" id="editLogoInput" placeholder="ej: https://ejemplo.com/logo.png" />
                    </div>
                </div>
                <div style="padding: 20px; border-top: 1px solid #ddd; display: flex; gap: 10px; justify-content: flex-end;">
                    <button onclick="closeEditModal()" class="btn-secondary">Cancelar</button>
                    <button onclick="saveStream()">Guardar Cambios</button>
                </div>
            </div>
        </div>
        
        <!-- Modal de Edición para M3U -->
        <div id="editModalM3U" style="display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5);">
            <div style="background-color: white; margin: auto; padding: 0; border-radius: 8px; width: 90%; max-width: 500px; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); box-shadow: 0 4px 20px rgba(0,0,0,0.3);">
                <div style="padding: 20px; border-bottom: 1px solid #ddd; display: flex; justify-content: space-between; align-items: center;">
                    <h2 style="margin: 0; font-size: 1.3em; color: #333;">✏️ Editar Stream del M3U</h2>
                    <button onclick="closeEditModalM3U()" style="background: none; border: none; font-size: 24px; cursor: pointer; color: #666;">✕</button>
                </div>
                <div style="padding: 20px;">
                    <div id="editMessageM3U" class="message" style="margin-bottom: 20px;"></div>
                    
                    <div class="form-row">
                        <div class="form-group">
                            <label for="editM3UNameInput">Nombre del Canal <span class="required">*</span></label>
                            <input type="text" id="editM3UNameInput" placeholder="ej: HBO, CNN, TN, etc" />
                        </div>
                        <div class="form-group">
                            <label for="editM3UGroupInput">Grupo/Categoría</label>
                            <input type="text" id="editM3UGroupInput" placeholder="ej: Películas, Deportes, Noticias" />
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label for="editM3ULogoInput">URL del Logo (opcional)</label>
                        <input type="url" id="editM3ULogoInput" placeholder="ej: https://ejemplo.com/logo.png" />
                    </div>
                </div>
                <div style="padding: 20px; border-top: 1px solid #ddd; display: flex; gap: 10px; justify-content: flex-end;">
                    <button onclick="closeEditModalM3U()" class="btn-secondary">Cancelar</button>
                    <button onclick="saveM3UStream()">Guardar Cambios</button>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>🔄 Streams del M3U ({{ m3u_streams_count }})</h2>
            {{ m3u_streams_html|safe }}
        </div>
        
        <div class="section">
            <h2>📋 Streams Personalizados ({{ custom_streams_count }})</h2>
            {{ custom_streams_html|safe }}
        </div>
        
        <div class="section">
            <h2>🔗 Endpoints Disponibles</h2>
            <ul>
                <li>
                    <span><a href="/stream.m3u">/stream.m3u</a></span>
                    <span>Descargar el archivo M3U modificado</span>
                </li>
                <li>
                    <span><a href="/status">/status</a></span>
                    <span>JSON con estado detallado</span>
                </li>
                <li>
                    <span><a href="/health">/health</a></span>
                    <span>Verificar disponibilidad</span>
                </li>
                <li>
                    <span><code>/api/streams</code></span>
                    <span>API para gestionar streams (GET/POST/PUT/DELETE)</span>
                </li>
            </ul>
        </div>
        
        <div class="section">
            <h2>💡 Cómo Usar</h2>
            <p><strong>En VLC, Kodi, Plex u otros reproductores:</strong></p>
            <code style="display: block; margin-top: 10px;">http://IP_DEL_SERVIDOR:8082/stream.m3u</code>
            <p style="margin-top: 15px;"><strong>Agregando Streams:</strong></p>
            <ol style="margin-left: 20px; margin-top: 10px;">
                <li>Ingresa el nombre del canal o stream</li>
                <li>Pega la URL del archivo M3U o stream directo</li>
                <li>Opcionalmente agrega logo y categoría</li>
                <li>¡El caché se actualiza automáticamente!</li>
            </ol>
        </div>
        
        <script>
            let currentEditStreamId = null;
            let currentEditM3UStreamId = null;
            
            async function addStream() {{
                const name = document.getElementById('nameInput').value.trim();
                const url = document.getElementById('urlInput').value.trim();
                const logo = document.getElementById('logoInput').value.trim();
                const group = document.getElementById('groupInput').value.trim();
                const messageDiv = document.getElementById('message');
                const loading = document.getElementById('loading');
                
                messageDiv.style.display = 'none';
                messageDiv.className = 'message';
                
                if (!name) {{
                    messageDiv.textContent = '❌ Por favor ingresa un nombre para el stream';
                    messageDiv.classList.add('error');
                    messageDiv.style.display = 'block';
                    return;
                }}
                
                if (!url) {{
                    messageDiv.textContent = '❌ Por favor ingresa una URL';
                    messageDiv.classList.add('error');
                    messageDiv.style.display = 'block';
                    return;
                }}
                
                loading.style.display = 'inline';
                
                try {{
                    const response = await fetch('/api/streams', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                        }},
                        body: JSON.stringify({{name, url, logo, group}})
                    }});
                    
                    const data = await response.json();
                    
                    if (response.ok) {{
                        messageDiv.textContent = '✅ Stream agregado exitosamente. Actualizando caché...';
                        messageDiv.classList.add('success');
                        messageDiv.style.display = 'block';
                        document.getElementById('nameInput').value = '';
                        document.getElementById('urlInput').value = '';
                        document.getElementById('logoInput').value = '';
                        document.getElementById('groupInput').value = '';
                        setTimeout(() => location.reload(), 1500);
                    }} else {{
                        messageDiv.textContent = '❌ Error: ' + data.error;
                        messageDiv.classList.add('error');
                        messageDiv.style.display = 'block';
                    }}
                }} catch (error) {{
                    messageDiv.textContent = '❌ Error de red: ' + error.message;
                    messageDiv.classList.add('error');
                    messageDiv.style.display = 'block';
                }} finally {{
                    loading.style.display = 'none';
                }}
            }}
            
            async function deleteStream(streamId) {{
                if (!confirm('¿Seguro que deseas eliminar este stream personalizado?')) {{
                    return;
                }}
                
                try {{
                    const response = await fetch('/api/streams/' + streamId, {{
                        method: 'DELETE'
                    }});
                    
                    if (response.ok) {{
                        alert('✅ Stream eliminado. Actualizando página...');
                        location.reload();
                    }} else {{
                        const data = await response.json();
                        alert('❌ Error: ' + data.error);
                    }}
                }} catch (error) {{
                    alert('❌ Error de red: ' + error.message);
                }}
            }}
            
            async function deleteM3UStream(streamId) {{
                if (!confirm('¿Seguro que deseas eliminar este stream del M3U?')) {{
                    return;
                }}
                
                try {{
                    const response = await fetch('/api/m3u-streams/' + streamId, {{
                        method: 'DELETE'
                    }});
                    
                    if (response.ok) {{
                        alert('✅ Stream eliminado. Actualizando página...');
                        location.reload();
                    }} else {{
                        const data = await response.json();
                        alert('❌ Error: ' + data.error);
                    }}
                }} catch (error) {{
                    alert('❌ Error de red: ' + error.message);
                }}
            }}
            
            function openEditModal(streamId) {{
                const streamItem = document.querySelector(`[data-stream-id="${{streamId}}"][data-stream-type="custom"]`);
                if (!streamItem) return;
                
                currentEditStreamId = streamId;
                
                const name = streamItem.querySelector('[data-field="name"]').textContent;
                const url = streamItem.querySelector('[data-field="url"]').textContent;
                const logo = streamItem.querySelector('[data-field="logo"]').textContent;
                const group = streamItem.querySelector('[data-field="group"]').textContent;
                
                document.getElementById('editNameInput').value = name;
                document.getElementById('editUrlInput').value = url;
                document.getElementById('editLogoInput').value = logo;
                document.getElementById('editGroupInput').value = group;
                
                document.getElementById('editMessage').style.display = 'none';
                document.getElementById('editMessage').className = 'message';
                
                document.getElementById('editModal').style.display = 'block';
            }}
            
            function openEditModalM3U(streamId) {{
                const streamItem = document.querySelector(`[data-stream-id="${{streamId}}"][data-stream-type="m3u"]`);
                if (!streamItem) return;
                
                currentEditM3UStreamId = streamId;
                
                const name = streamItem.querySelector('[data-field="name"]').textContent;
                const logo = streamItem.querySelector('[data-field="logo"]').textContent;
                const group = streamItem.querySelector('[data-field="group"]').textContent;
                
                document.getElementById('editM3UNameInput').value = name;
                document.getElementById('editM3ULogoInput').value = logo;
                document.getElementById('editM3UGroupInput').value = group;
                
                document.getElementById('editMessageM3U').style.display = 'none';
                document.getElementById('editMessageM3U').className = 'message';
                
                document.getElementById('editModalM3U').style.display = 'block';
            }}
            
            function closeEditModal() {{
                document.getElementById('editModal').style.display = 'none';
                currentEditStreamId = null;
            }}
            
            function closeEditModalM3U() {{
                document.getElementById('editModalM3U').style.display = 'none';
                currentEditM3UStreamId = null;
            }}
            
            async function saveStream() {{
                if (!currentEditStreamId) return;
                
                const name = document.getElementById('editNameInput').value.trim();
                const url = document.getElementById('editUrlInput').value.trim();
                const logo = document.getElementById('editLogoInput').value.trim();
                const group = document.getElementById('editGroupInput').value.trim();
                const messageDiv = document.getElementById('editMessage');
                
                messageDiv.style.display = 'none';
                messageDiv.className = 'message';
                
                if (!name) {{
                    messageDiv.textContent = '❌ Por favor ingresa un nombre para el stream';
                    messageDiv.classList.add('error');
                    messageDiv.style.display = 'block';
                    return;
                }}
                
                if (!url) {{
                    messageDiv.textContent = '❌ Por favor ingresa una URL';
                    messageDiv.classList.add('error');
                    messageDiv.style.display = 'block';
                    return;
                }}
                
                try {{
                    const response = await fetch('/api/streams/' + currentEditStreamId, {{
                        method: 'PUT',
                        headers: {{
                            'Content-Type': 'application/json',
                        }},
                        body: JSON.stringify({{name, url, logo, group}})
                    }});
                    
                    const data = await response.json();
                    
                    if (response.ok) {{
                        messageDiv.textContent = '✅ Stream actualizado exitosamente. Actualizando página...';
                        messageDiv.classList.add('success');
                        messageDiv.style.display = 'block';
                        setTimeout(() => {{
                            location.reload();
                        }}, 1500);
                    }} else {{
                        messageDiv.textContent = '❌ Error: ' + data.error;
                        messageDiv.classList.add('error');
                        messageDiv.style.display = 'block';
                    }}
                }} catch (error) {{
                    messageDiv.textContent = '❌ Error de red: ' + error.message;
                    messageDiv.classList.add('error');
                    messageDiv.style.display = 'block';
                }}
            }}
            
            async function saveM3UStream() {{
                if (!currentEditM3UStreamId) return;
                
                const name = document.getElementById('editM3UNameInput').value.trim();
                const logo = document.getElementById('editM3ULogoInput').value.trim();
                const group = document.getElementById('editM3UGroupInput').value.trim();
                const messageDiv = document.getElementById('editMessageM3U');
                
                messageDiv.style.display = 'none';
                messageDiv.className = 'message';
                
                if (!name) {{
                    messageDiv.textContent = '❌ Por favor ingresa un nombre para el stream';
                    messageDiv.classList.add('error');
                    messageDiv.style.display = 'block';
                    return;
                }}
                
                try {{
                    const response = await fetch('/api/m3u-streams/' + currentEditM3UStreamId, {{
                        method: 'PUT',
                        headers: {{
                            'Content-Type': 'application/json',
                        }},
                        body: JSON.stringify({{name, logo, group}})
                    }});
                    
                    const data = await response.json();
                    
                    if (response.ok) {{
                        messageDiv.textContent = '✅ Stream actualizado exitosamente. Actualizando página...';
                        messageDiv.classList.add('success');
                        messageDiv.style.display = 'block';
                        setTimeout(() => {{
                            location.reload();
                        }}, 1500);
                    }} else {{
                        messageDiv.textContent = '❌ Error: ' + data.error;
                        messageDiv.classList.add('error');
                        messageDiv.style.display = 'block';
                    }}
                }} catch (error) {{
                    messageDiv.textContent = '❌ Error de red: ' + error.message;
                    messageDiv.classList.add('error');
                    messageDiv.style.display = 'block';
                }}
            }}
            
            // Cerrar modal al hacer clic fuera
            window.onclick = function(event) {{
                const modalCustom = document.getElementById('editModal');
                const modalM3U = document.getElementById('editModalM3U');
                if (event.target == modalCustom) {{
                    modalCustom.style.display = 'none';
                }}
                if (event.target == modalM3U) {{
                    modalM3U.style.display = 'none';
                }}
            }}
            
            // Auto-submit al presionar Enter
            ['nameInput', 'urlInput', 'logoInput', 'groupInput'].forEach(id => {{
                const el = document.getElementById(id);
                if (el) el.addEventListener('keypress', function(e) {{
                    if (e.key === 'Enter') addStream();
                }});
            }});
            
            // Auto-submit al presionar Enter en el modal de edición
            ['editNameInput', 'editUrlInput', 'editLogoInput', 'editGroupInput'].forEach(id => {{
                const element = document.getElementById(id);
                if (element) {{
                    element.addEventListener('keypress', function(e) {{
                        if (e.key === 'Enter') saveStream();
                    }});
                }}
            }});
            
            // Auto-submit al presionar Enter en el modal de edición M3U
            ['editM3UNameInput', 'editM3UGroupInput', 'editM3ULogoInput'].forEach(id => {{
                const element = document.getElementById(id);
                if (element) {{
                    element.addEventListener('keypress', function(e) {{
                        if (e.key === 'Enter') saveM3UStream();
                    }});
                }}
            }});
        </script>
    </body>
    </html>
    """


__all__ = ['ui_bp', 'init_ui']
