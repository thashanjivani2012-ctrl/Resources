"""Start the standalone Discord bot from this folder."""

from pathlib import Path
import runpy
import sys

from dotenv import load_dotenv

folder = Path(__file__).resolve().parent
load_dotenv(folder / ".env", override=False)
sys.path.insert(0, str(folder))
runpy.run_path(str(folder / "bot.py"), run_name="__main__")
