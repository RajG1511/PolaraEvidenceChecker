from __future__ import annotations
import json
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, Depends, HTTPException
from fastapi.responses import JSONResponse

from api.dependencies import verify_api_key
from polara_checker.extraction import extract_text
from polara_checker.scorer import scoreDocument

app = FastAPI(
    title="Polara Evidence Quality Checker",
    version="1.0.0",
)

# Controls are loaded once at startup into memory.
# This avoids hitting disk on every request.
_CONTROLS_DIR = Path(__file__).resolve().parent.parent / "controls"
_controls_cache: dict[str, dict] = {}

def _load_control(control_id: str) -> dict:
    """
    Load a control JSON file, using an in-memory cache.

    On first call for a given control_id, reads from disk.
    On subsequent calls, returns the cached dict.
    This means the embedding vectors (which are large) are only
    deserialized once per process lifetime.
    """
    if control_id not in _controls_cache:
        path = _CONTROLS_DIR / f"{control_id}.json"
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Control '{control_id}' not found"
            )
        with open(path, "r", encoding="utf-8") as f:
            _controls_cache[control_id] = json.load(f)
    return _controls_cache[control_id]


@app.get("/health")
def health_check():
    """
    Simple liveness probe.
    Docker and load balancers use this to know the container is up.
    No auth required — it contains no sensitive information.
    """
    return {"status": "ok"}


@app.post("/api/v1/check", dependencies=[Depends(verify_api_key)])
async def check_evidence(
    file:       UploadFile = File(...),
    control_id: str        = Form(...),
):
    """
    Main endpoint. Accepts a multipart form with:
      - file:       the uploaded evidence document (PDF, DOCX, TXT, PNG)
      - control_id: which SOC 2 control to score against (e.g. "CC6.1")

    Returns the full scoring result as JSON.

    We write the upload to a temp file because extractText() expects
    a file path, not a byte stream. tempfile.NamedTemporaryFile with
    delete=False gives us a path we can pass around, then we clean up
    manually in the finally block.
    """
    # Validate control exists before doing any expensive work
    control = _load_control(control_id)

    # Write upload to a temp file so extractText can work with it
    suffix = Path(file.filename).suffix.lower() if file.filename else ".bin"
    tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        # Run the full pipeline
        document_text = extract_text(tmp_path)

        if not document_text.strip():
            raise HTTPException(
                status_code=422,
                detail="Could not extract text from the uploaded file"
            )

        result = scoreDocument(document_text, control)

    finally:
        # Always clean up the temp file — even if an exception occurred
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)

    return JSONResponse(content=result)