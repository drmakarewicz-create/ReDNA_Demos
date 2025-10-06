import os
from dotenv import load_dotenv

load_dotenv()

print("API key (first 8 chars):", os.getenv("OPENAI_API_KEY")[:8])
print("Model:", os.getenv("OPENAI_MODEL"))