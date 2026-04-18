# F95Tracker

A web-based game library manager and update checker for F95zone games. This is a reimplementation of F95Checker as a web application for use on your local network.

## Features

- 🎮 **Game Library Management**: Track games with metadata (name, version, developer, type, status, tags, score, etc.)
- 🔍 **Game Discovery**: Add games by F95zone URL or search the F95zone database directly
- 🔄 **Update Checking**: Automatic background checks for game updates using the F95Checker cache API
- 📊 **Status Tracking**: Track installed and finished versions, ratings, and notes
- 🏷️ **Organization**: Use labels, filters, and sort options to organize your library
- 🌐 **Local Network Access**: Use from any device on your network via browser
- 🎨 **Dark Theme**: Modern dark UI inspired by the original F95Checker

## Quick Start

### Prerequisites

- Python 3.11+

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start the server:
```bash
# Linux/macOS
./start.sh

# Or manually:
python -m uvicorn app:app --host 0.0.0.0 --port 8000

# Windows
start.bat
```

3. Open in browser:
```
http://localhost:8000
```

### Docker

```bash
docker build -t f95tracker .
docker run -d -p 8000:8000 -v f95tracker_data:/app/data f95tracker
```

### Access from Other Devices

Once running, access from any device on your local network using:
```
http://<your-computer-ip>:8000
```

To find your IP address:
- Windows: Run `ipconfig` in Command Prompt
- Linux/macOS: Run `ifconfig` or `ip addr`

## Usage

### Adding Games

1. Click the **➕** button (or press **N**)
2. Choose method:
   - **By URL**: Paste an F95zone thread URL
   - **Search**: Search F95zone by game title or creator
   - **Custom**: Add non-F95zone games manually

### Managing Your Library

- **List/Grid View**: Toggle between grid and list views
- **Filters**: Filter by status, type, updates, installed, finished, archived
- **Sort**: Sort by date added, name, score, last updated
- **Search**: Real-time search by game name or developer

### Game Details

Click any game to view details and:
- See description, changelog, downloads
- Mark as installed/finished with version tracking
- Rate games (1-5 stars)
- Add personal notes
- View timeline of changes
- Check for updates manually

### Settings

1. **Authentication** (optional but recommended):
   - Log in with F95zone credentials, OR
   - Manually paste cookies from your browser
   - Enables search and full thread access

2. **Refresh Settings**:
   - Auto-refresh interval (0 to disable)
   - Whether to refresh archived/completed games
   - Max concurrent connections

3. **Labels**:
   - Create custom labels with colors
   - Organize games your way

## Data Storage

All data is stored locally in the `data/` folder:
- `data/f95tracker.db` - SQLite database with games, settings, and cookies
- `data/images/` - Downloaded game header images

## Importing from F95Checker

If you have an existing F95Checker installation, you can import your library:

1. Go to **Settings** → **Import from F95Checker**
2. The default path will be auto-detected, or enter the path to your `db.sqlite3`
3. Click **Import**

## Keyboard Shortcuts

- **N** - Open Add Game dialog
- **Escape** - Close modal

## Architecture

### Backend
- **FastAPI** - Modern async web framework
- **SQLite** - Lightweight database (via aiosqlite)
- **httpx** - Async HTTP client for API calls

### Frontend
- **Jinja2 Templates** - Server-side rendering
- **Alpine.js** - Lightweight JavaScript framework
- **HTMX** - AJAX interactions
- **CSS Custom Properties** - Dark theme styling

### APIs Used
- **F95Checker Cache API** (`api.f95checker.dev`) - For fast update checking
- **F95zone API** - For game search and authentication

## Differences from F95Checker Desktop

- **No executable launching** - This is a web app, so game launching is not supported
- **Browser-based** - No desktop GUI, access via browser on any device
- **Simplified authentication** - Store credentials/cookies server-side
- **No tray icon** - Runs as a background service

## Security Notes

- The application binds to all interfaces (`0.0.0.0`) so it's accessible from any device on your network
- F95zone credentials are stored in the local SQLite database
- No user authentication is implemented - anyone on your network can access it
- For privacy, run on a trusted local network only

## Troubleshooting

### Can't connect to F95zone
- Check your internet connection
- Try logging in via Settings
- Check if F95zone is accessible from your browser

### Images not loading
- The game header images are downloaded on first full check
- Images may fail if the original host is unavailable

### Refresh stuck
- Check the browser console for errors
- Restart the server if needed

## License

This is an unofficial fan project. F95zone is a trademark of its respective owners.

## Credits

- Original F95Checker by WillyJL
- F95Checker Cache API (api.f95checker.dev)