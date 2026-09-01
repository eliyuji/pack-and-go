from pathlib import Path
import sys

if sys.version_info < (3, 10):
    raise RuntimeError(
        f"Pack & Go needs Python 3.10+ (found {sys.version.split()[0]}). "
        "macOS python3 is 3.9 and cannot install spaCy. Recreate the venv with:\n"
        "  /opt/anaconda3/bin/python3.12 -m venv venv\n"
        "  source venv/bin/activate"
    )

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
