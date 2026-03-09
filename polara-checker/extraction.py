# polara_checker/extraction.py

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import fitz  # PyMuPDF
from docx import Document


# Custom error classes because callers can catch ExtractionError specifically the API endpoint can return a 422 to the user instead of crashing with a 500
class ExtractionError(Exception):
    """
    Raised when a file can't be extracted at all — corrupt file,
    unsupported format, that kind of thing. Not for minor cleanup issues.
    """
    pass

class LowQualityExtractionWarning(Warning):
    """
    Raised as a warning (not an error) when extraction works but the
    output is suspiciously short or garbled. The pipeline still runs,
    but something upstream might be wrong.
    """
    pass

