import sqlite3
import os
import requests
import json
import time

# Configuration
API_URL = "http://localhost:8002/api/v1"
DB_PATH = os.path.expanduser('~/.acm2/acm2.db')

def get_default_preset_id():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("SELECT id FROM presets WHERE name = 'Default Preset'")
        row = c.fetchone()
        return row[0] if row else None
    finally:
        conn.close()

def create_run(preset_id):
    payload = {
        "name": f"Test Run Post-Combine Fix {int(time.time())}",
        "preset_id": preset_id
    }
    response = requests.post(f"{API_URL}/runs", json=payload)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to create run: {response.text}")
        return None

def check_run_config_db(run_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("SELECT config FROM runs WHERE id = ?", (run_id,))
        row = c.fetchone()
        if row and row[0]:
            config = json.loads(row[0])
            return config.get('post_combine_top_n')
        return None
    finally:
        conn.close()

def start_run(run_id):
    response = requests.post(f"{API_URL}/runs/{run_id}/start")
    if response.status_code == 200:
        print(f"Run {run_id} started successfully.")
        return True
    else:
        print(f"Failed to start run: {response.text}")
        return False

def monitor_run(run_id):
    print(f"Monitoring run {run_id}...")
    while True:
        response = requests.get(f"{API_URL}/runs/{run_id}")
        if response.status_code == 200:
            data = response.json()
            status = data.get('status')
            print(f"Status: {status}")
            
            if status in ['completed', 'failed', 'cancelled']:
                return data
            
            time.sleep(5)
        else:
            print(f"Failed to get run status: {response.text}")
            break

def main():
    preset_id = get_default_preset_id()
    if not preset_id:
        print("Default Preset not found in DB.")
        return

    print(f"Found Default Preset ID: {preset_id}")

    run_data = create_run(preset_id)
    if not run_data:
        return

    run_id = run_data['id']
    print(f"Created Run ID: {run_id}")

    # Verify config in DB
    pctn = check_run_config_db(run_id)
    print(f"post_combine_top_n in DB config: {pctn}")

    if pctn != 5:
        print("ERROR: post_combine_top_n is not 5! Fix failed.")
        return

    # Start run
    if start_run(run_id):
        final_data = monitor_run(run_id)
        
        # Check results
        if final_data:
            summary = final_data.get('results_summary', {})
            # The API might return summary as dict, DB stores as JSON string
            # If via API, it's already parsed
            
            print("\nChecking for Post-Combine Results...")
            # Note: The API response model might structure this differently than DB JSON
            # Let's check the raw keys
            print("Summary Keys:", summary.keys())
            
            if 'post_combine_eval_results' in summary and summary['post_combine_eval_results']:
                print("SUCCESS: Post-Combine Eval Results Found!")
                print(json.dumps(summary['post_combine_eval_results'], indent=2))
            elif 'post_combine_eval' in summary and summary['post_combine_eval']:
                 print("SUCCESS: Post-Combine Eval Found (alt key)!")
                 print(json.dumps(summary['post_combine_eval'], indent=2))
            else:
                print("FAILURE: Post-Combine Eval Results NOT found.")

if __name__ == "__main__":
    main()
