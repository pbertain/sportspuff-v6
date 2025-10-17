#!/usr/bin/env python3
"""
Logo mapping utility for sportspuff-v6
Maps team names to their corresponding logo files
"""

import os
import re
from pathlib import Path

def normalize_team_name(team_name):
    """Normalize team name for logo matching"""
    # Convert to lowercase and replace spaces/special chars with underscores
    normalized = team_name.lower()
    normalized = re.sub(r'[^a-z0-9]', '_', normalized)
    normalized = re.sub(r'_+', '_', normalized)  # Remove multiple underscores
    normalized = normalized.strip('_')  # Remove leading/trailing underscores
    return normalized

def find_logo_file(team_name, league):
    """Find the logo file for a team"""
    logos_dir = Path('logos')
    league_dir = logos_dir / league.lower()
    
    if not league_dir.exists():
        return None
    
    # Try exact match first
    normalized_name = normalize_team_name(team_name)
    logo_filename = f"{normalized_name}_logo.png"
    logo_path = league_dir / logo_filename
    
    if logo_path.exists():
        return str(logo_path)
    
    # Try variations
    variations = [
        f"{normalized_name}.png",
        f"{normalized_name}_logo.svg.png",
        f"{normalized_name}.svg.png"
    ]
    
    for variation in variations:
        logo_path = league_dir / variation
        if logo_path.exists():
            return str(logo_path)
    
    # Try partial matches
    for logo_file in league_dir.glob("*.png"):
        logo_name = logo_file.stem.lower()
        if normalized_name in logo_name or logo_name in normalized_name:
            return str(logo_file)
    
    return None

def create_logo_mapping():
    """Create a mapping of teams to their logo files"""
    import pandas as pd
    
    # Read teams data
    df = pd.read_csv('leagues-and-teams.csv')
    
    logo_mapping = {}
    missing_logos = []
    
    for _, team in df.iterrows():
        team_name = team['real_team_name']
        league = team['league'].lower()
        
        logo_path = find_logo_file(team_name, league)
        
        if logo_path:
            logo_mapping[team['team_id']] = {
                'team_name': team_name,
                'league': league,
                'logo_path': logo_path,
                'logo_url': f"/static/{logo_path}"
            }
        else:
            missing_logos.append({
                'team_id': team['team_id'],
                'team_name': team_name,
                'league': league
            })
    
    return logo_mapping, missing_logos

def main():
    """Main function to create logo mapping"""
    print("🔍 Creating logo mapping...")
    
    logo_mapping, missing_logos = create_logo_mapping()
    
    print(f"✅ Found logos for {len(logo_mapping)} teams")
    print(f"❌ Missing logos for {len(missing_logos)} teams")
    
    if missing_logos:
        print("\nMissing logos:")
        for team in missing_logos[:10]:  # Show first 10
            print(f"  {team['team_name']} ({team['league'].upper()})")
        if len(missing_logos) > 10:
            print(f"  ... and {len(missing_logos) - 10} more")
    
    # Save mapping to JSON
    import json
    with open('logo_mapping.json', 'w') as f:
        json.dump(logo_mapping, f, indent=2)
    
    print(f"\n💾 Logo mapping saved to logo_mapping.json")
    
    return logo_mapping, missing_logos

if __name__ == "__main__":
    main()
