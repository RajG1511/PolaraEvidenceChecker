from __future__ import annotations
import os
from fastapi import Header, HTTPException
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

# The key the caller must pass in the X-API-Key header.
# Stored in .env as CHECKER_API_KEY — separate from your OpenAI key.
_VALID_API_KEY = os.environ.get("CHECKER_API_KEY", "")

def verify_api_key(x_api_key: str = Header(...)) -> None:
    """
    FastAPI dependency that validates the X-API-Key header.

    Header(...) means the header is required — FastAPI returns 422
    automatically if it's missing before this function even runs.

    We raise 403 (not 401) because the client is identified but
    not authorized. 401 implies the client needs to authenticate first.
    """
    if not _VALID_API_KEY:
        raise HTTPException(status_code=500, detail="CHECKER_API_KEY not configured on server")
    if x_api_key != _VALID_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")