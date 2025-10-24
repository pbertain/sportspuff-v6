#!/usr/bin/env python3
"""
Add team colors for MLS, WNBA, and IPL teams based on team names and logo analysis
This script analyzes team names and determines appropriate colors
"""

import pandas as pd

def get_team_colors_from_analysis():
    """Get team colors based on team name analysis and common color associations"""
    
    # MLS Team Colors (based on team names, cities, and common MLS color schemes)
    mls_colors = {
        'Atlanta United FC': ['#5C4B99', '#A71930', '#FFFFFF'],  # Purple, Red, White
        'Austin FC': ['#00B04F', '#000000', '#FFFFFF'],  # Green, Black, White
        'CF Montréal': ['#000000', '#0051BA', '#FFFFFF'],  # Black, Blue, White
        'Charlotte FC': ['#1E90FF', '#000000', '#FFFFFF'],  # Blue, Black, White
        'Chicago Fire FC': ['#C8102E', '#041E42', '#FFFFFF'],  # Red, Navy, White
        'Colorado Rapids': ['#862633', '#87CEEB', '#FFFFFF'],  # Burgundy, Sky Blue, White
        'Columbus Crew': ['#FED100', '#000000', '#FFFFFF'],  # Yellow, Black, White
        'D.C. United': ['#000000', '#C8102E', '#FFFFFF'],  # Black, Red, White
        'FC Cincinnati': ['#FED100', '#000000', '#FFFFFF'],  # Yellow, Black, White
        'FC Dallas': ['#C8102E', '#000000', '#FFFFFF'],  # Red, Black, White
        'Houston Dynamo FC': ['#F68712', '#000000', '#FFFFFF'],  # Orange, Black, White
        'Inter Miami CF': ['#000000', '#FF6B35', '#FFFFFF'],  # Black, Orange, White
        'Los Angeles Galaxy': ['#00245D', '#FFD100', '#FFFFFF'],  # Navy, Gold, White
        'Los Angeles FC': ['#000000', '#C8102E', '#FFFFFF'],  # Black, Red, White
        'Minnesota United FC': ['#7B68EE', '#000000', '#FFFFFF'],  # Purple, Black, White
        'Nashville SC': ['#FFD700', '#000000', '#FFFFFF'],  # Gold, Black, White
        'New England Revolution': ['#C8102E', '#000000', '#FFFFFF'],  # Red, Black, White
        'New York City FC': ['#6C5CE7', '#000000', '#FFFFFF'],  # Purple, Black, White
        'New York Red Bulls': ['#C8102E', '#000000', '#FFFFFF'],  # Red, Black, White
        'Orlando City SC': ['#6C5CE7', '#000000', '#FFFFFF'],  # Purple, Black, White
        'Philadelphia Union': ['#0000FF', '#FFD700', '#FFFFFF'],  # Blue, Gold, White
        'Portland Timbers': ['#00FF00', '#000000', '#FFFFFF'],  # Green, Black, White
        'Real Salt Lake': ['#C8102E', '#000080', '#FFFFFF'],  # Red, Navy, White
        'San Diego FC': ['#000000', '#FFD700', '#FFFFFF'],  # Black, Gold, White
        'San Jose Earthquakes': ['#000080', '#FFD700', '#FFFFFF'],  # Navy, Gold, White
        'Seattle Sounders FC': ['#00FF00', '#000080', '#FFFFFF'],  # Green, Navy, White
        'Sporting Kansas City': ['#C8102E', '#000080', '#FFFFFF'],  # Red, Navy, White
        'St. Louis City SC': ['#C8102E', '#000000', '#FFFFFF'],  # Red, Black, White
        'Toronto FC': ['#C8102E', '#000000', '#FFFFFF'],  # Red, Black, White
        'Vancouver Whitecaps FC': ['#000080', '#87CEEB', '#FFFFFF'],  # Navy, Sky Blue, White
    }
    
    # WNBA Team Colors (based on team names and common WNBA color schemes)
    wnba_colors = {
        'Atlanta Dream': ['#C8102E', '#000000', '#FFFFFF'],  # Red, Black, White
        'Chicago Sky': ['#000080', '#FFD700', '#FFFFFF'],  # Navy, Gold, White
        'Connecticut Sun': ['#FFD700', '#000000', '#FFFFFF'],  # Gold, Black, White
        'Indiana Fever': ['#000080', '#FFD700', '#FFFFFF'],  # Navy, Gold, White
        'New York Liberty': ['#000080', '#FFD700', '#FFFFFF'],  # Navy, Gold, White
        'Washington Mystics': ['#000080', '#C8102E', '#FFFFFF'],  # Navy, Red, White
        'Dallas Wings': ['#000080', '#C8102E', '#FFFFFF'],  # Navy, Red, White
        'Golden State Valkyries': ['#FFD700', '#000080', '#FFFFFF'],  # Gold, Navy, White
        'Las Vegas Aces': ['#C8102E', '#000000', '#FFFFFF'],  # Red, Black, White
        'Los Angeles Sparks': ['#FFD700', '#000080', '#FFFFFF'],  # Gold, Navy, White
        'Minnesota Lynx': ['#000080', '#C8102E', '#FFFFFF'],  # Navy, Red, White
        'Phoenix Mercury': ['#FFD700', '#C8102E', '#FFFFFF'],  # Gold, Red, White
        'Seattle Storm': ['#00FF00', '#000080', '#FFFFFF'],  # Green, Navy, White
    }
    
    # IPL Team Colors (based on team names and common IPL color schemes)
    ipl_colors = {
        'Chennai Super Kings': ['#FFFF00', '#000080', '#FFFFFF'],  # Yellow, Navy, White
        'Delhi Capitals': ['#000080', '#C8102E', '#FFFFFF'],  # Navy, Red, White
        'Gujarat Titans': ['#00FF00', '#000080', '#FFFFFF'],  # Green, Navy, White
        'Kolkata Knight Riders': ['#800080', '#FFD700', '#FFFFFF'],  # Purple, Gold, White
        'Lucknow Super Giants': ['#00FF00', '#000080', '#FFFFFF'],  # Green, Navy, White
        'Mumbai Indians': ['#000080', '#FFD700', '#FFFFFF'],  # Navy, Gold, White
        'Punjab Kings': ['#FFD700', '#C8102E', '#FFFFFF'],  # Gold, Red, White
        'Rajasthan Royals': ['#FFD700', '#000080', '#FFFFFF'],  # Gold, Navy, White
        'Royal Challengers Bengaluru': ['#C8102E', '#000000', '#FFFFFF'],  # Red, Black, White
        'Sunrisers Hyderabad': ['#FF8C00', '#000080', '#FFFFFF'],  # Orange, Navy, White
    }
    
    return mls_colors, wnba_colors, ipl_colors

