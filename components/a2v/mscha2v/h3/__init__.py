"""Adapter layer for the installed MiniMax H3 ComfyUI pack.

adapter.py imports comfy/torch/the H3 pack lazily, inside function bodies
only -- never at module import time -- so this package stays importable in
a plain Python environment (its constants/JSON loading do not require
ComfyUI to be present).
"""
