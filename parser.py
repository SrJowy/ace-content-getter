"""
Parser de Acestream - CLI compatible
Este módulo ahora usa la estructura modular app/services/acestream_parser.py internamente
Se mantiene la interfaz CLI por compatibilidad
"""

from app.services.acestream_parser import AcestreamParser
from app.services.m3u_generator import M3UGenerator
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Crear instancias globales para compatibilidad con código antiguo
_parser = AcestreamParser()
_generator = M3UGenerator()


def scrape_acestream_links(url='https://ciriaco.netlify.app/'):
    """
    Scrape Acestream links from the website
    (Función compatible con interfaz antigua)
    """
    return _parser.scrape(url)


def remove_duplicates(acestream_links):
    """
    Remove duplicate links based on URL, keeping the first occurrence
    (Función compatible con interfaz antigua)
    """
    return _parser.remove_duplicates(acestream_links)


def categorize_channel(channel_name):
    """
    Categorize a channel based on its name
    (Función compatible con interfaz antigua)
    """
    return _parser.categorize_channel(channel_name)


def group_channels_by_category(acestream_links):
    """
    Group channels by category
    (Función compatible con interfaz antigua)
    """
    return _parser.group_by_category(acestream_links)


def getChannelName(channel_name):
    """
    Generate a valid tvg-id from channel name
    (Función compatible con interfaz antigua)
    """
    import re
    splitter = re.split(r'1080p|720p|-->|\*', channel_name)
    tvg_id = splitter[0].strip()
    return tvg_id


def generate_m3u_content(acestream_links):
    """
    Generate M3U playlist content from Acestream links as string
    (Función compatible con interfaz antigua)
    """
    return M3UGenerator.generate_with_categories(acestream_links)


def generate_m3u(acestream_links, output_file='playlist.m3u'):
    """
    Generate M3U playlist from Acestream links, grouped by category (writes to file)
    (Función compatible con interfaz antigua)
    """
    if not acestream_links:
        print("No Acestream links found")
        return False
    
    try:
        # Get content as string
        content = generate_m3u_content(acestream_links)
        if not content:
            return False
        
        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"M3U playlist generated: {output_file}")
        print(f"Total links: {len(acestream_links)}")
        
        # Show summary by category
        categories = group_channels_by_category(acestream_links)
        for category in ['LaLiga', 'DAZN', 'Eurosport', 'M+ Deportes', '1RFEF', 'OTROS']:
            count = len(categories.get(category, []))
            if count > 0:
                print(f"  - {category}: {count} link(s)")
        
        return True
        
    except IOError as e:
        print(f"Error writing M3U file: {e}")
        return False


def main():
    """Main CLI entry point"""
    url = 'https://ciriaco.netlify.app/'
    print(f"Scraping Acestream links from {url}...")
    
    links = scrape_acestream_links(url)
    
    if links:
        print(f"Found {len(links)} Acestream link(s)")
        
        # Remove duplicates
        unique_links = remove_duplicates(links)
        duplicates_removed = len(links) - len(unique_links)
        
        if duplicates_removed > 0:
            print(f"Removed {duplicates_removed} duplicate link(s)")
        
        for link in unique_links:
            print(f"  - {link['name']}: {link['url']}")
        
        generate_m3u(unique_links)
    else:
        print("No Acestream links found")


if __name__ == '__main__':
    main()
