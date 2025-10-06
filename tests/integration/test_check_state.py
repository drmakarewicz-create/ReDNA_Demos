import requests
import json
from pathlib import Path
import shutil

BASE_URL = "http://localhost:8001"
TEST_USER = "hc_v2_1b_demo"

# Simulate cleanup
print("=== CLEANUP ===")
user_dir = Path("data/users") / TEST_USER
if user_dir.exists():
    shutil.rmtree(user_dir)
print(f"Cleaned up {TEST_USER}")

# Simulate Test 1 - conversation
print("\n=== TEST 1: CONVERSATION ===")
requests.post(f"{BASE_URL}/hc/say?user_id={TEST_USER}", json={"message": "Hello"})
requests.post(f"{BASE_URL}/hc/say?user_id={TEST_USER}", json={"message": "Hi there"})
resp = requests.get(f"{BASE_URL}/hc/conversation/history?user_id={TEST_USER}")
print(f"Conversation messages: {len(resp.json().get('messages', []))}")

# Simulate Test 2 - playbook
print("\n=== TEST 2: PLAYBOOK ===")
from ReDNACoreDemo.core.storage import write_user_state

resolved = {
    "PaDNA.EyeDNA.Iris.BaseColor": {
        "resolved_value": "Green",
        "curiosity": 900,
        "ucn": 800,
        "rr": 100
    }
}
write_user_state(TEST_USER, resolved, {}, [])
print("Created user state")

resp = requests.post(f"{BASE_URL}/hc/playbooks/run?user_id={TEST_USER}", 
                    json={"playbook_id": "curiosity_campaign"})
print(f"Playbook result: {resp.json()}")

resp = requests.get(f"{BASE_URL}/hc/tasks/list?user_id={TEST_USER}")
tasks = resp.json()["tasks"]
print(f"Tasks after Test 2: {len(tasks)}")
for t in tasks:
    print(f"  - {t['id']}: {t['title']} (state: {t['state']})")

# Check conversation
resp = requests.get(f"{BASE_URL}/hc/conversation/history?user_id={TEST_USER}")
print(f"Conversation messages after Test 2: {len(resp.json().get('messages', []))}")

# Simulate Test 3 - task execution
print("\n=== TEST 3: TASK EXECUTION ===")

# List tasks before enqueueing
resp = requests.get(f"{BASE_URL}/hc/tasks/list?user_id={TEST_USER}")
tasks_before = resp.json()["tasks"]
print(f"Tasks before Test 3: {len(tasks_before)}")

# Enqueue new task
resp = requests.post(
    f"{BASE_URL}/hc/tasks/queue?user_id={TEST_USER}",
    json={
        "title": "Add evidence for Eye Color",
        "action": "add_evidence",
        "args": {"trait": "PaDNA.EyeDNA.Iris.BaseColor"},
        "eta_mins": 2
    }
)
task = resp.json()
print(f"Enqueued task: {task['id']}")

# List tasks after enqueueing
resp = requests.get(f"{BASE_URL}/hc/tasks/list?user_id={TEST_USER}")
tasks_after = resp.json()["tasks"]
print(f"Tasks after enqueueing: {len(tasks_after)}")
for t in tasks_after:
    print(f"  - {t['id']}: {t['title']} (state: {t['state']})")

# Execute task
resp = requests.post(f"{BASE_URL}/hc/tasks/tick?user_id={TEST_USER}")
result = resp.json()
print(f"\nTick result: {json.dumps(result, indent=2)}")

# Check conversation
resp = requests.get(f"{BASE_URL}/hc/conversation/history?user_id={TEST_USER}")
history = resp.json()
print(f"\nConversation messages after tick: {len(history.get('messages', []))}")

# Find the entry
evidence_entry = None
for msg in history.get("messages", []):
    print(f"  - ts: {msg.get('ts')}, task_id: {msg.get('task_id')}, content: {msg.get('content')[:50]}...")
    if msg.get("task_id") == task["id"]:
        evidence_entry = msg
        break

if evidence_entry:
    print(f"\n✅ Found evidence entry for task {task['id']}")
else:
    print(f"\n❌ No evidence entry found for task {task['id']}")

# Cleanup
shutil.rmtree(user_dir)
