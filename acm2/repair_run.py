#!/usr/bin/env python3
"""
Repair script to reconstruct results_summary for a run that crashed during completion.
"""
import sqlite3
import json
import sys
from pathlib import Path

def repair_run(run_id: str, db_path: str = "C:/Users/kjhgf/.acm2/acm2.db"):
    """Reconstruct results_summary from database tables and log files."""
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # 1. Get existing results_summary (has timeline_events)
    c.execute("SELECT results_summary FROM runs WHERE id = ?", (run_id,))
    row = c.fetchone()
    if not row:
        print(f"Run {run_id} not found")
        return
    
    existing = json.loads(row["results_summary"]) if row["results_summary"] else {}
    timeline_events = existing.get("timeline_events", [])
    
    # 2. Extract generated documents from timeline_events
    generated_docs_data = []
    for event in timeline_events:
        if event.get("event_type") == "generation" and event.get("details"):
            details = event["details"]
            doc_id = details.get("doc_id", "")
            if doc_id:
                # Get model from event, not from parsing doc_id
                model = event.get("model", "")
                generated_docs_data.append({
                    "id": doc_id,
                    "model": model,
                    "generator": "fpf",
                    "source_doc_id": "",
                    "iteration": 1,
                })
    
    # 2b. Extract combined docs from timeline_events
    combined_docs_data = []
    for event in timeline_events:
        if event.get("event_type") == "combine" and event.get("details"):
            details = event["details"]
            combined_doc_id = details.get("combined_doc_id", "")
            if combined_doc_id:
                model = event.get("model", "")
                combined_docs_data.append({
                    "id": combined_doc_id,
                    "model": model,
                    "generator": "fpf",
                    "source_doc_id": "",
                    "iteration": 1,
                    "is_combined": True,
                })
    
    print(f"Found {len(generated_docs_data)} generated documents")
    print(f"Found {len(combined_docs_data)} combined documents")
    
    # 3. Extract evaluation data from timeline_events
    # Format: { doc_id: { judge_model: score } }
    pre_combine_evals = {}
    pre_combine_evals_detailed = {}
    
    for event in timeline_events:
        if event.get("event_type") == "single_eval" and event.get("details"):
            details = event["details"]
            doc_id = details.get("doc_id", "")
            avg_score = details.get("average_score")
            judges = event.get("model", "").split(", ")  # "openai:gpt-5-mini, google:gemini-2.5-flash"
            
            if doc_id and avg_score is not None:
                # Initialize with placeholder scores for each judge
                # We only have the average, so we use it for all judges as an approximation
                if doc_id not in pre_combine_evals:
                    pre_combine_evals[doc_id] = {}
                    for judge in judges:
                        if judge:
                            pre_combine_evals[doc_id][judge] = avg_score
    
    print(f"Found {len(pre_combine_evals)} single evaluations")
    
    # 4. Extract pairwise data from timeline_events
    pairwise_rankings = []
    pairwise_comparisons = []
    winner_doc_id = None
    
    for event in timeline_events:
        # Check various event types for pairwise data
        if event.get("phase") == "pairwise" or "pairwise" in event.get("event_type", ""):
            details = event.get("details", {})
            if "rankings" in details:
                pairwise_rankings = details["rankings"]
            if "winner" in details:
                winner_doc_id = details["winner"]
            if "winner_doc_id" in details:
                winner_doc_id = details["winner_doc_id"]
            if "comparisons" in details:
                pairwise_comparisons = details["comparisons"]
            if "total_comparisons" in details and not pairwise_comparisons:
                # We know comparisons happened but don't have details
                print(f"  Note: {details['total_comparisons']} comparisons recorded but details not in timeline")
    
    # Build rankings from generated docs if we have winner but no rankings
    if winner_doc_id and not pairwise_rankings and generated_docs_data:
        # Create simple rankings based on winner
        pairwise_rankings = []
        for i, doc in enumerate(generated_docs_data):
            is_winner = doc["id"] == winner_doc_id
            pairwise_rankings.append({
                "doc_id": doc["id"],
                "rank": 1 if is_winner else 2,
                "elo": 1200 if is_winner else 1000,
                "wins": 1 if is_winner else 0,
                "losses": 0 if is_winner else 1,
                "win_rate": 1.0 if is_winner else 0.0,
            })
        pairwise_rankings.sort(key=lambda x: x["rank"])
    
    pairwise_data = {
        "rankings": pairwise_rankings,
        "comparisons": pairwise_comparisons,
    }
    
    print(f"Found pairwise rankings: {len(pairwise_rankings)}, comparisons: {len(pairwise_comparisons)}")
    print(f"Winner: {winner_doc_id}")
    
    # 5. Check for combined docs and post-combine eval
    combined_doc_id = combined_docs_data[0]["id"] if combined_docs_data else None
    post_combine_eval = None
    
    # Look for post-combine pairwise in timeline
    for event in timeline_events:
        if event.get("phase") == "post_combine_pairwise" or "post_combine" in event.get("description", "").lower():
            details = event.get("details", {})
            if "winner" in details or "winner_doc_id" in details:
                post_combine_eval = {
                    "winner": details.get("winner") or details.get("winner_doc_id"),
                    "comparisons": details.get("comparisons", 0),
                }
    
    print(f"Combined doc: {combined_doc_id}")
    print(f"Post-combine eval: {post_combine_eval}")
    
    # 5b. Add combined docs to generated_docs (UI filters from this list)
    all_docs = generated_docs_data.copy()
    for combined_doc in combined_docs_data:
        all_docs.append(combined_doc)
    
    print(f"All docs (including combined): {len(all_docs)}")
    
    # 6. Build complete results_summary
    results_summary = {
        "winner": winner_doc_id,
        "generated_count": len(generated_docs_data),
        "eval_count": len(pre_combine_evals),
        "combined_doc_id": combined_doc_id,
        "combined_docs": combined_docs_data,
        "post_combine_eval": post_combine_eval,
        "pre_combine_evals": pre_combine_evals,
        "pre_combine_evals_detailed": {},  # Cannot reconstruct from timeline
        "pairwise_results": pairwise_data,
        "generated_docs": all_docs,  # Include combined docs for UI
        "timeline_events": timeline_events,
    }
    
    # 7. Update the database
    c.execute("""
        UPDATE runs 
        SET results_summary = ?, status = 'completed'
        WHERE id = ?
    """, (json.dumps(results_summary), run_id))
    conn.commit()
    
    print(f"\nRepaired run {run_id}")
    print(f"  - Status: completed")
    print(f"  - Generated docs: {len(generated_docs_data)}")
    print(f"  - Single evals: {len(pre_combine_evals)}")
    print(f"  - Pairwise rankings: {len(pairwise_rankings)}")
    print(f"  - Winner: {winner_doc_id}")
    
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python repair_run.py <run_id>")
        sys.exit(1)
    
    run_id = sys.argv[1]
    repair_run(run_id)
