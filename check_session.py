#!/usr/bin/env python3
import sqlite3
import json

conn = sqlite3.connect('chattwelve.db')
cursor = conn.cursor()
cursor.execute("SELECT id, context FROM sessions ORDER BY last_activity DESC LIMIT 1")
row = cursor.fetchone()
if row:
    print(f"Session ID: {row[0]}")
    context = json.loads(row[1])
    print(f"Context entries: {len(context)}")
    for i, entry in enumerate(context):
        print(f"\n--- Entry {i+1} ---")
        print(f"Query: {entry.get('query', 'N/A')}")
        print(f"Symbols: {entry.get('symbols', [])}")
        print(f"Intent: {entry.get('intent', 'N/A')}")
conn.close()
