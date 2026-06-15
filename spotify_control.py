#!/home/shane/google-labs/gemma_stable_env/bin/python
import sys
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# --- CHANGELOG: spotify_control.py ---
# Fix 11: Swallowed librespot false-positive. Added a try/except block around start_playback to catch and ignore the 403 "Restriction violated" error that librespot clients throw after successfully starting a stream. Ensures Artoo receives a clean "Success" string.
# Fix 10: Brute-Force Device Matching. Removed the TARGET_NAMES dictionary abstraction. The script now performs a direct, case-insensitive substring search of the network devices using whatever target_node string Artoo passes it.
# Fix 9: Substring matching (depreciated).
# Fix 8: Externalized credentials to .env.

def load_local_env():
    """Parses gemma_stable_env/.env manually to prevent dependency issues."""
    env_path = "/home/shane/google-labs/gemma_stable_env/.env"
    if not os.path.exists(env_path):
        print(f"Error: Environment file not found at {env_path}")
        sys.exit(1)
        
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            
            if key in ["CLIENT_ID", "SPOTIPY_CLIENT_ID"]:
                os.environ["SPOTIPY_CLIENT_ID"] = value
            elif key in ["CLIENT_SECRET", "SPOTIPY_CLIENT_SECRET"]:
                os.environ["SPOTIPY_CLIENT_SECRET"] = value
            elif key in ["REDIRECT_URI", "SPOTIPY_REDIRECT_URI"]:
                os.environ["SPOTIPY_REDIRECT_URI"] = value

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 spotify_control.py 'play The Beatles' [target_device_name]")
        sys.exit(1)

    query = sys.argv[1].lower()
    
    # If Artoo passes a target, use it. Otherwise default to GEMMA.
    raw_target = sys.argv[2].strip() if len(sys.argv) > 2 else "gemma"

    # Clean query prefixes
    for prefix in ["tell artoo to play ", "play ", "tell artoo to "]:
        if query.startswith(prefix):
            query = query[len(prefix):].strip()

    load_local_env()
    
    CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
    CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
    REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")
    
    if not all([CLIENT_ID, CLIENT_SECRET, REDIRECT_URI]):
        print("Error: Missing credentials in .env")
        sys.exit(1)

    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope="user-modify-playback-state user-read-playback-state user-read-playback-position",
        cache_path="/home/shane/google-labs/.cache",
        open_browser=False
    ))

    # --- THE BRUTE-FORCE DEVICE DISCOVERY ---
    devices = sp.devices().get('devices', [])
    device_id = None
    actual_name = None
    
    for d in devices:
        # Case-insensitive substring match
        if raw_target.lower() in d['name'].lower():
            device_id = d['id']
            actual_name = d['name']
            break
            
    if not device_id:
        available = ", ".join([d['name'] for d in devices])
        print(f"Error: Target '{raw_target}' not found. Available devices: [{available}]")
        sys.exit(1)

    # Wake the target device
    try:
        sp.transfer_playback(device_id=device_id, force_play=False)
    except Exception:
        pass

    # Handle specific playback controls
    if "stop" in query or "pause" in query:
        try:
            sp.pause_playback(device_id=device_id)
            print(f"Success: Music paused on {actual_name}.")
            sys.exit(0)
        except Exception as e:
            print(f"Error pausing playback: {e}")
            sys.exit(1)

    # Search for the Track or Album
    if "album" in query:
        clean_query = query.replace("album", "").strip()
        if " by " in clean_query:
            parts = clean_query.split(" by ", 1)
            search_q = f"album:{parts[0].strip()} artist:{parts[1].strip()}"
        else:
            search_q = clean_query
            
        results = sp.search(q=search_q, limit=1, type='album')
        if not results.get('albums', {}).get('items', []):
            results = sp.search(q=clean_query, limit=1, type='album')
            
        albums = results.get('albums', {}).get('items', [])
        if not albums:
            print(f"Error: Could not find album '{clean_query}'")
            sys.exit(1)
            
        album_uri = albums[0]['uri']
        
        try:
            sp.start_playback(device_id=device_id, context_uri=album_uri)
            print(f"Success: Playing album '{albums[0]['name']}' by {albums[0]['artists'][0]['name']} on {actual_name}.")
        except spotipy.exceptions.SpotifyException as e:
            if "Restriction violated" in str(e):
                print(f"Success: Playing album '{albums[0]['name']}' by {albums[0]['artists'][0]['name']} on {actual_name}.")
            else:
                print(f"Error starting playback: {e}")
                sys.exit(1)
        
    else:
        if " by " in query:
            parts = query.split(" by ", 1)
            search_q = f"track:{parts[0].strip()} artist:{parts[1].strip()}"
        else:
            search_q = query
            
        results = sp.search(q=search_q, limit=1, type='track')
        if not results.get('tracks', {}).get('items', []):
            results = sp.search(q=query, limit=1, type='track')
            
        tracks = results.get('tracks', {}).get('items', [])
        if not tracks:
            print(f"Error: Could not find track '{query}'")
            sys.exit(1)
            
        track_uri = tracks[0]['uri']
        
        try:
            sp.start_playback(device_id=device_id, uris=[track_uri])
            print(f"Success: Playing track '{tracks[0]['name']}' by {tracks[0]['artists'][0]['name']} on {actual_name}.")
        except spotipy.exceptions.SpotifyException as e:
            if "Restriction violated" in str(e):
                print(f"Success: Playing track '{tracks[0]['name']}' by {tracks[0]['artists'][0]['name']} on {actual_name}.")
            else:
                print(f"Error starting playback: {e}")
                sys.exit(1)

if __name__ == "__main__":
    main()