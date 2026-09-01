#!/usr/bin/env bash
# Recreate ./venv with Python 3.12 (Anaconda on this machine), not macOS 3.9.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -x /opt/anaconda3/bin/python3.12 ]; then
  PY=/opt/anaconda3/bin/python3.12
elif command -v python3.12 >/dev/null 2>&1; then
  PY="$(command -v python3.12)"
else
  echo "Need Python 3.12. macOS python3 is 3.9 and will fail on spaCy."
  exit 1
fi

echo "Using $($PY -V) from $PY"
rm -rf venv
"$PY" -m venv venv
./venv/bin/python -m pip install --upgrade pip
echo
echo "Activate with:  source venv/bin/activate"
echo "Then:           pip install -r requirements.txt"
echo "python -V should print 3.12.x"
