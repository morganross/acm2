#!/usr/bin/env python3
import sqlite3
import json

conn = sqlite3.connect('C:/Users/kjhgf/.acm2/acm2.db')
c = conn.cursor()
c.execute('SELECT results_summary FROM runs WHERE id LIKE ?', ('2abe4071%',))
row = c.fetchone()
data = json.loads(row[0]) if row and row[0] else {}
timeline = data.get('timeline_events', [])

print("=== Timeline Events ===")
for i, evt in enumerate(timeline):
    phase = evt.get('phase', 'N/A')
    event_type = evt.get('event_type', 'N/A')
    print(f"{i+1}. Phase: {phase}, Type: {event_type}")
    
    if 'pairwise' in str(evt).lower() or 'combine' in str(evt).lower():
        details = evt.get('details', {})
        print(f"   Details keys: {list(details.keys())}")
        if 'comparisons' in details:
            print(f"   Comparisons count: {len(details['comparisons'])}")
        if 'rankings' in details:
            print(f"   Rankings count: {len(details['rankings'])}")

conn.close()
