#!/usr/bin/env python3
"""Update Default Preset to enable post-combine evaluation."""

import sqlite3

db_path = "C:/Users/kjhgf/.acm2/acm2.db"

conn = sqlite3.connect(db_path)
c = conn.cursor()

# Update Default Preset to set post_combine_top_n = 5
c.execute("""
UPDATE presets 
SET post_combine_top_n = 5 
WHERE name = 'Default Preset'
""")

conn.commit()
print(f"✅ Updated {c.rowcount} preset(s)")

# Verify the change
c.execute("SELECT name, post_combine_top_n FROM presets WHERE name = 'Default Preset'")
result = c.fetchone()
print(f"Default Preset: post_combine_top_n = {result[1]}")

conn.close()
