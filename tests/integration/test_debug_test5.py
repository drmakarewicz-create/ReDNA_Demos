import requests

BASE_URL = "http://localhost:8001"
TEST_USER = "hc_v2_1b_demo"

# Try the endpoint
response = requests.get(f"{BASE_URL}/hc/state?userId={TEST_USER}")
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
