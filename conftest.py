import sys
from pathlib import Path

# Add the project root to Python's path so pytest can find polara_checker
sys.path.insert(0, str(Path(__file__).parent))