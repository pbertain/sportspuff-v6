#!/usr/bin/env python3
"""
Improved Stadium Image Fetcher Script

This version uses multiple reliable image sources:
1. Wikimedia Commons API (high-quality, free images)
2. Wikipedia image extraction 
3. DuckDuckGo Instant Answer API
4. Direct team/stadium website scraping
5. Fallback to improved web scraping
"""

import os
import csv
import requests
import time
import json
import re
from urllib.parse import quote_plus, urljoin, urlparse
from PIL import Image
from io import BytesIO
from typing import Dict, List, Tuple, Optional

class ImprovedStadiumImageFetcher:
    def __init__(self):
        self.base_dir = "stadiums"
        self.target_leagues = {
            'mlb': 1,
            'mls': 2, 
            'nba': 3,
            'nfl': 4,
            'nhl': 5,
            'wnba': 6,
            'ipl': 7
        }
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Rate limiting
        self.request_delay = 2.0  # Increased delay
        self.last_request_time = 0
        
    def load_data(self) -> Tuple[Dict, Dict, Dict]:
        """Load teams, stadiums, and leagues data from CSV files"""
        teams = {}
        stadiums = {}
        leagues = {}
        
        # Load leagues
        try:
            with open('info-leagues.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    leagues[int(row['league_id'])] = row
        except Exception as e:
            print(f"Error loading leagues: {e}")
            
        # Load stadiums
        try:
            with open('info-stadiums.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stadiums[int(row['stadium_id'])] = row
        except Exception as e:
            print(f"Error loading stadiums: {e}")
            
        # Load teams
        try:
            with open('info-teams.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    teams[int(row['team_id'])] = row
        except Exception as e:
            print(f"Error loading teams: {e}")
            
        return teams, stadiums, leagues
    
    def get_stadium_team_mapping(self, teams: Dict, stadiums: Dict, leagues: Dict) -> Dict:
        """Create mapping of stadiums to teams for target leagues"""
        stadium_mapping = {}
        
        for team_id, team in teams.items():
            league_id = int(team['league_id'])
            stadium_id = int(team['stadium_id'])
            
            # Only process teams from target leagues
            league_name = None
            for league_key, lid in self.target_leagues.items():
                if lid == league_id:
                    league_name = league_key
                    break
                    
            if not league_name:
                continue
                
            if stadium_id not in stadiums:
                print(f"Stadium ID {stadium_id} not found for team {team['real_team_name']}")
                continue
                
            stadium = stadiums[stadium_id]
            stadium_key = f"{league_name}_{stadium_id}"
            
            if stadium_key not in stadium_mapping:
                stadium_mapping[stadium_key] = {
                    'stadium': stadium,
                    'league': league_name,
                    'teams': []
                }
            
            stadium_mapping[stadium_key]['teams'].append(team)
            
        return stadium_mapping
    
    def clean_stadium_name(self, stadium_name: str) -> str:
        """Clean stadium name for filename"""
        name = stadium_name.lower()
        name = re.sub(r'\s+(stadium|arena|park|field|center|centre|dome|coliseum)$', '', name)
        name = re.sub(r'[^\w\s-]', '', name)
        name = re.sub(r'\s+', '_', name)
        name = re.sub(r'_+', '_', name)
        name = name.strip('_')
        return name
    
    def rate_limit(self):
        """Implement rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_delay:
            time.sleep(self.request_delay - time_since_last)
        self.last_request_time = time.time()
    
    def search_wikimedia_commons(self, stadium_name: str, city: str = "") -> List[str]:
        """Search Wikimedia Commons for stadium images"""
        self.rate_limit()
        
        search_terms = [stadium_name]
        if city:
            search_terms.append(city)
        search_terms.append("stadium")
        
        query = " ".join(search_terms)
        
        try:
            # Search for files
            api_url = "https://commons.wikimedia.org/w/api.php"
            params = {
                'action': 'query',
                'format': 'json',
                'list': 'search',
                'srsearch': query,
                'srnamespace': 6,  # File namespace
                'srlimit': 10
            }
            
            response = self.session.get(api_url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            image_urls = []
            
            if 'query' in data and 'search' in data['query']:
                for result in data['query']['search']:
                    title = result['title']
                    if 'File:' in title:
                        # Get the actual file URL
                        file_params = {
                            'action': 'query',
                            'format': 'json',
                            'titles': title,
                            'prop': 'imageinfo',
                            'iiprop': 'url|size',
                            'iiurlwidth': 1200
                        }
                        
                        file_response = self.session.get(api_url, params=file_params, timeout=10)
                        file_data = file_response.json()
                        
                        if 'query' in file_data and 'pages' in file_data['query']:
                            for page_id, page_data in file_data['query']['pages'].items():
                                if 'imageinfo' in page_data:
                                    img_info = page_data['imageinfo'][0]
                                    if 'url' in img_info:
                                        image_urls.append(img_info['url'])
            
            return image_urls[:5]  # Return top 5
            
        except Exception as e:
            print(f"  Wikimedia Commons error: {e}")
            return []
    
    def search_wikipedia_images(self, stadium_name: str, city: str = "") -> List[str]:
        """Search Wikipedia for stadium images"""
        self.rate_limit()
        
        try:
            # Search for Wikipedia articles
            search_url = "https://en.wikipedia.org/w/api.php"
            search_params = {
                'action': 'query',
                'format': 'json',
                'list': 'search',
                'srsearch': f"{stadium_name} {city} stadium",
                'srlimit': 3
            }
            
            response = self.session.get(search_url, params=search_params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            image_urls = []
            
            if 'query' in data and 'search' in data['query']:
                for result in data['query']['search']:
                    page_title = result['title']
                    
                    # Get images from the page
                    images_params = {
                        'action': 'query',
                        'format': 'json',
                        'titles': page_title,
                        'prop': 'images',
                        'imlimit': 10
                    }
                    
                    img_response = self.session.get(search_url, params=images_params, timeout=10)
                    img_data = img_response.json()
                    
                    if 'query' in img_data and 'pages' in img_data['query']:
                        for page_id, page_data in img_data['query']['pages'].items():
                            if 'images' in page_data:
                                for img in page_data['images']:
                                    title = img['title']
                                    if any(ext in title.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                                        # Get the actual image URL
                                        img_url_params = {
                                            'action': 'query',
                                            'format': 'json',
                                            'titles': title,
                                            'prop': 'imageinfo',
                                            'iiprop': 'url',
                                            'iiurlwidth': 1200
                                        }
                                        
                                        url_response = self.session.get(search_url, params=img_url_params, timeout=10)
                                        url_data = url_response.json()
                                        
                                        if 'query' in url_data and 'pages' in url_data['query']:
                                            for url_page_id, url_page_data in url_data['query']['pages'].items():
                                                if 'imageinfo' in url_page_data:
                                                    img_info = url_page_data['imageinfo'][0]
                                                    if 'url' in img_info:
                                                        image_urls.append(img_info['url'])
            
            return list(dict.fromkeys(image_urls))[:5]  # Remove duplicates, return top 5
            
        except Exception as e:
            print(f"  Wikipedia error: {e}")
            return []
    
    def search_duckduckgo_images(self, stadium_name: str, city: str = "") -> List[str]:
        """Search DuckDuckGo for images (more permissive than Google/Bing)"""
        self.rate_limit()
        
        try:
            query_terms = [stadium_name]
            if city:
                query_terms.append(city)
            query_terms.extend(["stadium", "exterior"])
            
            query = " ".join(query_terms)
            
            # DuckDuckGo doesn't block scraping as aggressively
            search_url = f"https://duckduckgo.com/?q={quote_plus(query)}&t=h_&iax=images&ia=images"
            
            response = self.session.get(search_url, timeout=15)
            response.raise_for_status()
            
            # Extract image URLs from DuckDuckGo results
            image_urls = []
            patterns = [
                r'"image":"([^"]+)"',
                r'data-src="([^"]+)"',
                r'src="([^"]+)"'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, response.text)
                for match in matches:
                    if any(ext in match.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                        if match.startswith('http') and len(match) > 50:
                            # Decode URL if needed
                            url = match.replace('\\u002F', '/').replace('\\', '')
                            image_urls.append(url)
            
            return list(dict.fromkeys(image_urls))[:5]
            
        except Exception as e:
            print(f"  DuckDuckGo error: {e}")
            return []
    
    def search_direct_sources(self, stadium_name: str, teams: List[Dict]) -> List[str]:
        """Try to find images from official team/stadium websites"""
        self.rate_limit()
        
        image_urls = []
        
        # Common stadium/team website patterns
        search_terms = [
            f"{stadium_name} official website",
            f"{stadium_name} photos gallery",
        ]
        
        # Add team websites
        for team in teams:
            team_name = team['real_team_name']
            search_terms.append(f"{team_name} stadium photos")
        
        for search_term in search_terms[:2]:  # Limit searches
            try:
                # Use DuckDuckGo to find official sites
                search_url = f"https://duckduckgo.com/html/?q={quote_plus(search_term)}"
                response = self.session.get(search_url, timeout=10)
                
                # Extract first few URLs
                url_pattern = r'href="([^"]+)"'
                matches = re.findall(url_pattern, response.text)
                
                for match in matches[:3]:  # Check first 3 results
                    if match.startswith('http') and any(domain in match for domain in ['.com', '.org', '.net']):
                        try:
                            # Visit the page and look for images
                            page_response = self.session.get(match, timeout=10)
                            img_pattern = r'<img[^>]+src="([^"]+)"'
                            img_matches = re.findall(img_pattern, page_response.text, re.IGNORECASE)
                            
                            for img_url in img_matches:
                                if not img_url.startswith('http'):
                                    img_url = urljoin(match, img_url)
                                
                                if any(ext in img_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                                    image_urls.append(img_url)
                                    
                        except:
                            continue  # Skip failed pages
                            
            except Exception as e:
                print(f"  Direct source error for '{search_term}': {e}")
                continue
        
        return list(dict.fromkeys(image_urls))[:3]  # Return unique URLs
    
    def download_and_process_image(self, url: str, output_path: str) -> bool:
        """Download and process image from URL"""
        self.rate_limit()
        
        try:
            # Add better headers for image requests
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Referer': 'https://www.google.com/'
            }
            
            response = self.session.get(url, timeout=20, stream=True, headers=headers)
            response.raise_for_status()
            
            # Check if it's actually an image
            content_type = response.headers.get('content-type', '').lower()
            if not any(img_type in content_type for img_type in ['image/', 'jpeg', 'png', 'webp']):
                print(f"    Not an image: {content_type}")
                return False
            
            # Load image data
            img_data = BytesIO(response.content)
            img = Image.open(img_data)
            
            # Validate image dimensions (filter out small images/icons)
            if img.width < 500 or img.height < 300:
                print(f"    Too small: {img.width}x{img.height}")
                return False
            
            # Check aspect ratio (stadium images should be wider than tall)
            aspect_ratio = img.width / img.height
            if aspect_ratio < 0.8:  # Very tall images are likely not stadium exteriors
                print(f"    Bad aspect ratio: {aspect_ratio:.2f}")
                return False
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Resize if too large (save space)
            if img.width > 1200:
                ratio = 1200 / img.width
                new_height = int(img.height * ratio)
                img = img.resize((1200, new_height), Image.Resampling.LANCZOS)
            
            # Save as PNG
            img.save(output_path, 'PNG', optimize=True)
            
            print(f"    ✓ Downloaded: {os.path.basename(output_path)} ({img.width}x{img.height})")
            return True
            
        except Exception as e:
            print(f"    Error downloading {url[:60]}...: {e}")
            return False
    
    def fetch_stadium_image(self, stadium_data: Dict, league: str) -> bool:
        """Fetch the best image for a stadium using multiple sources"""
        stadium = stadium_data['stadium']
        stadium_name = stadium['full_stadium_name']
        city = stadium.get('city_name', '')
        teams = stadium_data['teams']
        
        # Create output directory
        league_dir = os.path.join(self.base_dir, league.lower())
        os.makedirs(league_dir, exist_ok=True)
        
        # Generate filename
        clean_name = self.clean_stadium_name(stadium_name)
        output_filename = f"{clean_name}_img.png"
        output_path = os.path.join(league_dir, output_filename)
        
        # Skip if file already exists
        if os.path.exists(output_path):
            print(f"⏭ Skipping {stadium_name} - file already exists")
            return True
        
        print(f"🔍 Searching for images of {stadium_name} ({city})")
        teams_list = [team['real_team_name'] for team in teams]
        print(f"    Teams: {', '.join(teams_list)}")
        
        all_image_urls = []
        
        # Method 1: Wikimedia Commons (highest quality, most reliable)
        print("  1. Checking Wikimedia Commons...")
        wikimedia_urls = self.search_wikimedia_commons(stadium_name, city)
        if wikimedia_urls:
            print(f"     Found {len(wikimedia_urls)} Wikimedia images")
            all_image_urls.extend(wikimedia_urls)
        
        # Method 2: Wikipedia
        print("  2. Checking Wikipedia...")
        wikipedia_urls = self.search_wikipedia_images(stadium_name, city)
        if wikipedia_urls:
            print(f"     Found {len(wikipedia_urls)} Wikipedia images")
            all_image_urls.extend(wikipedia_urls)
        
        # Method 3: DuckDuckGo
        print("  3. Checking DuckDuckGo...")
        ddg_urls = self.search_duckduckgo_images(stadium_name, city)
        if ddg_urls:
            print(f"     Found {len(ddg_urls)} DuckDuckGo images")
            all_image_urls.extend(ddg_urls)
        
        # Method 4: Direct sources
        print("  4. Checking direct sources...")
        direct_urls = self.search_direct_sources(stadium_name, teams)
        if direct_urls:
            print(f"     Found {len(direct_urls)} direct source images")
            all_image_urls.extend(direct_urls)
        
        # Remove duplicates while preserving order
        unique_urls = list(dict.fromkeys(all_image_urls))
        
        if not unique_urls:
            print(f"  ❌ No images found for {stadium_name}")
            return False
        
        print(f"  📊 Total unique URLs found: {len(unique_urls)}")
        
        # Try to download the best image
        for i, url in enumerate(unique_urls[:8]):  # Try up to 8 images
            print(f"  Trying image {i+1}/{min(8, len(unique_urls))}: {url[:60]}...")
            
            if self.download_and_process_image(url, output_path):
                print(f"  ✅ Successfully downloaded image for {stadium_name}")
                return True
        
        print(f"  ❌ Failed to download any images for {stadium_name}")
        return False
    
    def run(self):
        """Main execution method"""
        print("🏟️  Improved Stadium Image Fetcher")
        print("=" * 50)
        
        # Load data
        print("📊 Loading data from CSV files...")
        teams, stadiums, leagues = self.load_data()
        
        if not teams or not stadiums or not leagues:
            print("❌ Failed to load required data files")
            return
        
        print(f"   Loaded {len(teams)} teams, {len(stadiums)} stadiums, {len(leagues)} leagues")
        
        # Create stadium mapping
        print("🗺️  Creating stadium mappings...")
        stadium_mapping = self.get_stadium_team_mapping(teams, stadiums, leagues)
        
        total_stadiums = len(stadium_mapping)
        print(f"   Found {total_stadiums} unique stadiums across target leagues")
        
        # Group by league for progress tracking
        league_counts = {}
        for stadium_data in stadium_mapping.values():
            league = stadium_data['league']
            league_counts[league] = league_counts.get(league, 0) + 1
        
        print("\n📈 Stadiums per league:")
        for league, count in sorted(league_counts.items()):
            print(f"   {league.upper()}: {count} stadiums")
        
        # Create base directory
        os.makedirs(self.base_dir, exist_ok=True)
        
        # Process each stadium
        print(f"\n🚀 Starting image download process...")
        print("=" * 50)
        
        successful_downloads = 0
        failed_downloads = 0
        
        for i, (stadium_key, stadium_data) in enumerate(stadium_mapping.items(), 1):
            stadium_name = stadium_data['stadium']['full_stadium_name']
            league = stadium_data['league']
            
            print(f"\n[{i}/{total_stadiums}] {league.upper()}: {stadium_name}")
            
            if self.fetch_stadium_image(stadium_data, league):
                successful_downloads += 1
            else:
                failed_downloads += 1
            
            # Progress update every 5 stadiums
            if i % 5 == 0:
                print(f"\n📊 Progress: {i}/{total_stadiums} processed")
                print(f"   ✅ Successful: {successful_downloads}")
                print(f"   ❌ Failed: {failed_downloads}")
        
        # Final summary
        print("\n" + "=" * 50)
        print("🏁 DOWNLOAD COMPLETE")
        print("=" * 50)
        print(f"Total stadiums processed: {total_stadiums}")
        print(f"✅ Successful downloads: {successful_downloads}")
        print(f"❌ Failed downloads: {failed_downloads}")
        print(f"📁 Images saved to: {os.path.abspath(self.base_dir)}/")
        
        # Show directory structure
        print(f"\n📂 Directory structure created:")
        for league in sorted(league_counts.keys()):
            league_dir = os.path.join(self.base_dir, league)
            if os.path.exists(league_dir):
                files = [f for f in os.listdir(league_dir) if f.endswith('_img.png')]
                print(f"   {league}/ ({len(files)} images)")

if __name__ == "__main__":
    fetcher = ImprovedStadiumImageFetcher()
    fetcher.run()