import discord
import os
from dotenv import load_dotenv
from discord import app_commands
from music_player import MusicPlayer
from command_handler import register_commands
import asyncio

async def auto_disconnect_task(client, music_player):
    """Background task to periodically check for empty voice channels"""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            await music_player.check_empty_voice_channels(client)
        except Exception as e:
            print(f"Error in auto-disconnect task: {e}")
        
        # Check every 30 seconds
        await asyncio.sleep(30)
def run_bot():
    # Load environment variables
    load_dotenv()
    TOKEN = os.getenv("token")
    GUILD_ID = os.getenv("server_id")
    
    # Set up Discord client
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)
    
    # Initialize music player
    music_player = MusicPlayer()
    
    # Register commands with the command tree
    register_commands(tree, client, music_player, GUILD_ID)

    @client.event
    async def on_ready():
        # Sync for a single guild
        await tree.sync(guild=discord.Object(id=GUILD_ID))
        # For all guilds: await tree.sync()
        print(f"{client.user} is now ready.")
        # Start the auto-disconnect task
        client.loop.create_task(auto_disconnect_task(client, music_player))
        # Add this to your main bot file

    @client.event
    async def on_voice_state_update(member, before, after):
        """Handle voice state updates (users joining/leaving voice channels)"""
        # Skip if this update is for a bot
        if member.bot:
            return
            
        # Check if the user left a voice channel
        if before.channel and after.channel != before.channel:
            # Get the guild ID
            guild_id = before.channel.guild.id
            
            # Check if our bot is in this voice channel
            if guild_id in music_player.voice_clients and music_player.voice_clients[guild_id].channel == before.channel:
                # Count human members in the channel
                human_members = sum(1 for m in before.channel.members if not m.bot)
                
                # If no human members left in the channel, disconnect
                if human_members == 0:
                    print(f"All users left voice channel {before.channel.name}, disconnecting...")
                    
                    try:
                        # Try to send a message before disconnecting
                        if guild_id in music_player.text_channels:
                            text_channel = client.get_channel(music_player.text_channels[guild_id])
                            if text_channel:
                                await text_channel.send("Everyone paitao me :(")
                        
                        # Cancel any background playlist processing tasks
                        if hasattr(music_player, 'background_tasks') and guild_id in music_player.background_tasks:
                            try:
                                task = music_player.background_tasks[guild_id]
                                if not task.done() and not task.cancelled():
                                    task.cancel()
                                print(f"Cancelled background playlist processing for guild {guild_id}")
                            except Exception as task_error:
                                print(f"Error cancelling background task: {task_error}")
                        
                        # Stop playback if playing
                        voice_client = music_player.voice_clients[guild_id]
                        if voice_client.is_playing():
                            voice_client.stop()
                        
                        # Disconnect from voice channel
                        await voice_client.disconnect()
                        
                        # Clean up resources
                        del music_player.voice_clients[guild_id]
                        
                        # Clear the queue
                        if guild_id in music_player.queues:
                            music_player.queues[guild_id] = []
                            
                        # Clear current song reference
                        if guild_id in music_player.current_songs:
                            del music_player.current_songs[guild_id]
                            
                    except Exception as e:
                        print(f"Error disconnecting from empty voice channel: {e}")
    # Run the client
    client.run(TOKEN)

if __name__ == "__main__":
    run_bot()