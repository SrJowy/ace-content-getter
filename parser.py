import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

def scrape_acestream_links(url):
    """Scrape Acestream links from the website"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        acestream_links = []
        
        # Find all acestream:// links
        for link in soup.find_all('a', href=re.compile(r'acestream://')):
            href = link.get('href', '').strip()
            text = link.get_text(strip=True)
            if href and href.startswith('acestream://'):
                acestream_links.append({
                    'name': text if text else 'Acestream',
                    'url': f'http://127.0.0.1:6878/ace/getstream?id={href[12:]}'
                })
        
        # Also search for acestream:// in text nodes
        for text_node in soup.find_all(string=re.compile(r'acestream://')):
            matches = re.findall(r'acestream://[a-f0-9]{40}', text_node)
            for match in matches:
                if not any(link['url'] == f'http://127.0.0.1:6878/ace/getstream?id={match[12:]}' for link in acestream_links):
                    acestream_links.append({
                        'name': 'Acestream Stream',
                        'url': f'http://127.0.0.1:6878/ace/getstream?id={match[12:]}'
                    })
        
        return acestream_links
    
    except requests.RequestException as e:
        print(f"Error fetching the website: {e}")
        return []

def remove_duplicates(acestream_links):
    """Remove duplicate links based on URL, keeping the first occurrence"""
    seen_urls = set()
    unique_links = []
    
    for link in acestream_links:
        url = link['url']
        if url not in seen_urls:
            seen_urls.add(url)
            unique_links.append(link)
    
    return unique_links

def categorize_channel(channel_name):
    """Categorize a channel based on its name"""
    name_lower = channel_name.lower()
    
    # LaLiga category
    if 'la liga' in name_lower or 'laliga' in name_lower:
        return 'LaLiga'
    
    # DAZN category (but not LaLiga)
    if 'dazn' in name_lower and not ('la liga' in name_lower or 'laliga' in name_lower):
        return 'DAZN'
    
    # Eurosport category
    if 'eurosport' in name_lower:
        return 'Eurosport'
    
    # M+ Deportes category
    if 'm+ deportes' in name_lower:
        return 'M+ Deportes'
    
    if '1rfef' in name_lower or 'rfef' in name_lower:
        return '1RFEF'
    
    # Default category
    return 'OTROS'

def group_channels_by_category(acestream_links):
    """Group channels by category"""
    categories = {
        'LaLiga': [],
        'DAZN': [],
        'Eurosport': [],
        'M+ Deportes': [],
        '1RFEF': [],
        'OTROS': []
    }
    
    for link in acestream_links:
        category = categorize_channel(link['name'])
        link['category'] = category
        categories[category].append(link)
    
    return categories

def getChannelName(channel_name):
    """Generate a valid tvg-id from channel name"""

    splitter = re.split(r'1080p|720p|-->|\*', channel_name)

    tvg_id = splitter[0].strip()

    return tvg_id

def generate_m3u_content(acestream_links):
    """Generate M3U playlist content from Acestream links as string (for in-memory use)"""
    if not acestream_links:
        return None
    
    try:
        # Group channels by category
        categories = group_channels_by_category(acestream_links)
        
        content = '#EXTM3U url-tvg="https://raw.githubusercontent.com/davidmuma/EPG_dobleM/refs/heads/master/guiatv.xml,https://epgshare01.online/epgshare01/epg_ripper_NL1.xml.gz,' \
        'https://raw.githubusercontent.com/davidmuma/EPG_dobleM/master/guiatv.xml" refresh="3600"\n#EXTVLCOPT:network-caching=1000\n\n'
        
        # Write channels grouped by category
        for category in ['LaLiga', 'DAZN', 'Eurosport', 'M+ Deportes', '1RFEF', 'OTROS']:
            if categories[category]:
                for link in categories[category]:
                    content += f"#EXTINF:-1, tvg-id=\"{getChannelName(link['name'])}\",group-title=\"{category}\",{link['name']}\n"
                    content += f"{link['url']}\n"
        
        return content
    
    except Exception as e:
        print(f"Error generating M3U content: {e}")
        return None

def generate_m3u(acestream_links, output_file='playlist.m3u'):
    """Generate M3U playlist from Acestream links, grouped by category (writes to file)"""
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
            count = len(categories[category])
            if count > 0:
                print(f"  - {category}: {count} link(s)")
        
        return True
    
    except IOError as e:
        print(f"Error writing M3U file: {e}")
        return False

def main():
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
