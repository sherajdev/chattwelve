#!/usr/bin/env python3
"""
Test session expiry by creating an expired session in the database.
"""
import sqlite3
import json
from datetime import datetime, timedelta

conn = sqlite3.connect('chattwelve.db')
cursor = conn.cursor()

# Create an expired session (last_activity 2 hours ago)
session_id = "test-expired-session-12345"
two_hours_ago = (datetime.utcnow() - timedelta(hours=2)).isoformat()

# First, delete any existing test session
cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

# Insert expired session
cursor.execute(
    """
    INSERT INTO sessions (id, created_at, last_activity, context, request_count, request_window_start, metadata)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
    (session_id, two_hours_ago, two_hours_ago, "[]", 0, two_hours_ago, "{}")
)
conn.commit()

print(f"Created expired session: {session_id}")
print(f"Last activity was set to: {two_hours_ago} (2 hours ago)")
print(f"Session timeout is 60 minutes, so this session should be expired.")
conn.close()
