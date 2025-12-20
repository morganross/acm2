import sqlite3
import json

conn = sqlite3.connect('C:/Users/kjhgf/.acm2/acm2.db')
cursor = conn.cursor()

run_id = '6c9494cb-77b2-41ec-87c5-0e6aec032494'

# Query runs table for results_summary
cursor.execute("SELECT results_summary FROM runs WHERE id = ?", (run_id,))
row = cursor.fetchone()

if row and row[0]:
    results = json.loads(row[0])
    
    # Get generated docs (non-combine only)
    generated_docs = [d for d in results.get('generated_docs', []) if d.get('generator') != 'combine']
    print("=== GENERATED DOCS (FPF only) ===")
    for doc in generated_docs:
        print(f"  {doc['id']} | model: {doc['model']}")
    
    # Get evaluator list
    evaluators = results.get('evaluator_list', [])
    print(f"\n=== EVALUATORS ===")
    print(f"  {evaluators}")
    
    # Get pre_combine_evals_detailed
    pre_combine = results.get('pre_combine_evals_detailed', {})
    print(f"\n=== PRE_COMBINE_EVALS_DETAILED ===")
    print(json.dumps(pre_combine, indent=2))
    
    # Build expected matrix
    print(f"\n=== EXPECTED SINGLE EVAL MATRIX (2 docs x 2 judges = 4 cells) ===")
    for doc in generated_docs:
        doc_id = doc['id']
        doc_evals = pre_combine.get(doc_id, {})
        for evaluator in evaluators:
            evals = doc_evals.get('evaluations', [])
            found = None
            for e in evals:
                if e.get('judge_model') == evaluator:
                    found = e
                    break
            if found:
                scores = {s['criterion']: s['score'] for s in found.get('scores', [])}
                avg = found.get('average_score', 'N/A')
                print(f"  {doc_id} | Judge: {evaluator} | Scores: {scores} | Avg: {avg}")
            else:
                print(f"  {doc_id} | Judge: {evaluator} | Scores: MISSING | Avg: MISSING")

conn.close()
