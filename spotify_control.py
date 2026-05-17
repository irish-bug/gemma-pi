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

    # Clean query prefixes if Gemma/Artoo leaves them in bi
    for prefix in ["tell artoo to play ", "play "]:
        if query.startswith(prefix):
            query = query[len(prefix):]

    # Required permissions for controlling playback
    scope = "user-modify-playback-state user-read-playback-state"
    
    # open_browser=False prints the authentication URL cleanly in the SSH terminal
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        scope=scope,
        open_browser=False
    ))

# 1. Locate the Gemma Speaker Device ID
    devices = sp.devices()
    device_id = None
    
    # Print what Spotify actually sees so we can audit the network state
    print(f"Available devices found: {[d['name'] for d in devices.get('devices', [])]}")
    
    # Target our newly named speaker explicitly
    for d in devices.get('devices', []):
        if 'gemma' in d['name'].lower():
            device_id = d['id']
            break

    if not device_id:
        print("Error: GEMMA_Speaker not found in available devices. Is Raspotify awake?")
        sys.exit(1)

    # 2. Search and Play
# 2. Search for the Track or Album
    query = sys.argv[1]
    
    # Simple semantic routing: if the user says "album", search for an album
    if "album" in query.lower():
        clean_query = query.lower().replace("album", "").strip()
        results = sp.search(q=clean_query, limit=1, type='album')
        albums = results.get('albums', {}).get('items', [])
        
        if not albums:
            print(f"Error: Could not find an album matching '{clean_query}'")
            sys.exit(1)
            
        album_uri = albums[0]['uri']
        print(f"Success: Playing album '{albums[0]['name']}' by {albums[0]['artists'][0]['name']} on GEMMA_Speaker.")
        sp.start_playback(device_id=device_id, context_uri=album_uri)
        
    else:
        # Default behavior: Search for a single track
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