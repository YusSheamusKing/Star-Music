# RexTunes

A simple Discord music bot that plays songs from YouTube and Spotify playlists in your voice channels.

## Features

- Play songs from YouTube by title or URL
- Play entire Spotify playlists with a single command
- Queue system for multiple songs
- Basic playback controls (pause, resume, skip)
- Clean and simple slash command interface

## Prerequisites

Before setting up RexTunes, make sure you have the following installed:

- Python 3.8 or higher
- [FFmpeg](https://ffmpeg.org/download.html) installed and in your system PATH
- A Discord account and a Discord application with a bot
- A Spotify Developer account for playlist integration

## Installation

1. Clone this repository or download the source code:
   ```
   git clone https://github.com/yourusername/rextunes.git
   cd rextunes
   ```

2. Create a virtual environment (recommended):
   ```
   python -m venv .venv
   ```

3. Activate the virtual environment:
   - Windows: `.venv\Scripts\activate`
   - macOS/Linux: `source .venv/bin/activate`

4. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

5. Create a `.env` file in the project root directory with the following variables:
   ```
   token=YOUR_DISCORD_BOT_TOKEN
   server_id=YOUR_DISCORD_SERVER_ID
   spot_id=YOUR_SPOTIFY_CLIENT_ID
   spot_secret=YOUR_SPOTIFY_CLIENT_SECRET
   ```

## Spotify API Setup

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/)
2. Create a new application
3. Note your Client ID and Client Secret
4. Add these credentials to your `.env` file as `spot_id` and `spot_secret`

## FFmpeg Installation

RexTunes requires FFmpeg to process audio streams. Installation instructions vary by platform:

### Windows
1. Download FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html) or use a package manager like [Chocolatey](https://chocolatey.org/): `choco install ffmpeg`
2. Add FFmpeg to your system PATH

### macOS
1. Install using Homebrew: `brew install ffmpeg`

### Linux
1. Ubuntu/Debian: `sudo apt install ffmpeg`
2. Fedora: `sudo dnf install ffmpeg`
3. Arch Linux: `sudo pacman -S ffmpeg`

## Discord Bot Setup

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application and add a bot
3. Enable the following Privileged Gateway Intents:
   - Message Content Intent
   - Server Members Intent
4. Copy your bot token and add it to your `.env` file
5. Use the following OAuth2 URL to invite your bot to your server:
   ```
   https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=3145728&scope=bot%20applications.commands
   ```
   Replace `YOUR_CLIENT_ID` with your bot's client ID

## Usage

1. Start the bot:
   ```
   python main.py
   ```

2. Use the following slash commands in your Discord server:
   - `/play [song_title]` - Play a song or add it to the queue
   - `/play [spotify_playlist_url]` - Play an entire Spotify playlist
   - `/pause` - Pause the current song
   - `/resume` - Resume playback
   - `/skip` - Skip to the next song in the queue
   - `/queue` - Show the current song queue
   - `/stop` - Stop playback and disconnect the bot

## Multi-Server Support

By default, the bot is configured to work with a single Discord server specified in your `.env` file. To enable multi-server support:

1. Open `tunes.py`
2. Comment out or remove this line:
   ```python
   await tree.sync(guild=discord.Object(id=GUILD_ID))
   ```
3. Uncomment this line:
   ```python
   # await tree.sync()
   ```
4. Remove the `guild=discord.Object(id=GUILD_ID)` parameter from all slash command definitions

## Troubleshooting

- **Bot doesn't respond to commands**: Make sure the bot has the correct permissions and that slash commands are synced
- **Audio doesn't play**: Check that FFmpeg is correctly installed and in your PATH
- **Error finding songs**: Check your internet connection and YouTube search terms
- **Spotify playlists not working**: Verify your Spotify API credentials in the `.env` file

## Acknowledgments

- Uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) for YouTube integration
- Built with [discord.py](https://github.com/Rapptz/discord.py)
- Uses [spotipy](https://github.com/plamere/spotipy) for Spotify integration