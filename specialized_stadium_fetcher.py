#!/usr/bin/env python3
"""
Specialized Stadium Image Fetcher Script

This version uses official league-specific sources:
1. ballparksofbaseball.com for MLB stadiums (with detailed info)
2. nba.com for NBA arenas  
3. Fallback to improved general method for other leagues
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

class SpecializedStadiumImageFetcher:
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
            'Connection': 'keep-alive',
        })
        
        # Rate limiting
        self.request_delay = 1.5  
        self.last_request_time = 0
        
        # Cache for league-specific data
        self.mlb_ballpark_cache = {}
        self.nfl_stadium_cache = {}
        self.nhl_arena_cache = {}
        
    def load_data(self) -> Tuple[Dict, Dict, Dict]:
        """Load teams, stadiums, and leagues data from CSV files"""
        teams = {}
        stadiums = {}
        leagues = {}
        
        try:
            with open('info-leagues.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    leagues[int(row['league_id'])] = row
        except Exception as e:
            print(f"Error loading leagues: {e}")
            
        try:
            with open('info-stadiums.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stadiums[int(row['stadium_id'])] = row
        except Exception as e:
            print(f"Error loading stadiums: {e}")
            
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
    
    def load_mlb_ballpark_links(self) -> Dict[str, str]:
        """Load all MLB ballpark links from ballparksofbaseball.com"""
        if self.mlb_ballpark_cache:
            return self.mlb_ballpark_cache
            
        print("  📋 Loading MLB ballpark directory from ballparksofbaseball.com...")
        self.rate_limit()
        
        ballpark_links = {}
        
        # Load both American League and National League pages
        for league_page in ['american-league', 'national-league']:
            try:
                url = f"https://www.ballparksofbaseball.com/{league_page}/"
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                
                # Extract ballpark links
                # Fix the regex to handle the duplicate URLs properly
                links = re.findall(r'href=\"([^\"]*ballparks/[^\"]+)\"', response.text)
                
                for link in links:
                    # Clean up duplicate URL issue
                    if link.startswith('https://www.ballparksofbaseball.com'):
                        clean_link = link
                    else:
                        clean_link = f"https://www.ballparksofbaseball.com{link}"
                    
                    # Extract ballpark name from URL
                    match = re.search(r'/ballparks/([^/]+)/?$', clean_link)
                    if match:
                        ballpark_slug = match.group(1)
                        ballpark_name = ballpark_slug.replace('-', ' ').title()
                        ballpark_links[ballpark_name] = clean_link
                
            except Exception as e:
                print(f"    Error loading {league_page}: {e}")
        
        self.mlb_ballpark_cache = ballpark_links
        print(f"    Found {len(ballpark_links)} MLB ballparks")
        return ballpark_links
    
    def search_mlb_ballpark_images(self, stadium_name: str, teams: List[Dict]) -> List[str]:
        """Search for MLB stadium images using ballparksofbaseball.com"""
        self.rate_limit()
        
        # Load ballpark links if not cached
        ballpark_links = self.load_mlb_ballpark_links()
        
        # Try to match stadium name to ballpark
        best_match = None
        best_score = 0
        
        # Clean stadium name for matching
        clean_stadium = stadium_name.lower().replace('stadium', '').replace('park', '').replace('field', '').strip()
        
        for ballpark_name, ballpark_url in ballpark_links.items():
            # Simple scoring based on word matches
            ballpark_clean = ballpark_name.lower().replace('stadium', '').replace('park', '').replace('field', '').strip()
            
            # Check for exact matches or partial matches
            score = 0
            if clean_stadium in ballpark_clean or ballpark_clean in clean_stadium:
                score = 2
            else:
                # Check individual words
                stadium_words = clean_stadium.split()
                ballpark_words = ballpark_clean.split()
                common_words = set(stadium_words) & set(ballpark_words)
                score = len(common_words)
            
            if score > best_score:
                best_score = score
                best_match = ballpark_url
        
        if not best_match:
            print(f"    No matching ballpark found for {stadium_name}")
            return []
        
        try:
            print(f"    Fetching from: {best_match}")
            response = self.session.get(best_match, timeout=15)
            response.raise_for_status()
            
            # Extract image URLs from the ballpark page
            image_urls = []
            
            # Look for various image patterns
            patterns = [
                r'<img[^>]+src=\"([^\"]+)\"[^>]*>',
                r'background-image:\s*url\([\'"]([^\'"]+)[\'"]\)',
                r'data-src=\"([^\"]+)\"'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, response.text, re.IGNORECASE)
                for match in matches:
                    if not match.startswith('http'):
                        match = urljoin(best_match, match)
                    
                    # Filter for actual stadium images
                    if any(ext in match.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                        # Skip small icons and ads
                        if not any(skip in match.lower() for skip in ['icon', 'logo', 'thumb', 'ad', 'banner', 'social']):
                            if len(match) > 30:  # Reasonable URL length
                                image_urls.append(match)
            
            # Remove duplicates and return
            unique_urls = list(dict.fromkeys(image_urls))
            print(f"    Found {len(unique_urls)} image URLs from ballparksofbaseball.com")
            return unique_urls[:8]  # Return top 8
            
        except Exception as e:
            print(f"    Error fetching from ballparksofbaseball.com: {e}")
            return []
    
    def load_nfl_stadium_data(self) -> Dict[str, Dict]:
        """Load NFL stadium data from Stadium Scene TV and Stadiums of Pro Football"""
        if self.nfl_stadium_cache:
            return self.nfl_stadium_cache
            
        print("  🏈 Loading NFL stadium directory from specialized sources...")
        self.rate_limit()
        
        stadium_data = {}
        
        # Load from Stadium Scene TV (for images)
        try:
            response = self.session.get('https://stadiumscene.tv/leagues.php?sport=nfl', timeout=15)
            response.raise_for_status()
            
            # Extract stadium information and images
            # Look for stadium entries with images
            stadium_pattern = r'<div[^>]*class="[^"]*stadium[^"]*"[^>]*>.*?<img[^>]+src="([^"]+)"[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>'
            matches = re.findall(stadium_pattern, response.text, re.IGNORECASE | re.DOTALL)
            
            for img_src, stadium_link, stadium_name in matches:
                if not img_src.startswith('http'):
                    img_src = urljoin('https://stadiumscene.tv/', img_src)
                    
                clean_name = stadium_name.strip()
                stadium_data[clean_name] = {
                    'image_url': img_src,
                    'detail_url': urljoin('https://stadiumscene.tv/', stadium_link) if not stadium_link.startswith('http') else stadium_link,
                    'source': 'stadiumscene'
                }
            
            # Alternative pattern for simpler layout
            if not stadium_data:
                img_pattern = r'<img[^>]+src="([^"]+)"[^>]*alt="([^"]*)"[^>]*>'
                img_matches = re.findall(img_pattern, response.text, re.IGNORECASE)
                
                for img_src, alt_text in img_matches:
                    if 'stadium' in alt_text.lower() or 'field' in alt_text.lower():
                        if not img_src.startswith('http'):
                            img_src = urljoin('https://stadiumscene.tv/', img_src)
                        
                        clean_name = alt_text.strip()
                        if clean_name and len(clean_name) > 3:
                            stadium_data[clean_name] = {
                                'image_url': img_src,
                                'source': 'stadiumscene'
                            }
            
        except Exception as e:
            print(f"    Error loading from Stadium Scene TV: {e}")
        
        # Load additional data from Stadiums of Pro Football (for metadata)
        try:
            response = self.session.get('https://www.stadiumsofprofootball.com/comparisons/', timeout=15)
            response.raise_for_status()
            
            # Extract stadium details
            # Look for table rows with stadium information
            table_pattern = r'<tr[^>]*>.*?<td[^>]*>([^<]+)</td>.*?<td[^>]*>([^<]+)</td>.*?<td[^>]*>([^<]+)</td>.*?</tr>'
            matches = re.findall(table_pattern, response.text, re.IGNORECASE | re.DOTALL)
            
            for match in matches:
                if len(match) >= 3:
                    # Try to identify stadium name, team, and other info
                    for item in match:
                        item = item.strip()
                        if 'stadium' in item.lower() or 'field' in item.lower() or 'dome' in item.lower():
                            # Found a stadium name
                            if item not in stadium_data:
                                stadium_data[item] = {'source': 'stadiumsofprofootball'}
                            
                            # Add metadata if available
                            for detail in match:
                                detail = detail.strip()
                                if re.match(r'\d{2,3},\d{3}', detail):  # Capacity
                                    stadium_data[item]['capacity'] = detail
                                elif re.match(r'\d{4}', detail):  # Year
                                    stadium_data[item]['opened'] = detail
                                elif any(surface in detail.lower() for surface in ['grass', 'turf', 'artificial']):
                                    stadium_data[item]['surface'] = detail
            
        except Exception as e:
            print(f"    Error loading from Stadiums of Pro Football: {e}")
        
        self.nfl_stadium_cache = stadium_data
        print(f"    Found {len(stadium_data)} NFL stadiums")
        return stadium_data
    
    def search_nfl_stadium_images(self, stadium_name: str, teams: List[Dict]) -> List[str]:
        """Search for NFL stadium images using specialized NFL sources"""
        self.rate_limit()
        
        # Load NFL stadium data if not cached
        stadium_data = self.load_nfl_stadium_data()
        
        # Try to match stadium name
        best_match = None
        best_score = 0
        
        clean_stadium = stadium_name.lower().replace('stadium', '').replace('field', '').replace('dome', '').strip()
        
        for data_name, data_info in stadium_data.items():
            data_clean = data_name.lower().replace('stadium', '').replace('field', '').replace('dome', '').strip()
            
            # Scoring based on word matches
            score = 0
            if clean_stadium in data_clean or data_clean in clean_stadium:
                score = 3
            else:
                stadium_words = set(clean_stadium.split())
                data_words = set(data_clean.split())
                common_words = stadium_words & data_words
                score = len(common_words)
            
            if score > best_score:
                best_score = score
                best_match = data_info
        
        image_urls = []
        
        if best_match and 'image_url' in best_match:
            print(f"    Found matching NFL stadium data")
            image_urls.append(best_match['image_url'])
            
            # If there's a detail URL, try to get more images from it
            if 'detail_url' in best_match:
                try:
                    detail_response = self.session.get(best_match['detail_url'], timeout=10)
                    if detail_response.status_code == 200:
                        detail_images = re.findall(r'<img[^>]+src="([^"]+)"[^>]*>', detail_response.text, re.IGNORECASE)
                        for img in detail_images:
                            if not img.startswith('http'):
                                img = urljoin(best_match['detail_url'], img)
                            
                            if any(ext in img.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                                if not any(skip in img.lower() for skip in ['logo', 'icon', 'thumb', 'ad']):
                                    image_urls.append(img)
                except:
                    pass  # Skip failed detail pages
        
        # Fallback: try direct Stadium Scene TV search
        if not image_urls:
            try:
                # Try searching Stadium Scene TV directly
                search_terms = [clean_stadium] + [team['real_team_name'] for team in teams]
                for term in search_terms[:2]:  # Try first two terms
                    search_url = f"https://stadiumscene.tv/search.php?q={quote_plus(term)}"
                    search_response = self.session.get(search_url, timeout=10)
                    
                    if search_response.status_code == 200:
                        search_images = re.findall(r'<img[^>]+src="([^"]+)"[^>]*>', search_response.text, re.IGNORECASE)
                        for img in search_images:
                            if not img.startswith('http'):
                                img = urljoin('https://stadiumscene.tv/', img)
                            
                            if any(ext in img.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                                if 'stadium' in img.lower() or len(img) > 50:
                                    image_urls.append(img)
                                    
            except Exception as e:
                print(f"    Stadium Scene TV search error: {e}")
        
        unique_urls = list(dict.fromkeys(image_urls))
        print(f"    Found {len(unique_urls)} image URLs from NFL sources")
        return unique_urls[:6]  # Return top 6
    
    def load_nhl_arena_data(self) -> Dict[str, Dict]:
        """Load NHL arena data from Pro Hockey Arenas and Stadium Scene TV"""
        if self.nhl_arena_cache:
            return self.nhl_arena_cache
            
        print("  🏒 Loading NHL arena directory from specialized sources...")
        self.rate_limit()
        
        arena_data = {}
        
        # Load from Pro Hockey Arenas (for metadata)
        try:
            response = self.session.get('https://prohockeyarenas.com', timeout=15)
            response.raise_for_status()
            
            # Extract arena information
            # Look for arena names and associated data
            arena_patterns = [
                r'<td[^>]*>([^<]*(?:Arena|Center|Garden)[^<]*)</td>',
                r'<h[1-6][^>]*>([^<]*(?:Arena|Center|Garden)[^<]*)</h[1-6]>',
                r'>([A-Z][a-zA-Z\s]+ (?:Arena|Center|Garden))<'
            ]
            
            found_arenas = set()
            for pattern in arena_patterns:
                matches = re.findall(pattern, response.text, re.IGNORECASE)
                for match in matches:
                    arena_name = match.strip()
                    if len(arena_name) > 5 and arena_name not in ['Arena', 'Center', 'Garden']:
                        found_arenas.add(arena_name)
            
            # For each arena, try to extract associated metadata
            for arena in found_arenas:
                arena_data[arena] = {'source': 'prohockeyarenas'}
                
                # Look for capacity and year data near the arena name
                arena_context_pattern = rf'.*{re.escape(arena)}.*?(\d{{2,3}},\d{{3}}).*?(\d{{4}})'
                context_match = re.search(arena_context_pattern, response.text, re.IGNORECASE | re.DOTALL)
                
                if context_match:
                    capacity = context_match.group(1)
                    year = context_match.group(2)
                    
                    # Validate year is reasonable (1900-2030)
                    if 1900 <= int(year) <= 2030:
                        arena_data[arena]['capacity'] = capacity
                        arena_data[arena]['opened'] = year
            
        except Exception as e:
            print(f"    Error loading from Pro Hockey Arenas: {e}")
        
        # Load from Stadium Scene TV NHL (for images)
        try:
            response = self.session.get('https://stadiumscene.tv/leagues.php?sport=nhl', timeout=15)
            response.raise_for_status()
            
            # Extract arena information and images
            # Look for arena entries with images
            stadium_pattern = r'<div[^>]*class="[^"]*arena[^"]*"[^>]*>.*?<img[^>]+src="([^"]+)"[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>'
            matches = re.findall(stadium_pattern, response.text, re.IGNORECASE | re.DOTALL)
            
            for img_src, arena_link, arena_name in matches:
                if not img_src.startswith('http'):
                    img_src = urljoin('https://stadiumscene.tv/', img_src)
                    
                clean_name = arena_name.strip()
                if clean_name not in arena_data:
                    arena_data[clean_name] = {}
                
                arena_data[clean_name]['image_url'] = img_src
                arena_data[clean_name]['detail_url'] = urljoin('https://stadiumscene.tv/', arena_link) if not arena_link.startswith('http') else arena_link
                arena_data[clean_name]['source'] = 'stadiumscene'
            
            # Alternative: look for any images that might be arenas
            if not any('image_url' in data for data in arena_data.values()):
                img_pattern = r'<img[^>]+src="([^"]+)"[^>]*alt="([^"]*)"[^>]*>'
                img_matches = re.findall(img_pattern, response.text, re.IGNORECASE)
                
                for img_src, alt_text in img_matches:
                    if any(keyword in alt_text.lower() for keyword in ['arena', 'center', 'garden', 'rink']):
                        if not img_src.startswith('http'):
                            img_src = urljoin('https://stadiumscene.tv/', img_src)
                        
                        clean_name = alt_text.strip()
                        if clean_name and len(clean_name) > 3:
                            if clean_name not in arena_data:
                                arena_data[clean_name] = {}
                            arena_data[clean_name]['image_url'] = img_src
                            arena_data[clean_name]['source'] = 'stadiumscene'
            
        except Exception as e:
            print(f"    Error loading from Stadium Scene TV NHL: {e}")
        
        self.nhl_arena_cache = arena_data
        print(f"    Found {len(arena_data)} NHL arenas")
        return arena_data
    
    def search_nhl_arena_images(self, stadium_name: str, teams: List[Dict]) -> List[str]:
        """Search for NHL arena images using specialized NHL sources"""
        self.rate_limit()
        
        # Load NHL arena data if not cached
        arena_data = self.load_nhl_arena_data()
        
        # Try to match arena name
        best_match = None
        best_score = 0
        
        clean_stadium = stadium_name.lower().replace('arena', '').replace('center', '').replace('garden', '').strip()
        
        for data_name, data_info in arena_data.items():
            data_clean = data_name.lower().replace('arena', '').replace('center', '').replace('garden', '').strip()
            
            # Scoring based on word matches
            score = 0
            if clean_stadium in data_clean or data_clean in clean_stadium:
                score = 3
            else:
                stadium_words = set(clean_stadium.split())
                data_words = set(data_clean.split())
                common_words = stadium_words & data_words
                score = len(common_words)
            
            if score > best_score:
                best_score = score
                best_match = data_info
        
        image_urls = []
        
        if best_match and 'image_url' in best_match:
            print(f"    Found matching NHL arena data")
            image_urls.append(best_match['image_url'])
            
            # If there's a detail URL, try to get more images from it
            if 'detail_url' in best_match:
                try:
                    detail_response = self.session.get(best_match['detail_url'], timeout=10)
                    if detail_response.status_code == 200:
                        detail_images = re.findall(r'<img[^>]+src="([^"]+)"[^>]*>', detail_response.text, re.IGNORECASE)
                        for img in detail_images:
                            if not img.startswith('http'):
                                img = urljoin(best_match['detail_url'], img)
                            
                            if any(ext in img.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                                if not any(skip in img.lower() for skip in ['logo', 'icon', 'thumb', 'ad']):
                                    image_urls.append(img)
                except:
                    pass  # Skip failed detail pages
        
        # Fallback: try direct Stadium Scene TV search
        if not image_urls:
            try:
                # Try searching Stadium Scene TV directly
                search_terms = [clean_stadium] + [team['real_team_name'] for team in teams]
                for term in search_terms[:2]:  # Try first two terms
                    search_url = f"https://stadiumscene.tv/search.php?q={quote_plus(term)}"
                    search_response = self.session.get(search_url, timeout=10)
                    
                    if search_response.status_code == 200:
                        search_images = re.findall(r'<img[^>]+src="([^"]+)"[^>]*>', search_response.text, re.IGNORECASE)
                        for img in search_images:
                            if not img.startswith('http'):
                                img = urljoin('https://stadiumscene.tv/', img)
                            
                            if any(ext in img.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                                if any(keyword in img.lower() for keyword in ['arena', 'center', 'garden', 'rink']):
                                    image_urls.append(img)
                                    
            except Exception as e:
                print(f"    Stadium Scene TV NHL search error: {e}")
        
        unique_urls = list(dict.fromkeys(image_urls))
        print(f"    Found {len(unique_urls)} image URLs from NHL sources")
        return unique_urls[:6]  # Return top 6
    
    def search_nba_arena_images(self, stadium_name: str, teams: List[Dict]) -> List[str]:
        """Search for NBA arena images using official NBA sources"""
        self.rate_limit()
        
        try:
            # Use NBA.com arena page
            response = self.session.get('https://www.nba.com/news/all-30-nba-arenas-by-team', timeout=15)
            response.raise_for_status()
            
            # Look for images related to this arena
            image_urls = []
            
            # Extract all image URLs from the page
            img_patterns = [
                r'<img[^>]+src=\"([^\"]+)\"[^>]*>',
                r'background-image:\s*url\([\'"]([^\'"]+)[\'"]\)',
                r'data-src=\"([^\"]+)\"'
            ]
            
            for pattern in img_patterns:
                matches = re.findall(pattern, response.text, re.IGNORECASE)
                for match in matches:
                    if not match.startswith('http'):
                        if match.startswith('//'):
                            match = 'https:' + match
                        else:
                            match = urljoin('https://www.nba.com/', match)
                    
                    # Filter for arena images
                    if any(ext in match.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                        # Skip small icons and irrelevant images
                        if not any(skip in match.lower() for skip in ['icon', 'logo', 'thumb', 'player', 'headshot']):
                            if 'arena' in match.lower() or 'stadium' in match.lower() or len(match) > 50:
                                image_urls.append(match)
            
            # Also try team-specific searches
            for team in teams:
                team_name = team['real_team_name'].lower().replace(' ', '-')
                team_url = f"https://www.nba.com/{team_name}/"
                
                try:
                    team_response = self.session.get(team_url, timeout=10)
                    if team_response.status_code == 200:
                        team_images = re.findall(r'<img[^>]+src=\"([^\"]+)\"[^>]*>', team_response.text, re.IGNORECASE)
                        for img in team_images:
                            if not img.startswith('http'):
                                if img.startswith('//'):
                                    img = 'https:' + img
                                else:
                                    img = urljoin(team_url, img)
                            
                            if any(ext in img.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                                if 'arena' in img.lower() or 'stadium' in img.lower():
                                    image_urls.append(img)
                except:
                    continue  # Skip failed team pages
            
            unique_urls = list(dict.fromkeys(image_urls))
            print(f"    Found {len(unique_urls)} image URLs from NBA sources")
            return unique_urls[:6]  # Return top 6
            
        except Exception as e:
            print(f"    Error fetching from NBA sources: {e}")
            return []
    
    def search_wikimedia_commons(self, stadium_name: str, city: str = "") -> List[str]:
        """Search Wikimedia Commons for stadium images (fallback method)"""
        self.rate_limit()
        
        search_terms = [stadium_name]
        if city:
            search_terms.append(city)
        search_terms.append("stadium")
        
        query = " ".join(search_terms)
        
        try:
            api_url = "https://commons.wikimedia.org/w/api.php"
            params = {
                'action': 'query',
                'format': 'json',
                'list': 'search',
                'srsearch': query,
                'srnamespace': 6,  # File namespace
                'srlimit': 5
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
            
            return image_urls
            
        except Exception as e:
            print(f"    Wikimedia Commons error: {e}")
            return []
    
    def download_and_process_image(self, url: str, output_path: str) -> bool:
        """Download and process image from URL"""
        self.rate_limit()
        
        try:
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
            
            # Validate image dimensions
            if img.width < 400 or img.height < 250:
                print(f"    Too small: {img.width}x{img.height}")
                return False
            
            # Check aspect ratio
            aspect_ratio = img.width / img.height
            if aspect_ratio < 0.6:  # Very tall images are likely not stadium exteriors
                print(f"    Bad aspect ratio: {aspect_ratio:.2f}")
                return False
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Resize if too large
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
        """Fetch the best image for a stadium using specialized sources"""
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
        
        # Use specialized sources based on league
        if league.lower() == 'mlb':
            print("  🏟️ Checking ballparksofbaseball.com...")
            mlb_urls = self.search_mlb_ballpark_images(stadium_name, teams)
            if mlb_urls:
                print(f"     Found {len(mlb_urls)} MLB-specific images")
                all_image_urls.extend(mlb_urls)
        
        elif league.lower() == 'nba':
            print("  🏀 Checking NBA official sources...")
            nba_urls = self.search_nba_arena_images(stadium_name, teams)
            if nba_urls:
                print(f"     Found {len(nba_urls)} NBA-specific images")
                all_image_urls.extend(nba_urls)
        
        elif league.lower() == 'nfl':
            print("  🏈 Checking NFL specialized sources...")
            nfl_urls = self.search_nfl_stadium_images(stadium_name, teams)
            if nfl_urls:
                print(f"     Found {len(nfl_urls)} NFL-specific images")
                all_image_urls.extend(nfl_urls)
        
        # Fallback to Wikimedia Commons for all leagues
        print("  📚 Checking Wikimedia Commons...")
        wikimedia_urls = self.search_wikimedia_commons(stadium_name, city)
        if wikimedia_urls:
            print(f"     Found {len(wikimedia_urls)} Wikimedia images")
            all_image_urls.extend(wikimedia_urls)
        
        # Remove duplicates while preserving order
        unique_urls = list(dict.fromkeys(all_image_urls))
        
        if not unique_urls:
            print(f"  ❌ No images found for {stadium_name}")
            return False
        
        print(f"  📊 Total unique URLs found: {len(unique_urls)}")
        
        # Try to download the best image
        for i, url in enumerate(unique_urls[:10]):  # Try up to 10 images
            print(f"  Trying image {i+1}/{min(10, len(unique_urls))}: {url[:60]}...")
            
            if self.download_and_process_image(url, output_path):
                print(f"  ✅ Successfully downloaded image for {stadium_name}")
                return True
        
        print(f"  ❌ Failed to download any images for {stadium_name}")
        return False
    
    def run(self, specific_league: str = None):
        """Main execution method"""
        print("🏟️  Specialized Stadium Image Fetcher")
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
        
        # Filter by specific league if requested
        if specific_league:
            stadium_mapping = {k: v for k, v in stadium_mapping.items() if v['league'].lower() == specific_league.lower()}
            print(f"   Filtering for {specific_league.upper()} league only")
        
        total_stadiums = len(stadium_mapping)
        print(f"   Found {total_stadiums} unique stadiums to process")
        
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
    import sys
    
    fetcher = SpecializedStadiumImageFetcher()
    
    # Allow running for specific league
    if len(sys.argv) > 1:
        league = sys.argv[1].lower()
        fetcher.run(specific_league=league)
    else:
        fetcher.run()