import asyncio
import pyaudio
from google import genai

# Audio Configuration (Matches Gemini Live specs)
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE_IN = 16000  # Gemini expects 16kHz input
RATE_OUT = 24000 # Gemini returns 24kHz output
CHUNK = 512

client = genai.Client(api_key="AIzaSyBcFGxFC5Wr-YzmcLlOkVUWLia5ecgyqC0", http_options={'api_version': 'v1alpha'})

async def voice_session():
    p = pyaudio.PyAudio()
    
    # Mic Stream
    mic = p.open(format=FORMAT, channels=CHANNELS, rate=RATE_IN, input=True, frames_per_buffer=CHUNK)
    # Speaker Stream
    speaker = p.open(format=FORMAT, channels=CHANNELS, rate=RATE_OUT, output=True)

    print("--- Session Started: Start talking! ---")

    async with client.aio.live.connect(model="gemini-3.1-flash-live-preview", config={"response_modalities": ["AUDIO"]}) as session:
        
        async def send_audio():
            while True:
                data = await asyncio.to_thread(mic.read, CHUNK)
                await session.send_realtime_input(data)

        async def receive_audio():
            async for message in session.receive():
                if message.server_content and message.server_content.model_turn:
                    parts = message.server_content.model_turn.parts
                    for part in parts:
                        if part.inline_data:
                            await asyncio.to_thread(speaker.write, part.inline_data.data)

        await asyncio.gather(send_audio(), receive_audio())

if __name__ == "__main__":
    asyncio.run(voice_session())
