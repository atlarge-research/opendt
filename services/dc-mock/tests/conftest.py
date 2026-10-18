import sys
from pathlib import Path

# services/dc-mock, for `import dc_mock`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
