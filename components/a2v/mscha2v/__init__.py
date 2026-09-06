"""mscha2v package root.

Node registration (NODE_CLASS_MAPPINGS) and server-route wiring live in the
repo root's __init__.py, not here -- so that `import mscha2v.core...` (and
`import mscha2v.h3...`) stay usable from a plain pytest environment with no
ComfyUI installed. See mscha2v/core/__init__.py.
"""
