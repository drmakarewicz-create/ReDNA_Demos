import requests
import json

BASE_URL = "http://localhost:8001"
TEST_USER = "debug_test_user"

# Clean up first
requests.delete(f"{BASE_URL}/users/{TEST_USER}")

# Enqueue add_evidence task
print("Enqueueing task...")
response = requests.post(
    f"{BASE_URL}/hc/tasks/queue?user_id={TEST_USER}",
    json={
        "title": "Add evidence for Eye Color",
        "action": "add_evidence",
        "args": {"trait": "PaDNA.EyeDNA.Iris.BaseColor"},
        "eta_mins": 2
    }
)
print(f"Status: {response.status_code}")
task = response.json()
print(f"Task ID: {task['id']}")

# Execute task
print("\nExecuting task...")
response = requests.post(f"{BASE_URL}/hc/tasks/tick?user_id={TEST_USER}")
print(f"Status: {response.status_code}")
result = response.json()
print(f"Result: {json.dumps(result, indent=2)}")

# Check conversation history
print("\nChecking conversation history...")
response = requests.get(f"{BASE_URL}/hc/conversation/history?user_id={TEST_USER}")
print(f"Status: {response.status_code}")
history = response.json()
print(f"History: {json.dumps(history, indent=2)}")

# Find the entry
evidence_entry = None
for msg in history.get("messages", []):
    if msg.get("task_id") == task["id"]:
        evidence_entry = msg
        break

if evidence_entry:
    print("\n✅ Found evidence entry!")
    print(f"Entry: {json.dumps(evidence_entry, indent=2)}")
else:
    print("\n❌ Evidence entry not found")
    print(f"Looking for task_id: {task['id']}")
    print(f"Messages: {len(history.get('messages', []))}")

# Clean up
requests.delete(f"{BASE_URL}/users/{TEST_USER}")
