#!/usr/bin/env python3
"""
Re-analyze the two missing teams that failed due to connection timeouts
"""

import pandas as pd
import requests
from PIL import Image
import numpy as np
from collections import Counter
import io
import time

def get_dominant_colors(image_url, num_colors=3, max_retries=3):
    """Extract dominant colors from an image URL with retry logic"""
    for attempt in range(max_retries):
        try:
            print(f"  Attempt {attempt + 1}/{max_retries}...")
            
            # Download image with longer timeout
            response = requests.get(image_url, timeout=30)
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
            print(f"  Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"  Retrying in 2 seconds...")
                time.sleep(2)
            else:
                print(f"  All attempts failed for {image_url}")
                return None

def analyze_missing_teams():
    """Analyze the two missing teams"""
    print("Re-analyzing missing teams...")
    
    # Read CSV file
    try:
        df = pd.read_csv('info-teams.csv', encoding='utf-8-sig')
        print(f"Loaded CSV with {len(df)} teams")
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return False
    
    # The two missing teams
    missing_teams = [
        ("Las Vegas Aces", "wnba", "las_vegas_aces_logo.png"),
        ("Los Angeles FC", "mls", "los_angeles_fc_logo.png")
    ]
    
    updated_colors = {}
    
    for team_name, league_name, logo_filename in missing_teams:
        print(f"\nAnalyzing {team_name} ({league_name.upper()})...")
        
        # Construct logo URL
        logo_url = f"https://www.splitsp.lat/logos/{league_name}/{logo_filename}"
        print(f"  URL: {logo_url}")
        
        # Extract dominant colors
        colors = get_dominant_colors(logo_url)
        
        if colors:
            # Ensure we have exactly 3 colors
            while len(colors) < 3:
                colors.append('#FFFFFF')  # Add white as fallback
            
            colors = colors[:3]  # Take only first 3
            updated_colors[team_name] = colors
            
            print(f"  ✅ Found colors: {colors[0]}, {colors[1]}, {colors[2]}")
        else:
            print(f"  ❌ Failed to extract colors")
        
        # Be respectful to the server
        time.sleep(1)
    
    # Update CSV with new colors
    if updated_colors:
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
            print(f"\n✅ Successfully updated CSV with missing team colors")
            return True
        except Exception as e:
            print(f"❌ Error saving CSV: {e}")
            return False
    else:
        print("\n❌ No teams were successfully analyzed")
        return False

def main():
    """Main function"""
    print("Starting re-analysis of missing teams...")
    
    if analyze_missing_teams():
        print("\n✅ Missing team analysis completed successfully!")
    else:
        print("\n❌ Missing team analysis failed!")

if __name__ == "__main__":
    main()
