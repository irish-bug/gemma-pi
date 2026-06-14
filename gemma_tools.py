# --- v18.0.4 Gemma Session Tools ---
# This module contains specific tools that control the lifecycle 
# and behavior of the Gemma Live websocket session itself, 
# completely isolated from Artoo's OS-level executions.

import asyncio

# Global reference set to protect tasks from the Garbage Collector
background_tasks = set()

def create_bg_task(loop, coro):
    """
    Wraps task creation to maintain a strong reference, preventing GC destruction.
    Passes the active asyncio event loop to ensure thread-safe creation.
    """
    task = loop.create_task(coro)
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return task

async def handle_end_session(input_queue):
    """
    Cleans up the audio buffer and initiates a session disconnect.
    """
    print("\n[!] Manual Sleep Command Received. Severing websocket...")
    
    # Wait a moment for her goodbye audio to finish playing
    await asyncio.sleep(1.5) 
    
    # Flush any trailing audio from the microphone buffer
    while not input_queue.empty(): 
        input_queue.get_nowait()
        
    # We return True as a flag to the main loop to break the connection
    return True