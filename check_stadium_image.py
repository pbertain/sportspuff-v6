#!/usr/bin/env python3
"""Check stadium image_name in database"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'sportspuff_v6'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD')
)

cursor = conn.cursor()
cursor.execute("SELECT stadium_id, full_stadium_name, image_name FROM stadiums WHERE stadium_id = 107")
result = cursor.fetchone()
if result:
    print(f"Stadium ID: {result[0]}")
    print(f"Name: {result[1]}")
    print(f"Image Name: {result[2]}")
else:
    print("Stadium not found")

cursor.close()
conn.close()

