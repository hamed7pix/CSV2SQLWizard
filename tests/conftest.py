import sys
from pathlib import Path

# sql_builder.py sits at the repo root, beside CSV2SQLWizard.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
