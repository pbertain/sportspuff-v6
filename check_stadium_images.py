#!/usr/bin/env python3
"""Check and fix stadium image_name values"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'sportspuff_v6'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD')
)

cursor = conn.cursor(cursor_factory=RealDictCursor)

# Check specific stadiums
cursor.execute("""
    SELECT stadium_id, full_stadium_name, stadium_name, image_name 
    FROM stadiums 
    WHERE stadium_name IN ('dodger_stadium', 'comerica_park')
    ORDER BY stadium_name
""")
results = cursor.fetchall()

print("Current database values:")
for row in results:
    print(f"  ID: {row['stadium_id']}, Name: {row['full_stadium_name']}, Image: {row['image_name']}")

# Check how many stadiums have image_name
cursor.execute("SELECT COUNT(*) as count FROM stadiums WHERE image_name IS NOT NULL AND image_name != ''")
with_images = cursor.fetchone()['count']
cursor.execute("SELECT COUNT(*) as count FROM stadiums")
total = cursor.fetchone()['count']

print(f"\nTotal stadiums: {total}")
print(f"Stadiums with image_name: {with_images}")
print(f"Stadiums without image_name: {total - with_images}")

# Read CSV to see what should be there
print("\nReading CSV...")
df = pd.read_csv('info-stadiums.csv', encoding='utf-8-sig')
stadiums_with_images = df[df['image_name'].notna() & (df['image_name'] != '')]
print(f"CSV has {len(stadiums_with_images)} stadiums with image_name")

# Check a few examples from CSV
print("\nSample from CSV:")
for idx, row in stadiums_with_images.head(10).iterrows():
    print(f"  {row['stadium_name']}: {row['image_name']}")

cursor.close()
conn.close()

