#!//home/shane/google-labs/gemma_stable_env/bin/python

from google import genai
import os

client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
print("Models supporting the Live (bidi) protocol:")
for m in client.models.list():
    if 'bidiGenerateContent' in m.supported_actions:
        print(f"- {m.name}")