##test script for verification of model access
import os
import sys
from google import genai
from google.genai.errors import APIError

def verify_endpoints():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("[!] FATAL: GOOGLE_API_KEY environment variable is not set.")
        sys.exit(1)

    print("[*] Project Gemma: Initializing API Endpoint Verification...")
    client = genai.Client()
    
    # The GA targets for May 2026
    models_to_test = [
        "gemini-3.1-flash-lite",
        "gemini-3.1-flash"
    ]

    for model_name in models_to_test:
        try:
            # Querying the model definition directly bypasses the need for a WebSocket handshake
            model_info = client.models.get(model=model_name)
            print(f"  [✓] ONLINE : {model_name}")
            print(f"      ├─ Display Name : {model_info.display_name}")
            print(f"      └─ Context Limit: {model_info.input_token_limit} tokens")
        except APIError as e:
            print(f"  [X] OFFLINE: {model_name} is unavailable or quota denied.")
            print(f"      └─ Exception: {e}")
        except Exception as e:
            print(f"  [X] ERROR  : Unexpected failure on {model_name}.")
            print(f"      └─ Exception: {e}")

if __name__ == "__main__":
    verify_endpoints()