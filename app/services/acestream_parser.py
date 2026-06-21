"""
Parser de Acestream
Extrae, limpia y categoriza streams de acestream desde una URL
"""

import re
from typing import List, Dict
import requests
from bs4 import BeautifulSoup
from app.utils.logger import get_logger
from app.utils.constants import USER_AGENT, DEFAULT_TIMEOUT, CHANNEL_CATEGORIES, DEFAULT_CATEGORY

logger = get_logger(__name__)


class AcestreamParser:
    """Clase para parsear y procesar streams de Acestream"""
    
    def __init__(self, scrape_url: str = 'https://ciriaco.netlify.app/'):
        """
        Inicializa el parser
        
        Args:
            scrape_url: URL a scrapear para obtener streams de acestream
        """
        self.scrape_url = scrape_url
    
    def scrape(self, url: str = None) -> List[Dict[str, str]]:
        """
        Scrape acestream links desde la URL configurada
        
        Args:
            url: URL a scrapear (usa la default si no se especifica)
        
        Returns:
            Lista de diccionarios con {name, url}
        """
        target_url = url or self.scrape_url
        
        try:
            headers = {'User-Agent': USER_AGENT}
            response = requests.get(target_url, headers=headers, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            
            logger.info(f"Scrapeando {target_url}...")
            soup = BeautifulSoup(response.content, 'html.parser')
            acestream_links = []
            
            # Buscar enlaces acestream:// en atributos href
            for link in soup.find_all('a', href=re.compile(r'acestream://')):
                href = link.get('href', '').strip()
                text = link.get_text(strip=True)
                if href and href.startswith('acestream://'):
                    acestream_links.append({
                        'name': text if text else 'Acestream',
                        'url': f'http://127.0.0.1:6878/ace/getstream?id={href[12:]}'
                    })
            
            # Buscar acestream:// en nodos de texto
            for text_node in soup.find_all(string=re.compile(r'acestream://')):
                matches = re.findall(r'acestream://[a-f0-9]{40}', text_node)
                for match in matches:
                    stream_url = f'http://127.0.0.1:6878/ace/getstream?id={match[12:]}'
                    if not any(link['url'] == stream_url for link in acestream_links):
                        acestream_links.append({
                            'name': 'Acestream Stream',
                            'url': stream_url
                        })
            
            logger.info(f"Se encontraron {len(acestream_links)} enlaces de acestream")
            return acestream_links
            
        except requests.RequestException as e:
            logger.error(f"Error al scrapear {target_url}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error inesperado scrapeando: {e}")
            return []
    
    def remove_duplicates(self, acestream_links: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Elimina enlaces duplicados basándose en la URL
        
        Args:
            acestream_links: Lista de enlaces
        
        Returns:
            Lista sin duplicados, manteniendo la primera ocurrencia
        """
        seen_urls = set()
        unique_links = []
        
        for link in acestream_links:
            url = link['url']
            if url not in seen_urls:
                seen_urls.add(url)
                unique_links.append(link)
        
        duplicates_removed = len(acestream_links) - len(unique_links)
        if duplicates_removed > 0:
            logger.info(f"Se removieron {duplicates_removed} enlaces duplicados")
        
        return unique_links
    
    def categorize_channel(self, channel_name: str) -> str:
        """
        Categoriza un canal basándose en su nombre
        
        Args:
            channel_name: Nombre del canal
        
        Returns:
            Categoría del canal
        """
        name_lower = channel_name.lower()
        
        for category, keywords in CHANNEL_CATEGORIES.items():
            for keyword in keywords:
                if keyword in name_lower:
                    return category
        
        return DEFAULT_CATEGORY
    
    def group_by_category(self, acestream_links: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
        """
        Agrupa canales por categoría
        
        Args:
            acestream_links: Lista de enlaces
        
        Returns:
            Diccionario con canales agrupados por categoría
        """
        categories = {cat: [] for cat in CHANNEL_CATEGORIES.keys()}
        categories[DEFAULT_CATEGORY] = []
        
        for link in acestream_links:
            category = self.categorize_channel(link['name'])
            link['category'] = category
            categories[category].append(link)
        
        return categories
    
    def process_links(self, url: str = None) -> List[Dict[str, str]]:
        """
        Procesa completamente: scrape, dedup, categorización
        
        Args:
            url: URL a scrapear (usa default si no se especifica)
        
        Returns:
            Lista de enlaces únicos categorizados
        """
        # Scrapear
        links = self.scrape(url)
        if not links:
            return []
        
        # Eliminar duplicados
        links = self.remove_duplicates(links)
        
        # Agrupar (esto adiciona el campo 'category')
        grouped = self.group_by_category(links)
        
        # Retornar todos planos pero con categoría añadida
        result = []
        for category_list in grouped.values():
            result.extend(category_list)
        
        return result
