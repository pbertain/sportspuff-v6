#!/usr/bin/env python3
"""
Debug script to test image search methods
"""

import requests
import re
from urllib.parse import quote_plus

def test_bing_search():
    """Test current Bing search method"""
    print("=" * 50)
    print("Testing Bing Image Search")
    print("=" * 50)
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    
    query = "fenway park stadium exterior"
    search_url = f"https://www.bing.com/images/search?q={quote_plus(query)}&form=HDRSC2&first=1&tsc=ImageHoverTitle"
    
    try:
        print(f"URL: {search_url}")
        response = session.get(search_url, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type', 'N/A')}")
        print(f"Response Length: {len(response.text)} characters")
        
        if response.status_code == 200:
            # Look for image URLs in the response
            patterns = [
                r'"murl":"([^"]+)"',
                r'"purl":"([^"]+)"',
                r'data-src="([^"]+)"',
                r'src="([^"]+)"'
            ]
            
            all_urls = []
            for pattern in patterns:
                matches = re.findall(pattern, response.text)
                print(f"Pattern '{pattern}' found {len(matches)} matches")
                all_urls.extend(matches)
            
            # Filter for actual image URLs
            image_urls = []
            for url in all_urls:
                if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    if url.startswith('http') and len(url) > 50:
                        image_urls.append(url)
            
            print(f"Found {len(image_urls)} image URLs:")
            for i, url in enumerate(image_urls[:3]):
                print(f"  {i+1}: {url}")
                
        else:
            print(f"Error: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"Exception: {e}")

def test_alternative_sources():
    """Test alternative image sources"""
    print("=" * 50)
    print("Testing Alternative Sources")
    print("=" * 50)
    
    # Test DuckDuckGo Images (more permissive)
    try:
        print("Testing DuckDuckGo Images...")
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        
        query = "fenway park stadium"
        search_url = f"https://duckduckgo.com/?q={quote_plus(query)}&t=h_&iax=images&ia=images"
        
        response = session.get(search_url, timeout=10)
        print(f"DuckDuckGo Status: {response.status_code}")
        print(f"DuckDuckGo Content Length: {len(response.text)}")
        
    except Exception as e:
        print(f"DuckDuckGo Error: {e}")
    
    # Test Wikimedia Commons
    try:
        print("Testing Wikimedia Commons API...")
        api_url = "https://commons.wikimedia.org/w/api.php"
        params = {
            'action': 'query',
            'format': 'json',
            'list': 'search',
            'srsearch': 'fenway park stadium',
            'srnamespace': 6,  # File namespace
            'srlimit': 5
        }
        
        response = requests.get(api_url, params=params, timeout=10)
        print(f"Wikimedia Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'query' in data and 'search' in data['query']:
                results = data['query']['search']
                print(f"Found {len(results)} Wikimedia results:")
                for result in results[:3]:
                    print(f"  - {result['title']}")
        
    except Exception as e:
        print(f"Wikimedia Error: {e}")

if __name__ == "__main__":
    test_bing_search()
    print("\n")
    test_alternative_sources()