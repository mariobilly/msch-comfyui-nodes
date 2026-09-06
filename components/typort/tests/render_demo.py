import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import ROOT
from mariotyport.render import render

project = json.loads((ROOT/'examples'/'promo_project.json').read_text(encoding='utf-8'))
result = render(project, ROOT/'artifacts'/('showcase_'+uuid.uuid4().hex[:8]),
                width=1920, height=1080, fps=30, format='MP4 composite', samples=3)
print(json.dumps(result, indent=2))
