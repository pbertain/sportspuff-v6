#!/usr/bin/env python3
"""
Analyze Excel file and extract data for sportspuff-v6
"""

import pandas as pd
import sys
import os

def analyze_excel(file_path):
    """Analyze Excel file and extract data"""
    try:
        # Read Excel file
        excel_file = pd.ExcelFile(file_path)
        print(f"Excel file: {file_path}")
        print(f"Sheet names: {excel_file.sheet_names}")
        
        # Process leagues-and-teams sheet
        if 'leagues-and-teams' in excel_file.sheet_names:
            teams_df = pd.read_excel(file_path, sheet_name='leagues-and-teams')
            print(f"\nLeagues and Teams sheet:")
            print(f"Shape: {teams_df.shape}")
            print(f"Columns: {list(teams_df.columns)}")
            print(f"First few rows:")
            print(teams_df.head())
            
            # Save as CSV
            teams_df.to_csv('leagues-and-teams.csv', index=False)
            print(f"Saved leagues-and-teams.csv with {len(teams_df)} rows")
        
        # Process final_stadiums sheet
        if 'final_stadiums' in excel_file.sheet_names:
            stadiums_df = pd.read_excel(file_path, sheet_name='final_stadiums')
            print(f"\nFinal Stadiums sheet:")
            print(f"Shape: {stadiums_df.shape}")
            print(f"Columns: {list(stadiums_df.columns)}")
            print(f"First few rows:")
            print(stadiums_df.head())
            
            # Save as CSV
            stadiums_df.to_csv('final_stadiums.csv', index=False)
            print(f"Saved final_stadiums.csv with {len(stadiums_df)} rows")
        
        print("\n✅ Excel analysis complete!")
        
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    excel_file = "team-logo-image-downloads.xlsx"
    
    if not os.path.exists(excel_file):
        print(f"Error: {excel_file} not found")
        sys.exit(1)
    
    analyze_excel(excel_file)
