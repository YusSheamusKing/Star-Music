import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import re

class Spotify:
    def __init__(self, SECRET, ID):
        self.secret = SECRET
        self.id = ID
        self.client_credentials_manager = SpotifyClientCredentials(client_id=self.id, client_secret=self.secret)
        self.sp = spotipy.Spotify(client_credentials_manager=self.client_credentials_manager)
        
    def get_playlist_id_from_url(self, url):
        # Extract the playlist ID from various URL formats
        patterns = [
            r'spotify:playlist:([a-zA-Z0-9]+)',  # Spotify URI
            r'open.spotify.com/playlist/([a-zA-Z0-9]+)',  # Web URL
            r'/playlist/([a-zA-Z0-9]+)'  # Partial URL
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
        
    def get_playlist_info(self, playlist_url):
        # Extract playlist ID from URL
        playlist_id = self.get_playlist_id_from_url(playlist_url)
        
        if not playlist_id:
            print(f"Could not extract playlist ID from URL: {playlist_url}")
            return []
        
        try:
            # Fetch the playlist
            res = []
            playlist = self.sp.playlist(playlist_id)
            
            # Check if tracks exist in the playlist
            if not playlist or 'tracks' not in playlist or 'items' not in playlist['tracks']:
                print(f"Invalid playlist structure: {playlist_url}")
                return []
                
            for i, item in enumerate(playlist['tracks']['items']):
                # Skip None tracks or items without track
                if not item or 'track' not in item or not item['track']:
                    continue
                    
                track = item['track']
                
                # Ensure track has a name and at least one artist
                if 'name' not in track or 'artists' not in track or not track['artists']:
                    continue
                    
                # Default to 'Unknown Artist' if no artist name is available
                artist_name = {'name': 'Unknown Artist'}
                if track['artists'] and 'name' in track['artists'][0]:
                    artist_name = track['artists'][0]
                    
                res.append([track['name'], artist_name])
            return res
        except spotipy.exceptions.SpotifyException as e:
            print(f"Error accessing playlist: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error accessing playlist: {e}")
            return []