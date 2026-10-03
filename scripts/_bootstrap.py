from pathlib import Path
import sys

SOURCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE_ROOT / 'src'))
from ear_malecns.paths import configure_storage

ROOT = configure_storage()
