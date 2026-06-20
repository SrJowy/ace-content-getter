"""
Parser para extraer y procesar archivos M3U
"""

import re


class M3UParser:
    """Parser para extraer streams de un archivo M3U"""
    
    @staticmethod
    def parse_m3u(content):
        """Parsea contenido M3U y retorna lista de streams"""
        streams = []
        lines = content.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('#EXTINF:'):
                # Parsear la línea EXTINF
                extinf_data = M3UParser._parse_extinf(line)
                
                # La siguiente línea (no vacía) debe ser la URL
                i += 1
                while i < len(lines) and not lines[i].strip():
                    i += 1
                
                if i < len(lines):
                    url = lines[i].strip()
                    if url and not url.startswith('#'):
                        extinf_data['url'] = url
                        streams.append(extinf_data)
            
            i += 1
        
        return streams
    
    @staticmethod
    def _parse_extinf(extinf_line):
        """Parsea una línea EXTINF y extrae los atributos"""
        data = {
            'id': None,
            'name': '',
            'logo': '',
            'group': 'Sin categoría',
            'url': ''
        }
        
        # Extraer tvg-id
        tvg_id_match = M3UParser._extract_attribute(extinf_line, 'tvg-id')
        if tvg_id_match:
            data['id'] = tvg_id_match
        
        # Extraer tvg-name
        tvg_name_match = M3UParser._extract_attribute(extinf_line, 'tvg-name')
        if tvg_name_match:
            data['name'] = tvg_name_match
        
        # Extraer tvg-logo
        tvg_logo_match = M3UParser._extract_attribute(extinf_line, 'tvg-logo')
        if tvg_logo_match:
            data['logo'] = tvg_logo_match
        
        # Extraer group-title
        group_match = M3UParser._extract_attribute(extinf_line, 'group-title')
        if group_match:
            data['group'] = group_match
        
        # Extraer nombre del canal (lo que viene después de la última coma)
        comma_pos = extinf_line.rfind(',')
        if comma_pos != -1:
            name_part = extinf_line[comma_pos + 1:].strip()
            if name_part:
                data['name'] = name_part
        
        # Generar ID si no existe
        if not data['id']:
            data['id'] = f"m3u_stream_{abs(hash(data['name'] + data['url'])) % 10000000}"
        
        return data
    
    @staticmethod
    def _extract_attribute(extinf_line, attr_name):
        """Extrae un atributo de la línea EXTINF"""
        pattern = f'{attr_name}="([^"]*)"'
        match = re.search(pattern, extinf_line)
        if match:
            return match.group(1)
        return None


__all__ = ['M3UParser']
