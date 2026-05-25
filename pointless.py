import google.generativeai as genai
import os

# Configure the SDK
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.0-flash")

def run_command(prompt):
    # This uses standard REST inference, bypassing the WebSocket/Bidi gateway
    response = model.generate_content(prompt)puy
    print(f"[Gemma]: {response.text}")

if __name__ == "__main__":
    # Test ground connectivity
    run_command("What is the current weather in Golden, CO?")