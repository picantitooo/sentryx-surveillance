"""Stable ASGI entry point used by run_server.py and existing deployments."""
from pathlib import Path
from dotenv import load_dotenv
from app.bootstrap import create_app

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
app = create_app()
