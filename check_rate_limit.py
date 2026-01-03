#!/usr/bin/env python3
"""Check session rate limit info from database."""
import sqlite3
import sys

session_id = sys.argv[1] if len(sys.argv) > 1 else "c32179b9-f42b-455c-a443-a68d9910e055"
db_path = "/home/sherajx1fe/Documents/sherajdev github/autonomous-coding/generations/learn2autocode/chattwelve.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, request_count, request_window_start FROM sessions WHERE id = ?", (session_id,))
row = cursor.fetchone()
if row:
    print(f"Session ID: {row[0][:16]}...")
    print(f"Request Count: {row[1]}")
    print(f"Window Start: {row[2]}")
else:
    print(f"Session not found: {session_id}")
conn.close()
