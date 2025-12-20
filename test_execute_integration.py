# Test script to verify ACM 2.0 Execute page functionality
# This script creates a test preset and verifies the API integration

import urllib.request
import urllib.parse
import json
import time

BASE_URL = "http://127.0.0.1:8001/api/v1"

def make_request(method, url, data=None):
    """Make HTTP request using urllib"""
    try:
        if data:
            data = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header('Content-Type', 'application/json')
        else:
            req = urllib.request.Request(url, method=method)

        with urllib.request.urlopen(req) as response:
            return response.getcode(), json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            error_data = json.loads(e.read().decode('utf-8'))
            return e.code, error_data
        except:
            return e.code, {'detail': str(e)}
    except Exception as e:
        return None, {'detail': str(e)}

def test_preset_creation():
    """Create a test preset via API"""
    import time
    preset_data = {
        "name": f"Test Preset {int(time.time())}",
        "description": "Test preset for Execute page verification",
        "documents": ["Document 1", "Document 2"],
        "generators": ["gptr"],
        "models": [
            {"provider": "openai", "model": "gpt-4", "temperature": 0.7, "max_tokens": 1000},
            {"provider": "anthropic", "model": "claude-3", "temperature": 0.7, "max_tokens": 1000}
        ],
        "iterations": 2,
        "gptr_settings": {
            "report_type": "research_report",
            "report_source": "web",
            "tone": "objective",
            "max_search_results": 5,
            "total_words": 1000,
            "fast_llm": "gpt-4",
            "smart_llm": "claude-3"
        },
        "evaluation": {
            "enabled": True,
            "criteria": ["accuracy", "relevance"],
            "eval_model": "gpt-4"
        },
        "pairwise": {
            "enabled": True,
            "judge_model": "gpt-4"
        }
    }

    status, response = make_request('POST', f"{BASE_URL}/presets", preset_data)
    if status == 200:
        preset = response
        print(f"✓ Created preset: {preset['name']} (ID: {preset['id']})")
        return preset['id']
    else:
        print(f"✗ Failed to create preset: {status} - {response}")
        return None

def test_preset_listing():
    """Test listing presets"""
    status, response = make_request('GET', f"{BASE_URL}/presets?page=1&page_size=10")
    if status == 200:
        data = response
        print(f"✓ Listed {len(data['items'])} presets")
        return data['items']
    else:
        print(f"✗ Failed to list presets: {status} - {response}")
        return []

def test_preset_execution(preset_id):
    """Test executing a preset"""
    status, response = make_request('POST', f"{BASE_URL}/presets/{preset_id}/execute")
    if status == 200:
        exec_data = response
        run_id = exec_data.get('run_id')
        if run_id:
            print(f"✓ Started execution, run ID: {run_id}")
            return run_id
        else:
            print(f"✗ No run_id in response: {exec_data}")
            return None
    else:
        print(f"✗ Failed to execute preset: {status} - {response}")
        return None

def test_run_status(run_id):
    """Test checking run status"""
    status, response = make_request('GET', f"{BASE_URL}/runs/{run_id}")
    if status == 200:
        run_data = response
        run_status = run_data.get('status')
        print(f"✓ Run status: {run_status}")
        return run_status
    else:
        print(f"✗ Failed to get run status: {status} - {response}")
        return None

def main():
    print("🧪 Testing ACM 2.0 Execute Page Integration")
    print("=" * 50)

    # Test preset creation
    preset_id = test_preset_creation()
    if not preset_id:
        return

    # Test preset listing
    presets = test_preset_listing()
    if not presets:
        return

    # Verify our preset is in the list
    our_preset = next((p for p in presets if p['id'] == preset_id), None)
    if our_preset:
        print(f"✓ Our preset found in list: {our_preset['name']}")
        print(f"  - Documents: {our_preset['document_count']}")
        print(f"  - Models: {our_preset['model_count']}")
        print(f"  - Iterations: {our_preset['iterations']}")
        print(f"  - Generators: {our_preset['generators']}")
    else:
        print("✗ Our preset not found in list")
        return

    # Test execution (this will likely fail without proper GPTR setup, but tests the API)
    print("\n⚠️  Note: Execution may fail without proper GPTR configuration")
    run_id = test_preset_execution(preset_id)

    if run_id:
        # Check status a few times
        for i in range(3):
            status = test_run_status(run_id)
            if status in ['completed', 'failed', 'cancelled']:
                break
            time.sleep(2)

    print("\n✅ Execute page integration test completed!")
    print("The Execute page should now load presets from the backend and allow execution.")

if __name__ == "__main__":
    main()