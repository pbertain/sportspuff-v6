#!/usr/bin/env python3
"""Debug what stadium data is being returned"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'sportspuff_v6'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD')
)

cursor = conn.cursor(cursor_factory=RealDictCursor)
cursor.execute("SELECT * FROM stadiums WHERE stadium_id = 107")
stadium = cursor.fetchone()

if stadium:
    print("Stadium data:")
    print(f"  stadium_id: {stadium.get('stadium_id')}")
    print(f"  full_stadium_name: {stadium.get('full_stadium_name')}")
    print(f"  image_name: {repr(stadium.get('image_name'))}")
    print(f"  image_name type: {type(stadium.get('image_name'))}")
    print(f"  image_name bool: {bool(stadium.get('image_name'))}")
    print(f"  image (old): {repr(stadium.get('image'))}")
    print("\nAll columns:")
    for key in sorted(stadium.keys()):
        print(f"  {key}: {repr(stadium[key])}")
else:
    print("Stadium not found")

cursor.close()
conn.close()

