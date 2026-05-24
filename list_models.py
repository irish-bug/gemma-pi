#list all available models
import os
import sys
from google import genai

def enumerate_models():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("[!] FATAL: GOOGLE_API_KEY environment variable is not set.")
        sys.exit(1)

    print("[*] Project Gemma: Scanning API for unlocked models...\n")
    client = genai.Client()
    
    try:
        # Fetch the generator of all models available to this specific key
        models = client.models.list()
        
        print(f"{'MODEL ID':<40} | {'DISPLAY NAME':<35} | {'LIMIT (Tokens)'}")
        print("-" * 95)
        
        for model in models:
            # We filter for 'gemini' to keep the legacy bison/palm models off the screen
            if "gemini" in model.name:
                # The API usually returns 'models/gemini-X', so we strip the prefix for cleaner reading
                clean_name = model.name.replace("models/", "")
                display = str(model.display_name)[:34]
                print(f"{clean_name:<40} | {display:<35} | {model.input_token_limit}")
                
    except Exception as e:
        print(f"[X] FATAL: Failed to enumerate models. {e}")

if __name__ == "__main__":
    enumerate_models()
