import asyncio
import json
import discord
import os
import yt_dlp
from youtube_search import YoutubeSearch
from spotify import Spotify

class MusicPlayer:
    def __init__(self):
        self.queues = {}
        self.voice_clients = {}
        self.current_songs = {}  # Track currently playing songs
        self.text_channels = {} # Track text channels 
        self.background_tasks = {} # Track background playlist processing tasks

        spot_id = os.getenv("spot_id")
        spot_secret = os.getenv("spot_secret")
        self.sp = Spotify(spot_secret, spot_id)
        
        # YT-DLP configuration
        self.yt_dlp_options = {
            "format": "bestaudio[abr<=96]/bestaudio",
            "noplaylist": True,
            "youtube_include_dash_manifest": False,
            "youtube_include_hls_manifest": False,
        }
        self.ytdl = yt_dlp.YoutubeDL(self.yt_dlp_options)
        
        # FFmpeg options
        self.ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 15 -timeout 10000000',
            'options': '-vn -filter:a "volume=0.25"'
        }
    
    async def connect_to_voice(self, interaction):
        """Connect to the user's voice channel"""
        try:
            # Check if user is in a voice channel
            if not interaction.user.voice:
                return False
                
            voice_client_id = interaction.user.voice.channel.id
            voice_channel = interaction.client.get_channel(voice_client_id)
            
            guild_id = interaction.guild_id
            
            # If already connected to a different channel, move to the new one
            if guild_id in self.voice_clients:
                # If already in the right channel, we're good
                if self.voice_clients[guild_id].channel.id == voice_client_id:
                    return True
                # Otherwise, disconnect to reconnect to the new channel    
                await self.voice_clients[guild_id].disconnect()
                
            # Connect to the voice channel
            voice_client = await voice_channel.connect()
            self.voice_clients[guild_id] = voice_client
            return True
            
        except Exception as e:
            print(f"Voice connection error: {e}")
            return False
    
    async def search_youtube(self, search_term):
        """Search YouTube for a song"""
        if not search_term:
            return None, None
            
        try:
            if search_term.startswith("https://www.youtube.com/watch?v="):
                # Direct URL provided
                song_url = search_term
                try:
                    loop = asyncio.get_event_loop()
                    data = await loop.run_in_executor(None, lambda: self.ytdl.extract_info(song_url, download=False))
                    title = data.get('title', song_url)
                    return song_url, title
                except Exception as e:
                    print(f"Error extracting info from URL: {e}")
                    return None, None
            else:
                # Search by title
                try:
                    yt = YoutubeSearch(search_term, max_results=1).to_json()
                    search_results = json.loads(yt)['videos']
                    
                    if not search_results:
                        return None, None
                        
                    song_id = str(search_results[0]['id'])
                    song_url = f"https://www.youtube.com/watch?v={song_id}"
                    title = search_results[0]['title']
                    return song_url, title
                except Exception as e:
                    print(f"YouTube search error: {e}")
                    return None, None
        except Exception as e:
            print(f"Search YouTube error: {e}")
            return None, None
            
    async def play_playlist(self, interaction, playlist_url):
        """Play or add songs from a playlist using batch processing"""
        guild_id = interaction.guild_id
        
        # Initialize queue if it doesn't exist
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        if guild_id not in self.text_channels:
            self.text_channels[guild_id] = interaction.channel_id
            
        try:
            # Get playlist info in List([track_name, artist_name])
            playlist_info = self.sp.get_playlist_info(playlist_url)
            
            if not playlist_info:
                return False, "Couldn't find or access that playlist!"
            
            # Define batch size for initial loading
            initial_batch_size = 5
            
            # Process first batch to start playback quickly
            first_batch = playlist_info[:initial_batch_size]
            remaining_songs = playlist_info[initial_batch_size:]
            
            # Process first batch
            added_songs = []
            for song in first_batch:
                # Form search query - song name + artist name
                search_query = f"{song[0]} {song[1]['name']}"
                song_url, title = await self.search_youtube(search_query)
                
                if not song_url:
                    continue
                    
                added_songs.append((song_url, title))
            
            if not added_songs:
                return False, "Couldn't find any songs from that playlist!"
            
            # Start a background task to process remaining songs
            asyncio.create_task(self._process_remaining_playlist_songs(
                remaining_songs, 
                guild_id, 
                interaction.client
            ))
            
            # Check if already playing music
            if guild_id in self.voice_clients and self.voice_clients[guild_id].is_playing():
                # Add first batch songs to queue
                for song_url, title in added_songs:
                    self.queues[guild_id].append(song_url)
                    
                return True, f"Added {len(added_songs)} songs from the playlist to queue. Processing {len(remaining_songs)} more songs in the background..."
            else:
                # Play first song immediately
                first_song_url, first_title = added_songs[0]
                
                # Add remaining songs from first batch to queue
                for song_url, title in added_songs[1:]:
                    self.queues[guild_id].append(song_url)
                
                # Play first song
                await self.play_immediate(guild_id, first_song_url, interaction.client)
                
                return True, f"Playing: {first_title}\nAdded {len(added_songs) - 1} songs to the queue. Processing {len(remaining_songs)} more songs in the background..."
                
        except Exception as e:
            print(f"Error in play_playlist function: {e}")
            return False, f"Error playing the playlist: {str(e)}"

    async def _process_remaining_playlist_songs(self, remaining_songs, guild_id, client):
        """Process remaining playlist songs in background"""
        try:
            # Get reference to text channel for status updates
            text_channel = None
            if guild_id in self.text_channels:
                channel_id = self.text_channels[guild_id]
                text_channel = client.get_channel(channel_id)
            
            # Process songs in smaller batches to avoid overwhelming resources
            batch_size = 10
            total_remaining = len(remaining_songs)
            processed_count = 0
            is_cancelled = False
            
            # Track the task in a class attribute if not already there
            if not hasattr(self, 'background_tasks'):
                self.background_tasks = {}
            
            # Store the task for this guild
            self.background_tasks[guild_id] = asyncio.current_task()
            
            # Process in batches
            for i in range(0, len(remaining_songs), batch_size):
                # Multiple checks to ensure we should still be processing
                if any([
                    # Bot disconnected or not in voice clients dict
                    guild_id not in self.voice_clients,
                    # Voice client exists but is not connected
                    guild_id in self.voice_clients and not self.voice_clients[guild_id].is_connected(),
                    # Queue for this guild has been deleted
                    guild_id not in self.queues,
                    # Explicit cancellation flag
                    is_cancelled
                ]):
                    print(f"Voice client disconnected for guild {guild_id}, stopping playlist processing")
                    if guild_id in self.background_tasks:
                        del self.background_tasks[guild_id]
                    return
                    
                # Get current batch
                current_batch = remaining_songs[i:i+batch_size]
                
                # Process batch
                batch_added = 0
                for song in current_batch:
                    # Double-check connection hasn't been lost during song processing
                    if guild_id not in self.voice_clients or not self.voice_clients[guild_id].is_connected():
                        is_cancelled = True
                        break
                        
                    # Form search query - song name + artist name
                    search_query = f"{song[0]} {song[1]['name']}"
                    song_url, title = await self.search_youtube(search_query)
                    
                    if song_url:
                        # Add to queue only if queue still exists
                        if guild_id in self.queues:
                            self.queues[guild_id].append(song_url)
                            batch_added += 1
                    
                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.5)
                
                processed_count += len(current_batch)
                
                # Stop if cancelled
                if is_cancelled:
                    print(f"Playlist processing cancelled for guild {guild_id}")
                    break
                    
                # Optional: Send progress update to channel every few batches
                if text_channel and (i + batch_size) % (batch_size * 3) == 0:
                    # Make sure the channel still exists and is accessible
                    try:
                        progress_percent = int((processed_count / total_remaining) * 100)
                        await text_channel.send(f"Playlist loading progress: {progress_percent}% ({processed_count}/{total_remaining})")
                    except Exception as channel_error:
                        print(f"Could not send progress update: {channel_error}")
                
                # Wait a bit between batches to avoid overwhelming resources
                await asyncio.sleep(2)
            
            # Notify when complete (only if not cancelled and channel is available)
            if not is_cancelled and text_channel:
                try:
                    await text_channel.send(f"✅ Finished loading all {total_remaining} remaining songs from the playlist!")
                except Exception as notification_error:
                    print(f"Could not send completion notification: {notification_error}")
                    
            # Clean up task reference
            if guild_id in self.background_tasks:
                del self.background_tasks[guild_id]
                
        except Exception as e:
            print(f"Error processing remaining playlist songs: {e}")
            # Try to notify in text channel about the error
            if text_channel:
                try:
                    await text_channel.send("⚠️ Encountered an error while processing the full playlist. Some songs might be missing.")
                except:
                    pass
            
            # Clean up task reference even on error
            if guild_id in self.background_tasks:
                del self.background_tasks[guild_id]
        
    async def play_immediate(self, guild_id, song_url, client):
        """Immediately play a song without interaction"""
        try:
            # Get song info
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: self.ytdl.extract_info(song_url, download=False))
            
            if not data or 'url' not in data:
                print(f"No valid URL found for {song_url}")
                return False
                
            # Store current song for reference
            self.current_songs[guild_id] = song_url
            
            # Create audio player
            source_url = data['url']
            player = discord.FFmpegPCMAudio(source_url, **self.ffmpeg_options)
            
            # Play the song
            self.voice_clients[guild_id].play(
                player, 
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self.play_next(guild_id, client.loop, client), 
                    client.loop
                )
            )
            return True
        except Exception as e:
            print(f"Error in play_immediate: {e}")
            return False
        
    async def play_song(self, interaction, song_url):
        """Play a song in a voice channel"""
        guild_id = interaction.guild_id
        
        # Initialize queue if it doesn't exist
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        if guild_id not in self.text_channels:
            self.text_channels[guild_id] = interaction.channel_id
        
        try:
            # Get song info
            song_url, title = await self.search_youtube(song_url)
            if not song_url:
                return False, "Couldn't find that song!"
            
            # Check if already playing
            if guild_id in self.voice_clients and self.voice_clients[guild_id].is_playing():
                # Add to queue if already playing
                self.queues[guild_id].append(song_url)
                return True, f"Added to queue: {title}"
            else:
                # Play immediately and track current song
                self.current_songs[guild_id] = song_url
                
                # Get song audio URL
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: self.ytdl.extract_info(song_url, download=False))
                
                if not data or 'url' not in data:
                    return False, "Error processing that song!"
                    
                source_url = data['url']
                player = discord.FFmpegPCMAudio(source_url, **self.ffmpeg_options)
                
                # Play the song
                self.voice_clients[guild_id].play(
                    player, 
                    after=lambda e: asyncio.run_coroutine_threadsafe(
                        self.play_next(guild_id, interaction.client.loop, interaction.client), 
                        interaction.client.loop
                    )
                )
                return True, f"Playing: {title}"
        except Exception as e:
            print(f"Error in play function: {e}")
            return False, f"Error playing the song: {str(e)}"
    
    async def play_next(self, guild_id, bot_loop, client):
        """Play the next song in the queue"""
        # Clear current song reference
        if guild_id in self.current_songs:
            del self.current_songs[guild_id]
                
        # Check if queue exists and has songs
        if guild_id in self.queues and self.queues[guild_id] and guild_id in self.voice_clients:
            try:
                # Get the next song from queue
                next_song = self.queues[guild_id].pop(0)
                self.current_songs[guild_id] = next_song
                    
                # Get guild from client
                guild = client.get_guild(guild_id)
                if not guild:
                    print(f"Could not find guild with ID {guild_id}")
                    return
                        
                # Find a text channel to notify about the next song
                text_channel = None
                if guild_id in self.text_channels:
                    channel_id = self.text_channels[guild_id]
                    text_channel = client.get_channel(channel_id)
                    # If channel no longer exists or bot doesn't have permissions, log it
                    if text_channel is None or not text_channel.permissions_for(guild.me).send_messages:
                        print(f"Cannot send to original channel {channel_id}, looking for alternative")
                        text_channel = None
                if text_channel == None:
                    for channel in guild.text_channels:
                        if channel.permissions_for(guild.me).send_messages:
                            text_channel = channel
                            break
                    
                # Get song info - Add retry mechanism
                retry_count = 0
                max_retries = 3
                success = False
                
                while retry_count < max_retries and not success:
                    try:
                        loop = asyncio.get_event_loop()
                        data = await loop.run_in_executor(None, lambda: self.ytdl.extract_info(next_song, download=False))
                        
                        if data and 'url' in data:
                            success = True
                        else:
                            retry_count += 1
                            print(f"Retry {retry_count} for {next_song} - no URL found")
                            await asyncio.sleep(1)  # Short delay between retries
                    except Exception as e:
                        retry_count += 1
                        print(f"Retry {retry_count} for {next_song} - error: {e}")
                        await asyncio.sleep(1)  # Short delay between retries
                        
                if not success:
                    print(f"Failed to get URL for {next_song} after {max_retries} retries")
                    if text_channel:
                        await text_channel.send(f"Failed to play song, skipping to next one")
                    # Try playing the next one in queue
                    await self.play_next(guild_id, bot_loop, client)
                    return
                    
                source_url = data['url']
                title = data.get('title', next_song)
                    
                # Create and play the audio source with improved error handling
                try:
                    player = discord.FFmpegPCMAudio(source_url, **self.ffmpeg_options)
                    
                    # Double check that voice client is still connected
                    if guild_id in self.voice_clients and self.voice_clients[guild_id].is_connected():
                        self.voice_clients[guild_id].play(
                            player, 
                            after=lambda e: asyncio.run_coroutine_threadsafe(
                                self.play_next(guild_id, bot_loop, client), 
                                bot_loop
                            )
                        )
                        
                        # Notify about the new song
                        if text_channel:
                            await text_channel.send(f"Now playing: {title}")
                    else:
                        print(f"Voice client disconnected for guild {guild_id}")
                except Exception as e:
                    print(f"Error playing audio: {e}")
                    if text_channel:
                        await text_channel.send(f"Error playing this song, skipping to next")
                    # Try playing the next one in queue
                    await self.play_next(guild_id, bot_loop, client)
            
            except Exception as e:
                print(f"Error in play_next function: {e}")
                # Try to get a channel to notify
                try:
                    guild = client.get_guild(guild_id)
                    if guild:
                        text_channel = None
                        for channel in guild.text_channels:
                            if channel.permissions_for(guild.me).send_messages:
                                text_channel = channel
                                break
                        
                        if text_channel:
                            await text_channel.send(f"Failed to play next song: {str(e)}")
                except Exception as inner_e:
                    print(f"Error notifying about failure: {inner_e}")
    async def check_empty_voice_channels(self, client):
        """
        Check if the bot is alone in any voice channels and disconnect if so.
        This should be called periodically.
        """
        # Create a list of guild IDs to avoid modifying dictionary during iteration
        guild_ids = list(self.voice_clients.keys())
        
        for guild_id in guild_ids:
            try:
                # Get the voice client for this guild
                voice_client = self.voice_clients.get(guild_id)
                if not voice_client or not voice_client.is_connected():
                    continue
                
                # Get the voice channel
                channel = voice_client.channel
                
                # Count members in the voice channel (excluding bots)
                human_members = sum(1 for member in channel.members if not member.bot)
                
                # If no human members are in the channel, disconnect
                if human_members == 0:
                    print(f"No users in voice channel {channel.name} ({channel.id}), disconnecting...")
                    
                    # Try to send a message before disconnecting
                    if guild_id in self.text_channels:
                        try:
                            text_channel = client.get_channel(self.text_channels[guild_id])
                            if text_channel:
                                await text_channel.send("Leaving voice channel because everyone left!")
                        except Exception as e:
                            print(f"Failed to send leave message: {e}")
                    
                    # Cancel any background playlist processing tasks
                    if hasattr(self, 'background_tasks') and guild_id in self.background_tasks:
                        try:
                            task = self.background_tasks[guild_id]
                            if not task.done() and not task.cancelled():
                                task.cancel()
                            print(f"Cancelled background playlist processing for guild {guild_id}")
                        except Exception as task_error:
                            print(f"Error cancelling background task: {task_error}")
                    
                    # Stop playback if playing
                    if voice_client.is_playing():
                        voice_client.stop()
                    
                    # Disconnect from voice channel
                    await voice_client.disconnect()
                    
                    # Clean up resources
                    del self.voice_clients[guild_id]
                    
                    # Clear the queue
                    if guild_id in self.queues:
                        self.queues[guild_id] = []
                        
                    # Clear current song reference
                    if guild_id in self.current_songs:
                        del self.current_songs[guild_id]
                        
            except Exception as e:
                print(f"Error checking empty voice channel for guild {guild_id}: {e}")