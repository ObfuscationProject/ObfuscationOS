"""Run hosted actual-source multi-user controls, without native execution claims."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    subprocess.run([sys.executable, '-m', 'unittest', '-v',
        'test_native_user_registry', 'test_users_store'], cwd=ROOT / 'tests/tools', check=True)
