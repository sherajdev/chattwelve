#!/usr/bin/env python3
import sqlite3
import json

conn = sqlite3.connect('chattwelve.db')
cursor = conn.cursor()
cursor.execute("SELECT key, query_type, ttl_seconds, created_at FROM cache ORDER BY created_at DESC LIMIT 5")
rows = cursor.fetchall()
print(f"Cache entries: {len(rows)}")
for row in rows:
    print(f"  Key: {row[0][:16]}... | Type: {row[1]} | TTL: {row[2]}s | Created: {row[3]}")
conn.close()
