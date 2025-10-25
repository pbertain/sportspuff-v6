#!/usr/bin/env python3
"""
Improved logo color extraction - better algorithm to capture vibrant team colors
"""

import pandas as pd
import requests
from PIL import Image
import numpy as np
from collections import Counter
import io
import time

def get_dominant_colors_improved(image_url, num_colors=3):
    """Extract dominant colors with improved algorithm to capture vibrant team colors"""
    try:
        # Download image
        response = requests.get(image_url, timeout=15)
        response.raise_for_status()
        
        # Open image with PIL
        image = Image.open(io.BytesIO(response.content))
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize image to speed up processing
        image = image.resize((200, 200))
        
        # Convert to numpy array
        img_array = np.array(image)
        
        # Reshape to list of pixels
        pixels = img_array.reshape(-1, 3)
        
        # Improved filtering - be less aggressive
        # Remove pure white and very light colors (likely background)
        brightness = np.sum(pixels, axis=1)
        saturation = np.max(pixels, axis=1) - np.min(pixels, axis=1)
        
        # Keep pixels that are not pure white/very light AND have some color saturation
        mask = (brightness < 750) & (saturation > 20)
        filtered_pixels = pixels[mask]
        
        # If we filtered out too much, be more lenient
        if len(filtered_pixels) < len(pixels) * 0.1:  # Less than 10% of pixels
            mask = brightness < 800  # Just remove very bright pixels
            filtered_pixels = pixels[mask]
        
        # If still too few pixels, use all pixels
        if len(filtered_pixels) < len(pixels) * 0.05:  # Less than 5% of pixels
            filtered_pixels = pixels
        
        # Less aggressive quantization to preserve color variety
        quantized_pixels = (filtered_pixels // 16) * 16
        
        # Count color frequencies
        color_counts = Counter(map(tuple, quantized_pixels))
        
        # Get most common colors
        most_common = color_counts.most_common(num_colors * 2)  # Get more options
        
        # Filter out colors that are too similar to each other
        final_colors = []
        for color, count in most_common:
            if len(final_colors) >= num_colors:
                break
                
            # Check if this color is too similar to already selected colors
            too_similar = False
            for existing_color in final_colors:
                # Calculate color distance
                distance = np.sqrt(sum((a - b) ** 2 for a, b in zip(color, existing_color)))
                if distance < 50:  # Colors are too similar
                    too_similar = True
                    break
            
            if not too_similar:
                final_colors.append(color)
        
        # Convert to hex
        hex_colors = []
        for color in final_colors:
            hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
            hex_colors.append(hex_color)
        
        # Ensure we have exactly num_colors
        while len(hex_colors) < num_colors:
            hex_colors.append('#FFFFFF')  # Add white as fallback
        
        return hex_colors[:num_colors]
        
    except Exception as e:
        print(f"Error processing {image_url}: {e}")
        return None

def reanalyze_team_colors():
    """Re-analyze team colors with improved algorithm"""
    print("Re-analyzing team colors with improved algorithm...")
    
    # Read CSV file
    try:
        df = pd.read_csv('info-teams.csv', encoding='utf-8-sig')
        print(f"Loaded CSV with {len(df)} teams")
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return False
    
    # Focus on MLS, WNBA, and IPL teams
    leagues_to_analyze = [2, 6, 7]  # MLS, WNBA, IPL
    teams_to_analyze = df[df['league_id'].isin(leagues_to_analyze)]
    
    print(f"Re-analyzing {len(teams_to_analyze)} teams from MLS, WNBA, and IPL...")
    
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
        
        print(f"Re-analyzing {team_name} ({league_name.upper()})...")
        
        # Extract dominant colors with improved algorithm
        colors = get_dominant_colors_improved(logo_url)
        
        if colors:
            updated_colors[team_name] = colors
            print(f"  Found colors: {colors[0]}, {colors[1]}, {colors[2]}")
        else:
            print(f"  Failed to extract colors")
        
        # Be respectful to the server
        time.sleep(0.3)
    
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
        print(f"\nSuccessfully updated CSV with improved logo-based colors")
        return True
    except Exception as e:
        print(f"Error saving CSV: {e}")
        return False

def main():
    """Main function"""
    print("Starting improved logo color analysis...")
    
    if reanalyze_team_colors():
        print("\nImproved logo color analysis completed successfully!")
        print("Colors should now be more vibrant and representative of team logos.")
    else:
        print("\nImproved logo color analysis failed!")

if __name__ == "__main__":
    main()
