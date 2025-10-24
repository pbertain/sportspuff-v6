#!/usr/bin/env python3
"""
Fix Montréal encoding issue in CSV file
"""

import pandas as pd

def fix_montreal_encoding():
    """Fix the Montréal encoding issue in the CSV file"""
    print("Fixing Montréal encoding issue...")
    
    try:
        # Read CSV with latin-1 encoding to handle the corrupted characters
        df = pd.read_csv('info-teams.csv', encoding='latin-1')
        print(f"Loaded CSV with {len(df)} teams")
        
        # Find and fix the Montréal team
        montreal_mask = df['real_team_name'].str.contains('Montr', na=False)
        montreal_teams = df[montreal_mask]
        
        print("Found Montréal teams:")
        for _, team in montreal_teams.iterrows():
            print(f"  Team ID {team['team_id']}: {team['real_team_name']} - {team['logo_filename']}")
        
        # Fix CF Montréal specifically
        cf_montreal_mask = df['team_id'] == 1021
        if cf_montreal_mask.any():
            df.loc[cf_montreal_mask, 'real_team_name'] = 'CF Montréal'
            df.loc[cf_montreal_mask, 'logo_filename'] = 'cf_montréal_logo.png'
            print("Fixed CF Montréal team name and logo filename")
        
        # Write back with utf-8-sig encoding
        df.to_csv('info-teams.csv', index=False, encoding='utf-8-sig')
        print("Successfully updated CSV file with proper encoding")
        
        # Verify the fix
        print("\nVerification:")
        cf_montreal_team = df[df['team_id'] == 1021]
        if not cf_montreal_team.empty:
            team = cf_montreal_team.iloc[0]
            print(f"  Team ID {team['team_id']}: {team['real_team_name']} - {team['logo_filename']}")
        
        return True
        
    except Exception as e:
        print(f"Error fixing Montréal encoding: {e}")
        return False

def main():
    """Main function"""
    print("Starting Montréal encoding fix...")
    
    if fix_montreal_encoding():
        print("\nMontréal encoding fix completed successfully!")
    else:
        print("\nMontréal encoding fix failed!")

if __name__ == "__main__":
    main()
