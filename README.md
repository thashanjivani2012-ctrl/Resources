# Resources Managament

This folder is the standalone Discord bot and clothing showcase command.
It does not load `bot.py` or settings from Virtual-Designs-Management.

## Setup on Windows

```powershell
cd "Resources Managament"
copy .env.example .env
# Open .env and replace both values before starting the bot.
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

Put the Discord bot token in `.env` as `DISCORD_TOKEN`. Do not share that file.
Upload this entire folder (including `bot.py`, `clothing_showcase.py`, and
`assets`) to your hosting service. Set the host startup command to
`python run.py` or `py run.py`.

## Deploy on Railway

1. Create a Railway project and deploy this folder as a service.
2. Set `DISCORD_TOKEN` in the service's **Variables**. Optionally set
   `DISCORD_GUILD_ID` to sync commands immediately to one server.
3. Railway will use `railway.toml` and start the worker with `python run.py`.
   Do not add a web server or HTTP health check; this is a Discord gateway
   worker.

Railway's local filesystem is ephemeral. The bot will run without a volume,
but saved showcase backgrounds and settings can be lost when the service is
redeployed. Attach a Railway volume for persistent storage if those settings
must survive redeployments.

### Log in from Windows

The Railway CLI is optional, but it lets you deploy and manage the service
from PowerShell. Install Node.js 16 or newer, then open a new PowerShell
window and run:

```powershell
npm install --global @railway/cli
railway login
railway whoami
```

`railway login` opens Railway's browser sign-in flow. After signing in, run
these commands from this folder to create or select a project and deploy:

```powershell
railway init
railway up
```

Never put a Railway API token or the Discord token in source control. The
browser login stores the CLI credential locally; use `railway logout` on a
shared computer.

## Clothing commands

- `/showcase clothing full`: upload exactly `shirt1`, `pants1`, `shirt2`,
  `shirt3`, `pants2`, and `pants3`. The optional `type` is **Portrait** by
  default and can be changed to **Landscape**.
- `/showcase clothing single`: upload `shirt` and `pants`. The optional `type`
  is **Portrait** by default and can be changed to **Landscape**.
- `/showcase background`: managers can upload a default background or provide
  an HTTPS image URL. Run it with no image or URL to clear the default.

The generated image is sent as `clothing-showcase.png`. The bot needs
`View Channels`, `Send Messages`, `Attach Files`, and `Use Application Commands`.

## Files to upload

Do upload: `bot.py`, `clothing_showcase.py`, `run.py`,
`requirements.txt`, `.env`, and `assets/`.

Do not upload: `.venv/`, `__pycache__/`, or any file containing a token other
than the private `.env` file.
