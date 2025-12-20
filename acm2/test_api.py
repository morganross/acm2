"""Quick test script for ACM2 API"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000/api/v1"

def test_health():
    r = requests.get("http://127.0.0.1:8000/health")
    print(f"Health: {r.status_code} - {r.json()}")

def test_create_preset():
    data = {
        "name": "Test Preset",
        "description": "My first preset",
        "documents": ["doc1.md", "doc2.md"],
        "models": ["gpt-4o", "claude-3.5-sonnet"],
        "generators": ["gptr"],
        "iterations": 3,
        "evaluation_enabled": True,
        "pairwise_enabled": False
    }
    r = requests.post(f"{BASE_URL}/presets", json=data)
    print(f"Create Preset: {r.status_code}")
    if r.status_code == 200:
        preset = r.json()
        print(f"  Created: {preset['id']} - {preset['name']}")
        return preset['id']
    else:
        print(f"  Error: {r.text}")
    return None

def test_list_presets():
    r = requests.get(f"{BASE_URL}/presets")
    print(f"List Presets: {r.status_code}")
    presets = r.json()
    for p in presets:
        print(f"  - {p['id']}: {p['name']}")
    return presets

def test_create_run(preset_id: str):
    data = {
        "title": "Test Run",
        "description": "Testing the run API",
        "documents": ["doc1.md"],
        "models": ["gpt-4o"],
        "generators": ["gptr"],
        "iterations": 1,
        "evaluation_enabled": True,
        "pairwise_enabled": False
    }
    r = requests.post(f"{BASE_URL}/runs", json=data)
    print(f"Create Run: {r.status_code}")
    if r.status_code == 200:
        run = r.json()
        print(f"  Created: {run['id']} - {run['title']}")
        return run['id']
    else:
        print(f"  Error: {r.text}")
    return None

def test_list_runs():
    r = requests.get(f"{BASE_URL}/runs")
    print(f"List Runs: {r.status_code}")
    runs = r.json()
    for run in runs:
        print(f"  - {run['id']}: {run['title']} ({run['status']})")

if __name__ == "__main__":
    print("=" * 50)
    print("ACM2 API Test")
    print("=" * 50)
    
    test_health()
    print()
    
    preset_id = test_create_preset()
    print()
    
    test_list_presets()
    print()
    
    run_id = test_create_run(preset_id)
    print()
    
    test_list_runs()
    print()
    
    print("=" * 50)
    print("Done!")
