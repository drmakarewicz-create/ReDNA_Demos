import os
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY", None)
if api_key:
    print("✅ OPENAI_API_KEY is loaded and available in the environment.")
    print(f"First 6 chars: {api_key[:6]}... (redacted)")
else:
    print("❌ OPENAI_API_KEY not found. Check your .env file or path.")
