#!/usr/bin/env python3
"""
Extract dominant colors from team logos
This script downloads team logos and analyzes them to extract the top 3 most prevalent colors
"""

import pandas as pd
import requests
from PIL import Image
import numpy as np
from collections import Counter
import io
import time

def get_dominant_colors(image_url, num_colors=3):
    """Extract dominant colors from an image URL"""
    try:
        # Download image
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
        
        # Open image with PIL
        image = Image.open(io.BytesIO(response.content))
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize image to speed up processing
        image = image.resize((150, 150))
        
        # Convert to numpy array
        img_array = np.array(image)
        
        # Reshape to list of pixels
        pixels = img_array.reshape(-1, 3)
        
        # Remove white/very light colors (background)
        # Filter out pixels that are too light (likely background)
        brightness = np.sum(pixels, axis=1)
        mask = brightness < 700  # Filter out very bright pixels
        filtered_pixels = pixels[mask]
        
        if len(filtered_pixels) == 0:
            # If all pixels were filtered out, use original pixels
            filtered_pixels = pixels
        
        # Quantize colors to reduce noise
        quantized_pixels = (filtered_pixels // 32) * 32
        
        # Count color frequencies
        color_counts = Counter(map(tuple, quantized_pixels))
        
        # Get most common colors
        most_common = color_counts.most_common(num_colors)
        
        # Convert to hex
        hex_colors = []
        for color, count in most_common:
            hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            hex_colors.append(hex_color)
        
        return hex_colors
        
    except Exception as e:
        print(f"Error processing {image_url}: {e}")
        return None

def analyze_team_logos():
    """Analyze logos for IPL, WNBA, and MLS teams"""
    print("Analyzing team logos to extract dominant colors...")
    
    # Read CSV file
    try:
        df = pd.read_csv('info-teams.csv', encoding='utf-8-sig')
        print(f"Loaded CSV with {len(df)} teams")
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return False
    
    # Focus on teams that need better color analysis
    leagues_to_analyze = [2, 6, 7]  # MLS, WNBA, IPL
    teams_to_analyze = df[df['league_id'].isin(leagues_to_analyze)]
    
    print(f"Analyzing {len(teams_to_analyze)} teams from MLS, WNBA, and IPL...")
    
    updated_colors = {}
    
    for _, team in teams_to_analyze.iterrows():
        team_name = team['real_team_name']
        league_id = team['league_id']
        logo_filename = team['logo_filename']
        
        if pd.isna(logo_filename):
            continue
        
        # Determine league name for URL
        league_names = {2: 'mls', 6: 'wnba', 7: 'ipl'}
        league_name = league_names.get(league_id)
        
        if not league_name:
            continue
        
        # Construct logo URL
        logo_url = f"https://www.splitsp.lat/logos/{league_name}/{logo_filename}"
        
        print(f"Analyzing {team_name} ({league_name.upper()})...")
        
        # Extract dominant colors
        colors = get_dominant_colors(logo_url)
        
        if colors:
            # Ensure we have exactly 3 colors
            while len(colors) < 3:
                colors.append('#FFFFFF')  # Add white as fallback
            
            colors = colors[:3]  # Take only first 3
            updated_colors[team_name] = colors
            
            print(f"  Found colors: {colors[0]}, {colors[1]}, {colors[2]}")
        else:
            print(f"  Failed to extract colors")
        
        # Be respectful to the server
        time.sleep(0.5)
    
    # Update CSV with new colors
    print(f"\nUpdating CSV with {len(updated_colors)} teams...")
    
    for team_name, colors in updated_colors.items():
        mask = df['real_team_name'] == team_name
        if mask.any():
            df.loc[mask, 'team_color_1'] = colors[0]
            df.loc[mask, 'team_color_2'] = colors[1]
            df.loc[mask, 'team_color_3'] = colors[2]
            print(f"Updated {team_name}: {colors[0]}, {colors[1]}, {colors[2]}")
    
    # Save updated CSV
    try:
        df.to_csv('info-teams.csv', index=False, encoding='utf-8-sig')
        print(f"\nSuccessfully updated CSV with logo-based colors")
        return True
    except Exception as e:
        print(f"Error saving CSV: {e}")
        return False

def main():
    """Main function"""
    print("Starting logo color analysis...")
    
    if analyze_team_logos():
        print("\nLogo color analysis completed successfully!")
        print("Colors are now based on actual logo analysis.")
    else:
        print("\nLogo color analysis failed!")

if __name__ == "__main__":
    main()
