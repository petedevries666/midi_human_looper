#!/usr/bin/env python3
"""Reuse D's unchanged output assertions with UI-authored configuration and TEST."""
import os,sys,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
result=subprocess.run([sys.executable,str(root/'tests/test_conductor_execution_jack.py')],cwd=root,env={**os.environ,'CONDUCTOR_BROWSER_AUTHOR':'1'})
raise SystemExit(result.returncode)
