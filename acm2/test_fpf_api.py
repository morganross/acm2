"""Quick test script for FPF API endpoint."""
import requests
import time
import sys

def test_fpf_generation():
    # Start a new generation
    url = 'http://127.0.0.1:8002/api/v1/generation/generate'
    data = {
        'query': 'What is 2+2? Answer briefly.',
        'generator': 'fpf',
        'provider': 'openai',
        'model': 'gpt-4o',
        'document_content': 'Math test',
        'reasoning_effort': 'low',
        'max_completion_tokens': 500,
    }

    print("Starting FPF generation...")
    resp = requests.post(url, json=data, timeout=10)
    print(f"Response: {resp.status_code}")
    result = resp.json()
    task_id = result['task_id']
    print(f"Task ID: {task_id}")

    # Poll for completion
    status_url = f'http://127.0.0.1:8002/api/v1/generation/status/{task_id}'
    for i in range(30):
        resp = requests.get(status_url, timeout=10)
        data = resp.json()
        status = data['status']
        progress = data.get('progress', 0)
        print(f"[{i}] Status: {status}, Progress: {progress:.0%}")
        
        if status == 'completed':
            content = data.get('content', '')
            print(f"\n=== COMPLETED ===")
            print(f"Content ({len(content)} chars):")
            print(content[:500] if content else "(empty)")
            print(f"\nCost: ${data.get('cost_usd', 0):.4f}")
            print(f"Duration: {data.get('duration_seconds', 0):.1f}s")
            return True
        elif status == 'failed':
            print(f"\n=== FAILED ===")
            print(f"Error: {data.get('error', 'Unknown')}")
            return False
        
        time.sleep(1)
    
    print("Timeout waiting for completion")
    return False

if __name__ == "__main__":
    success = test_fpf_generation()
    sys.exit(0 if success else 1)
