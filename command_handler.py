import discord
from discord import app_commands
import asyncio
import random

def register_commands(tree, client, music_player, guild_id):
    """Register all slash commands with the command tree"""
    
    @tree.command(
        name="play",
        description="Play a song or Spotify playlist",
        guild=discord.Object(id=guild_id)
    )
    @app_commands.describe(song_title="Enter song title, YouTube URL, or Spotify playlist URL")
    async def play(interaction: discord.Interaction, song_title: str):
        try:
            # Connect to voice channel first
            if not await music_player.connect_to_voice(interaction):
                await interaction.response.send_message("You need to join a voice channel first!")
                return
                
            # Always defer the response first to prevent timeout issues
            await interaction.response.defer()
                
            if "https://open.spotify.com/playlist/" in song_title:
                # For playlists
                success, message = await music_player.play_playlist(interaction, song_title)
            else:
                # For single songs
                success, message = await music_player.play_song(interaction, song_title)
                
            # Use followup for all responses
            await interaction.followup.send(message)
                
        except Exception as e:
            print(f"Error in play command: {e}")
            try:
                await interaction.followup.send(f"An error occurred: {str(e)}")
            except Exception as inner_e:
                print(f"Failed to send error message: {inner_e}")

    @tree.command(
        name="stop",
        description="Stops the player and disconnects the bot",
        guild=discord.Object(id=guild_id)
    )
    async def stop(interaction: discord.Interaction):
        try:
            guild_id = interaction.guild_id
            music_player.text_channels[guild_id] = interaction.channel_id
            if guild_id in music_player.voice_clients:
                # Stop playback
                if music_player.voice_clients[guild_id].is_playing():
                    music_player.voice_clients[guild_id].stop()
                
                # Send response first before disconnecting
                await interaction.response.send_message("Leaving ;-;")
                
                # Cancel any background playlist processing tasks
                if hasattr(music_player, 'background_tasks') and guild_id in music_player.background_tasks:
                    try:
                        # Mark for cancellation (our task checks this flag)
                        task = music_player.background_tasks[guild_id]
                        if not task.done() and not task.cancelled():
                            task.cancel()
                        print(f"Cancelled background playlist processing for guild {guild_id}")
                    except Exception as task_error:
                        print(f"Error cancelling background task: {task_error}")
                
                # Then disconnect
                await music_player.voice_clients[guild_id].disconnect()
                
                # Clean up resources
                del music_player.voice_clients[guild_id]
                
                # Clear the queue
                if guild_id in music_player.queues:
                    music_player.queues[guild_id] = []
                    
                # Clear current song reference
                if guild_id in music_player.current_songs:
                    del music_player.current_songs[guild_id]
                # Clear the text channel reference
                if guild_id in music_player.text_channels:
                    del music_player.text_channels[guild_id]
            else:
                await interaction.response.send_message("Not connected to a voice channel!")
        except Exception as e:
            print(f"Error in stop command: {e}")
            try:
                await interaction.response.send_message(f"Failed to stop playback: {str(e)}")
            except discord.errors.InteractionResponded:
                await interaction.followup.send(f"Failed to stop playback: {str(e)}")

    @tree.command(
        name="pause",
        description="Pauses the player",
        guild=discord.Object(id=guild_id)
    )
    async def pause(interaction: discord.Interaction):
        try:
            guild_id = interaction.guild_id
            if guild_id in music_player.voice_clients and music_player.voice_clients[guild_id].is_playing():
                music_player.voice_clients[guild_id].pause()
                await interaction.response.send_message("Paused playback.")
            else:
                await interaction.response.send_message("Nothing is playing right now!")
        except Exception as e:
            print(f"Error in pause command: {e}")
            try:
                await interaction.response.send_message(f"Failed to pause: {str(e)}")
            except discord.errors.InteractionResponded:
                await interaction.followup.send(f"Failed to pause: {str(e)}")

    @tree.command(
        name="resume",
        description="Resumes the player",
        guild=discord.Object(id=guild_id)
    )
    async def resume(interaction: discord.Interaction):
        try:
            guild_id = interaction.guild_id
            if guild_id in music_player.voice_clients and music_player.voice_clients[guild_id].is_paused():
                music_player.voice_clients[guild_id].resume()
                await interaction.response.send_message("Resuming playback.")
            else:
                await interaction.response.send_message("Nothing is paused right now!")
        except Exception as e:
            print(f"Error in resume command: {e}")
            try:
                await interaction.response.send_message(f"Failed to resume: {str(e)}")
            except discord.errors.InteractionResponded:
                await interaction.followup.send(f"Failed to resume: {str(e)}")

    @tree.command(
        name="skip",
        description="Skips the current song",
        guild=discord.Object(id=guild_id)
    )
    async def skip(interaction: discord.Interaction):
        try:
            guild_id = interaction.guild_id
            
            # Check if connected to voice
            if guild_id not in music_player.voice_clients:
                await interaction.response.send_message("I'm not connected to a voice channel!")
                return
            
            # Check if we have a queue for this guild
            if guild_id not in music_player.queues or not music_player.queues[guild_id]:
                await interaction.response.send_message("No songs in queue to skip to!")
                return
                
            # Acknowledge the skip request
            await interaction.response.send_message("Skipping to next song...")
            
            # Stop current playback
            if music_player.voice_clients[guild_id].is_playing():
                music_player.voice_clients[guild_id].stop()
                
            # The play_next function will be automatically called by the 'after' parameter
            
        except Exception as e:
            print(f"Error in skip function: {e}")
            try:
                await interaction.response.send_message(f"Failed to skip: {str(e)}")
            except discord.errors.InteractionResponded:
                await interaction.followup.send(f"Failed to skip: {str(e)}")

    @tree.command(
        name="queue",
        description="Shows the current song queue",
        guild=discord.Object(id=guild_id)
    )
    async def queue(interaction: discord.Interaction):
        try:
            # Defer response to avoid timeout
            await interaction.response.defer()
            
            guild_id = interaction.guild_id
            
            # Check if queue exists
            if guild_id not in music_player.queues or not music_player.queues[guild_id]:
                await interaction.followup.send("The queue is empty!")
                return
                
            # Get current song info
            current_title = "Unknown song"
            if guild_id in music_player.current_songs:
                _, current_title = await music_player.search_youtube(music_player.current_songs[guild_id])
            
            # Begin building queue message
            queue_message = f"**Currently Playing:** {current_title}\n\n**Queue:**\n"
            
            # Process up to 10 songs in queue to avoid timeout
            queue_list = []
            position = 1
            
            # Process songs in batches to avoid timeouts
            songs_to_process = min(5, len(music_player.queues[guild_id]))
            
            for i in range(songs_to_process):
                song_url = music_player.queues[guild_id][i]
                try:
                    _, title = await music_player.search_youtube(song_url)
                    if title:
                        queue_list.append(f"{position}. {title}")
                    else:
                        queue_list.append(f"{position}. Unknown song")
                except Exception as e:
                    print(f"Error getting queue item title: {e}")
                    queue_list.append(f"{position}. Unknown song")
                position += 1
                
            # Add the list to the message
            queue_message += "\n".join(queue_list)
            
            # Add footer if there are more songs
            if len(music_player.queues[guild_id]) > 10:
                queue_message += f"\n\n...and {len(music_player.queues[guild_id]) - 10} more songs"
                
            # Send the queue information
            await interaction.followup.send(queue_message)
                
        except Exception as e:
            print(f"Error in queue command: {e}")
            try:
                await interaction.followup.send(f"Failed to get queue: {str(e)}")
            except:
                # If all else fails, try again with a new message
                try:
                    await interaction.channel.send(f"Failed to show queue: {str(e)}")
                except:
                    pass
    @tree.command(
        name="shuffle",
        description="Shuffles the current playlist",
        guild=discord.Object(id=guild_id)
    )
    async def shuffle(interaction: discord.Interaction):
        try:
            guild_id = interaction.guild_id
            # Check if queue exists
            if guild_id not in music_player.queues or not music_player.queues[guild_id]:
                await interaction.followup.send("The queue is empty!")
                return
            random.shuffle(music_player.queues[guild_id])
            # Acknowledge the skip request
            await interaction.response.send_message("Shuffling the queue....")
        except Exception as e:
            print(f"Error in shuffle command: {e}")
            try:
                await interaction.followup.send(f"Failed to shuffle playlist: {str(e)}")
            except:
                # If all else fails, try again with a new message
                try:
                    await interaction.channel.send(f"Failed to shuffle playlist: {str(e)}")
                except:
                    pass