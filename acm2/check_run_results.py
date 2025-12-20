import sqlite3
import os
import json

db_path = os.path.expanduser('~/.acm2/acm2.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

run_id = 'b7fc39f2-a7b3-45a4-a814-8a4a17c7b65f'

try:
    c.execute("SELECT results_summary FROM runs WHERE id = ?", (run_id,))
    row = c.fetchone()
    if row and row[0]:
        summary = json.loads(row[0])
        print("Results Summary Keys:", summary.keys())
        
        if 'post_combine_eval_results' in summary:
            print("\nPost-Combine Eval Results Found!")
            pc_results = summary['post_combine_eval_results']
            if pc_results:
                print(f"  Winner: {pc_results.get('winner_doc_id')}")
                print(f"  Total Comparisons: {pc_results.get('total_comparisons')}")
            else:
                print("  Post-combine results are null/empty.")
        else:
            print("\nPost-Combine Eval Results NOT found in summary.")
            
        if 'pairwise_results' in summary:
             print("\nPairwise Results Found!")
             pw_results = summary['pairwise_results']
             if pw_results:
                 print(f"  Winner: {pw_results.get('winner_doc_id')}")
                 print(f"  Total Comparisons: {pw_results.get('total_comparisons')}")
    else:
        print("Run not found or no results summary.")

except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
