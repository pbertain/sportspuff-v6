#!/usr/bin/env python3
"""
Stadium Image Fetcher Script

This script fetches high-quality stadium images for teams from MLB, MLS, NBA, NFL, NHL, WNBA, and IPL leagues.
Images are saved in the format: stadiums/{lower_case_league}/{lower_case_stadium_name}_img.png
"""

import os
import csv
import requests
import time
from urllib.parse import quote_plus
from PIL import Image
from io import BytesIO
import json
import re
from typing import Dict, List, Tuple, Optional

class StadiumImageFetcher:
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
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Rate limiting
        self.request_delay = 1.0
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
        # Remove common suffixes and clean up
        name = stadium_name.lower()
        name = re.sub(r'\s+(stadium|arena|park|field|center|centre|dome|coliseum)$', '', name)
        name = re.sub(r'[^\w\s-]', '', name)  # Remove special characters except hyphens
        name = re.sub(r'\s+', '_', name)  # Replace spaces with underscores
        name = re.sub(r'_+', '_', name)  # Remove multiple underscores
        name = name.strip('_')  # Remove leading/trailing underscores
        return name
    
    def rate_limit(self):
        """Implement rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_delay:
            time.sleep(self.request_delay - time_since_last)
        self.last_request_time = time.time()
    
    def search_stadium_images_bing(self, stadium_name: str, city: str = "") -> List[str]:
        """Search for stadium images using Bing Image Search API simulation"""
        self.rate_limit()
        
        # Create search query
        query_terms = [stadium_name]
        if city:
            query_terms.append(city)
        query_terms.extend(["stadium", "exterior", "aerial view"])
        
        query = " ".join(query_terms)
        
        # Bing image search URL (we'll scrape the results page)
        search_url = f"https://www.bing.com/images/search?q={quote_plus(query)}&form=HDRSC2&first=1&tsc=ImageHoverTitle"
        
        try:
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()
            
            # Extract image URLs from the response
            image_urls = []
            
            # Look for image URLs in the HTML - Bing embeds them in various formats
            patterns = [
                r'"murl":"([^"]+)"',
                r'"purl":"([^"]+)"',
                r'data-src="([^"]+)"',
                r'src="([^"]+)"'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, response.text)
                for match in matches:
                    if any(ext in match.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                        if match.startswith('http') and len(match) > 50:  # Filter out small icons
                            image_urls.append(match)
            
            # Remove duplicates and return top results
            return list(dict.fromkeys(image_urls))[:10]
            
        except Exception as e:
            print(f"Error searching for {stadium_name}: {e}")
            return []
    
    def search_stadium_images_google(self, stadium_name: str, city: str = "") -> List[str]:
        """Alternative search using Google Images (fallback)"""
        self.rate_limit()
        
        query_terms = [stadium_name]
        if city:
            query_terms.append(city)
        query_terms.extend(["stadium", "exterior"])
        
        query = " ".join(query_terms)
        search_url = f"https://www.google.com/search?q={quote_plus(query)}&tbm=isch"
        
        try:
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()
            
            # Extract image URLs from Google Images results
            image_urls = []
            patterns = [
                r'"ou":"([^"]+)"',
                r'data-src="([^"]+)"'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, response.text)
                for match in matches:
                    if any(ext in match.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                        if match.startswith('http'):
                            image_urls.append(match)
            
            return list(dict.fromkeys(image_urls))[:10]
            
        except Exception as e:
            print(f"Error searching Google for {stadium_name}: {e}")
            return []
    
    def download_and_process_image(self, url: str, output_path: str) -> bool:
        """Download and process image from URL"""
        self.rate_limit()
        
        try:
            response = self.session.get(url, timeout=15, stream=True)
            response.raise_for_status()
            
            # Check if it's actually an image
            content_type = response.headers.get('content-type', '').lower()
            if not any(img_type in content_type for img_type in ['image/', 'jpeg', 'png', 'webp']):
                return False
            
            # Load image data
            img_data = BytesIO(response.content)
            img = Image.open(img_data)
            
            # Validate image dimensions (filter out small images/icons)
            if img.width < 400 or img.height < 300:
                return False
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Save as PNG
            img.save(output_path, 'PNG', quality=95)
            
            print(f"✓ Downloaded: {os.path.basename(output_path)}")
            return True
            
        except Exception as e:
            print(f"  Error downloading {url}: {e}")
            return False
    
    def fetch_stadium_image(self, stadium_data: Dict, league: str) -> bool:
        """Fetch the best image for a stadium"""
        stadium = stadium_data['stadium']
        stadium_name = stadium['full_stadium_name']
        city = stadium.get('city_name', '')
        
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
        
        # Try Bing first, then Google as fallback
        image_urls = self.search_stadium_images_bing(stadium_name, city)
        if not image_urls:
            print("  Trying Google Images...")
            image_urls = self.search_stadium_images_google(stadium_name, city)
        
        if not image_urls:
            print(f"  ❌ No images found for {stadium_name}")
            return False
        
        print(f"  Found {len(image_urls)} potential images")
        
        # Try to download the best image
        for i, url in enumerate(image_urls[:5]):  # Try top 5 images
            print(f"  Trying image {i+1}/{min(5, len(image_urls))}: {url[:60]}...")
            
            if self.download_and_process_image(url, output_path):
                teams_list = [team['real_team_name'] for team in stadium_data['teams']]
                print(f"  ✅ Successfully downloaded image for {stadium_name}")
                print(f"     Teams: {', '.join(teams_list)}")
                return True
        
        print(f"  ❌ Failed to download any images for {stadium_name}")
        return False
    
    def run(self):
        """Main execution method"""
        print("🏟️  Stadium Image Fetcher")
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
            
            # Progress update every 10 stadiums
            if i % 10 == 0:
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
    fetcher = StadiumImageFetcher()
    fetcher.run()