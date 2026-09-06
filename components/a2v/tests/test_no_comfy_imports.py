"""Mechanically enforces the "mscha2v/core/ has zero ComfyUI/torch imports"
constraint (see mscha2v/core/__init__.py) instead of relying on manual review.
"""

from __future__ import annotations

from pathlib import Path

FORBIDDEN_SUBSTRINGS = ("import torch", "import comfy", "from comfy", "from torch")

_CORE_DIR = Path(__file__).resolve().parent.parent / "mscha2v" / "core"


def test_core_modules_have_no_comfy_or_torch_imports():
    offenders = []
    for path in sorted(_CORE_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if any(stripped.startswith(s) or f" {s}" in stripped for s in FORBIDDEN_SUBSTRINGS):
                offenders.append(f"{path.name}: {stripped}")
    assert not offenders, "mscha2v/core/*.py must have zero ComfyUI/torch imports:\n" + "\n".join(offenders)
