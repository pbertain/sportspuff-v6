# Stadium Image Fetcher

A Python script to automatically download high-quality stadium images for professional sports teams from MLB, MLS, NBA, NFL, NHL, WNBA, and IPL leagues.

## Overview

This script fetches the best looking stadium images for each team and stores them in an organized directory structure:
```
stadiums/{lower_case_league}/{lower_case_stadium_name}_img.png
```

## Features

- ✅ Supports 7 major sports leagues: MLB, MLS, NBA, NFL, NHL, WNBA, IPL
- ✅ Processes 177 unique stadiums across all leagues
- ✅ Automatic image quality filtering (minimum 400x300 pixels)
- ✅ Rate limiting to avoid overwhelming servers
- ✅ Fallback search engines (Bing → Google)
- ✅ Progress tracking and detailed logging
- ✅ Duplicate detection and skipping
- ✅ Comprehensive test suite

## Stadium Coverage

| League | Stadiums | Teams |
|--------|----------|-------|
| IPL    | 10       | 10    |
| MLB    | 30       | 30    |
| MLS    | 30       | 30    |
| NBA    | 30       | 30    |
| NFL    | 30       | 32    |
| NHL    | 32       | 32    |
| WNBA   | 15       | 13    |
| **Total** | **177** | **179** |

## Requirements

- Python 3.6 or higher
- Required Python packages (install via `pip install -r requirements.txt`):
  - `requests>=2.25.1`
  - `Pillow>=8.0.0`

## Installation

1. Ensure you have the required CSV data files:
   - `info-teams.csv`
   - `info-stadiums.csv` 
   - `info-leagues.csv`

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### 1. Run Tests (Recommended)

First, run the test suite to verify everything is working:

```bash
python3 test_stadium_fetcher.py
```

Expected output:
```
🏟️  Stadium Image Fetcher - Test Suite
==================================================
✅ CSV Files test PASSED!
✅ Dependencies test PASSED!
✅ Data Loading test PASSED!
✅ Directory Creation test PASSED!
🎉 ALL TESTS PASSED!
```

### 2. Run the Main Script

```bash
python3 fetch_stadium_images.py
```

The script will:
1. Load team and stadium data from CSV files
2. Create the directory structure
3. Search for and download images for each stadium
4. Provide progress updates and final statistics

## Output Structure

Images are saved in the following structure:
```
stadiums/
├── mlb/
│   ├── yankee_img.png
│   ├── fenway_park_img.png
│   └── ...
├── nba/
│   ├── madison_square_garden_img.png
│   ├── td_garden_img.png
│   └── ...
├── nfl/
│   ├── lambeau_img.png
│   ├── soldier_img.png
│   └── ...
├── nhl/
├── mls/
├── wnba/
└── ipl/
```

## Sample Output

```
🏟️  Stadium Image Fetcher
==================================================
📊 Loading data from CSV files...
   Loaded 179 teams, 151 stadiums, 7 leagues
🗺️  Creating stadium mappings...
   Found 177 unique stadiums across target leagues

📈 Stadiums per league:
   IPL: 10 stadiums
   MLB: 30 stadiums
   MLS: 30 stadiums
   NBA: 30 stadiums
   NFL: 30 stadiums
   NHL: 32 stadiums
   WNBA: 15 stadiums

🚀 Starting image download process...
==================================================

[1/177] MLB: Yankee Stadium
🔍 Searching for images of Yankee Stadium (the_bronx)
  Found 8 potential images
  Trying image 1/5: https://example.com/yankee-stadium.jpg...
✓ Downloaded: yankee_img.png
  ✅ Successfully downloaded image for Yankee Stadium
     Teams: New York Yankees

...

🏁 DOWNLOAD COMPLETE
==================================================
Total stadiums processed: 177
✅ Successful downloads: 165
❌ Failed downloads: 12
📁 Images saved to: /path/to/stadiums/
```

## Features & Options

### Image Quality Filtering
- Minimum resolution: 400x300 pixels
- Automatic format conversion to PNG
- Filters out icons and low-quality images

### Rate Limiting
- 1-second delay between requests
- Respectful of server resources

### Search Strategy
1. **Primary**: Bing Image Search
2. **Fallback**: Google Image Search
3. **Query terms**: Stadium name + city + "stadium exterior aerial view"

### Error Handling
- Graceful handling of network timeouts
- Automatic retries with different image sources
- Detailed error logging

## Troubleshooting

### Common Issues

1. **"command not found: python"**
   - Use `python3` instead of `python`

2. **Missing dependencies**
   ```bash
   pip install requests Pillow
   ```

3. **CSV files not found**
   - Ensure `info-teams.csv`, `info-stadiums.csv`, and `info-leagues.csv` are in the same directory

4. **Network errors**
   - Check internet connection
   - Some images may be temporarily unavailable
   - The script will continue with other stadiums

### Performance Notes

- Total runtime: Approximately 3-5 minutes for all 177 stadiums
- Network-dependent (download speeds vary)
- Images are typically 100KB - 2MB each

## File Naming Convention

Stadium names are cleaned for filenames:
- Converted to lowercase
- Spaces replaced with underscores
- Special characters removed
- Common suffixes removed (stadium, arena, park, etc.)
- Appended with `_img.png`

Examples:
- "Yankee Stadium" → `yankee_img.png`
- "Madison Square Garden" → `madison_square_garden_img.png`
- "AT&T Stadium" → `at&t_img.png`

## License

This script is for educational and research purposes. Please respect the terms of service of image sources and consider the copyright of downloaded images.

## Support

For issues or questions:
1. Run the test suite first: `python3 test_stadium_fetcher.py`
2. Check the troubleshooting section above
3. Verify all CSV files are present and properly formatted