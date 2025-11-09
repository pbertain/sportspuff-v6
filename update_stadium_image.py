#!/usr/bin/env python3
"""Update stadium image_name for American Family Field"""

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

# Update American Family Field (stadium_id 107)
image_name = '/static/images/stadiums/american_family_field.png'
cursor.execute("""
    UPDATE stadiums 
    SET image_name = %s 
    WHERE stadium_id = 107
""", (image_name,))

conn.commit()

# Verify the update
cursor.execute("SELECT stadium_id, full_stadium_name, image_name FROM stadiums WHERE stadium_id = 107")
result = cursor.fetchone()
if result:
    print(f"Updated Stadium ID: {result[0]}")
    print(f"Name: {result[1]}")
    print(f"Image Name: {result[2]}")

cursor.close()
conn.close()

