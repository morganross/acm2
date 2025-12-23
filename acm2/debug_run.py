import sqlite3
import json

conn = sqlite3.connect('C:/Users/kjhgf/.acm2/acm2.db')

# Check the run's timeline events - what phases actually executed?
r = conn.execute("SELECT results_summary FROM runs WHERE id = ?", ['f4e4c977-4c35-4289-a182-5ba79b6c0c9b']).fetchone()
summary = json.loads(r[0]) if r[0] else {}
timeline = summary.get('timeline_events', [])

print('=== TIMELINE EVENTS ===')
for evt in timeline:
    phase = evt.get('phase', '')
    event_type = evt.get('event_type', '')
    desc = evt.get('description', '')[:50]
    print(f"  {phase:15} | {event_type:15} | {desc}")

print()
print('=== KEY RESULTS ===')
print('winner:', summary.get('winner'))
print('combined_doc_id:', summary.get('combined_doc_id'))
print('post_combine_eval:', summary.get('post_combine_eval'))