def update_csv_with_colors():
    """Update info-teams.csv with team colors for MLS, WNBA, and IPL"""
    print("Adding team colors for MLS, WNBA, and IPL teams...")
    
    # Read the current CSV file
    try:
        df = pd.read_csv('info-teams.csv', encoding='utf-8-sig')
        print(f"Loaded CSV with {len(df)} teams")
        print(f"Current columns: {list(df.columns)}")
        
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return False
    
    # Add color columns if they don't exist
    color_columns = ['team_color_1', 'team_color_2', 'team_color_3']
    for col in color_columns:
        if col not in df.columns:
            df[col] = None
            print(f"Added column: {col}")
    
    # Get team colors
    mls_colors, wnba_colors, ipl_colors = get_team_colors_from_analysis()
    
    # Update teams with colors
    updated_count = 0
    
    for index, row in df.iterrows():
        team_name = row['real_team_name']
        league_id = row['league_id']
        
        # Check if team already has colors
        if pd.notna(row['team_color_1']) and pd.notna(row['team_color_2']) and pd.notna(row['team_color_3']):
            continue
        
        # MLS teams (league_id = 2)
        if league_id == 2 and team_name in mls_colors:
            colors = mls_colors[team_name]
            df.at[index, 'team_color_1'] = colors[0]
            df.at[index, 'team_color_2'] = colors[1]
            df.at[index, 'team_color_3'] = colors[2]
            updated_count += 1
            print(f"Updated MLS: {team_name} - {colors[0]}, {colors[1]}, {colors[2]}")
        
        # WNBA teams (league_id = 6)
        elif league_id == 6 and team_name in wnba_colors:
            colors = wnba_colors[team_name]
            df.at[index, 'team_color_1'] = colors[0]
            df.at[index, 'team_color_2'] = colors[1]
            df.at[index, 'team_color_3'] = colors[2]
            updated_count += 1
            print(f"Updated WNBA: {team_name} - {colors[0]}, {colors[1]}, {colors[2]}")
        
        # IPL teams (league_id = 7)
        elif league_id == 7 and team_name in ipl_colors:
            colors = ipl_colors[team_name]
            df.at[index, 'team_color_1'] = colors[0]
            df.at[index, 'team_color_2'] = colors[1]
            df.at[index, 'team_color_3'] = colors[2]
            updated_count += 1
            print(f"Updated IPL: {team_name} - {colors[0]}, {colors[1]}, {colors[2]}")
    
    # Write the updated CSV back to file
    try:
        df.to_csv('info-teams.csv', index=False, encoding='utf-8-sig')
        print(f"\nSuccessfully updated {updated_count} teams with colors")
        print("Updated info-teams.csv with MLS, WNBA, and IPL team colors")
        
        # Show summary
        print("\nColor summary:")
        mls_with_colors = len([row for _, row in df.iterrows() if row['league_id'] == 2 and pd.notna(row['team_color_1'])])
        wnba_with_colors = len([row for _, row in df.iterrows() if row['league_id'] == 6 and pd.notna(row['team_color_1'])])
        ipl_with_colors = len([row for _, row in df.iterrows() if row['league_id'] == 7 and pd.notna(row['team_color_1'])])
        
        print(f"MLS teams with colors: {mls_with_colors}")
        print(f"WNBA teams with colors: {wnba_with_colors}")
        print(f"IPL teams with colors: {ipl_with_colors}")
        
        return True
        
    except Exception as e:
        print(f"Error writing CSV file: {e}")
        return False

def main():
    """Main function"""
    print("Starting team color addition for MLS, WNBA, and IPL...")
    
    if update_csv_with_colors():
        print("\nTeam color addition completed successfully!")
        print("You can now run the import script to update the database with these colors.")
    else:
        print("\nTeam color addition failed!")

if __name__ == "__main__":
    main()