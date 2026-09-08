#!/usr/bin/env python3
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,'tools/generate_step_fixture.py'],cwd=ROOT,check=True);subprocess.run([sys.executable,'tools/readiness.py'],cwd=ROOT,check=True)
