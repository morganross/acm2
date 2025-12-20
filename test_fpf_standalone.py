"""Self-contained FPF API test."""
import subprocess
import sys
import time
import os

# Start server in background
env = os.environ.copy()
env['PYTHONPATH'] = 'c:/dev/silky/api_cost_multiplier/acm2'

server_proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8003'],
    cwd='c:/dev/silky/api_cost_multiplier/acm2',
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

time.sleep(4)

# Test the API
import requests
url = 'http://127.0.0.1:8003/api/v1/generation/generate'
data = {
    'query': 'What is 2+2? Answer briefly.',
    'generator': 'fpf',
    'provider': 'openai',
    'model': 'gpt-4o',
}

try:
    resp = requests.post(url, json=data, timeout=10)
    print(f'Create task: {resp.status_code}')
    result = resp.json()
    task_id = result['task_id']
    print(f'Task ID: {task_id}')
    
    # Poll for completion
    status_url = f'http://127.0.0.1:8003/api/v1/generation/status/{task_id}'
    for i in range(30):
        resp = requests.get(status_url, timeout=10)
        data = resp.json()
        status = data['status']
        print(f'[{i}] Status: {status}')
        
        if status == 'completed':
            print('SUCCESS!')
            content = data.get('content', '')
            print(f'Content: {content[:200] if content else "(empty)"}')
            break
        elif status == 'failed':
            err = data.get('error', 'Unknown')
            print(f'FAILED: {err}')
            break
        time.sleep(1)
except Exception as e:
    print(f'Error: {e}')
finally:
    server_proc.terminate()
    print('Server terminated')
