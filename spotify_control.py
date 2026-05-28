# --- CHANGELOG: spotify_control.py ---
# Fix 1: Variable Shadowing / Overwrite Bug
# - Issue: The script was stripping prefix words (like "tell artoo to play"), but immediately overwriting the cleaned `query` variable with `sys.argv[1]` right before the Spotify search execution.
# - Fix: Removed the redundant `query = sys.argv[1]` redeclaration in the search block. Added `.strip()` to the prefix cleaner to ensure no leading spaces break the semantic search.
# 
# Fix 2: Missing Explicit Media Controls (The "Stop" Fallthrough)
# - Issue: There was no routing for "stop" or "pause". When Gemma sent the "stop music" tool command, the script fell through to the default `else` block and attempted to search Spotify for a track literally named "stop music".
# - Fix: Injected an explicit `if "stop" in query or "pause" in query:` block that triggers `sp.pause_playback(device_id)` and calls `sys.exit(0)` before any search logic executes.

#!/home/shane/google-labs/gemma_stable_env/bin/python
import sys
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 spotify_control.py 'play The Beatles'")
        sys.exit(1)

    query = sys.argv[1].lower()

    # Clean query prefixes if Gemma/Artoo leaves them in
    for prefix in ["tell artoo to play ", "play ", "tell artoo to "]:
        if query.startswith(prefix):
            query = query[len(prefix):].strip()

    # Required permissions for controlling playback
    scope = "user-modify-playback-state user-read-playback-state"
    
    CLIENT_ID = "9d6fbdf00c2c40abafa3949764ef2fe1"
    CLIENT_SECRET = "912d11c2ce22432ab78bcbb449bd0c9e"
    REDIRECT_URI = "http://127.0.0.1:8888/callback"
    CACHE_PATH = "/home/shane/google-labs/.cache"
    
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=scope,
        cache_path=CACHE_PATH,
        open_browser=False
    ))

    # 1. Locate the Gemma Speaker Device ID
    devices = sp.devices()
    device_id = None
    
    for d in devices.get('devices', []):
        if 'gemma' in d['name'].lower():
            device_id = d['id']
            break

    if not device_id:
        print("Error: GEMMA_Speaker not found in available devices. Is Raspotify awake?")
        sys.exit(1)

    # 2. Handle specific playback controls BEFORE searching
    if "stop" in query or "pause" in query:
        try:
            sp.pause_playback(device_id=device_id)
            print("Success: Music paused on GEMMA_Speaker.")
            sys.exit(0)
        except Exception as e:
            print(f"Error pausing playback: {e}")
            sys.exit(1)

    # 3. Search for the Track or Album (Variable overwrite bug fixed here)
    if "album" in query:
        clean_query = query.replace("album", "").strip()
        results = sp.search(q=clean_query, limit=1, type='album')
        albums = results.get('albums', {}).get('items', [])
        
        if not albums:
            print(f"Error: Could not find an album matching '{clean_query}'")
            sys.exit(1)
            
        album_uri = albums[0]['uri']
        print(f"Success: Playing album '{albums[0]['name']}' by {albums[0]['artists'][0]['name']} on GEMMA_Speaker.")
        sp.start_playback(device_id=device_id, context_uri=album_uri)
        
    else:
        results = sp.search(q=query, limit=1, type='track')
        tracks = results.get('tracks', {}).get('items', [])
        
        if not tracks:
            print(f"Error: Could not find a track matching '{query}'")
            sys.exit(1)
            
        track_uri = tracks[0]['uri']
        print(f"Success: Playing track '{tracks[0]['name']}' by {tracks[0]['artists'][0]['name']} on GEMMA_Speaker.")
        sp.start_playback(device_id=device_id, uris=[track_uri])

if __name__ == "__main__":
    main()