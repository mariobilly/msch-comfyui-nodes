import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType("mariotyport")
package.__path__ = [str(ROOT)]
sys.modules.setdefault("mariotyport", package)
