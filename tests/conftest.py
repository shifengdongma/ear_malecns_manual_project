from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ear_malecns.paths import configure_storage
configure_storage()
