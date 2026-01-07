import sqlite3
import json

conn = sqlite3.connect('C:/Users/kjhgf/.acm2/acm2.db')
c = conn.cursor()
c.execute('SELECT results_summary FROM runs WHERE id = ?', ('de75a641-64d9-415c-8243-08f1c9f9411f',))
row = c.fetchone()
data = json.loads(row[0])
te = data.get('timeline_events', [])

print('Source doc IDs in run:')
sdr = data.get('source_doc_results', {})
for sdr_id in sdr.keys():
    print(f'  {sdr_id}')

print('\nTimeline event doc_id samples:')
for t in te[:6]:
    details = t.get('details') or {}
    doc_id = details.get('doc_id', 'NO DOC_ID')
    if doc_id != 'NO DOC_ID':
        # Extract source_doc_id from doc_id
        extracted = doc_id.split('.')[0] if '.' in doc_id else doc_id
        print(f'  {t.get("phase"):15} - doc_id: {doc_id[:60]}... -> extracted: {extracted}')

conn.close()
