"""LyricSyncPalette — pick the mosaic colours. Outputs a PALETTE (list of hex).

Has 12 visual colour-swatch slots (the web/ JS turns them into clickable colour
pickers with the OS eyedropper) plus an unlimited multiline hex list. Plug the
`palette` output into the Word Mosaic node's `palette_in`.
"""

from .mosaic import DEFAULT_PALETTE

_SLOT_DEFAULTS = [
    "#FFFFFF", "#7DEFA1", "#5FE39A", "#F25CC1", "#FF74B8", "#63D6F0",
    "#9B5DE5", "#B388F0", "#F5B8D6", "#FFFFFF", "#15151E", "#FFD23F",
]
NUM_SLOTS = 12


def _norm_hex(c):
    c = (c or "").strip()
    if not c:
        return None
    if not c.startswith("#"):
        c = "#" + c
    if len(c) == 4:  # #RGB -> #RRGGBB
        c = "#" + "".join(ch * 2 for ch in c[1:])
    if len(c) == 7:
        try:
            int(c[1:], 16)
            return c.upper()
        except ValueError:
            return None
    return None


class LyricSyncPalette:
    @classmethod
    def INPUT_TYPES(cls):
        req = {"num_colors": ("INT", {"default": 10, "min": 1, "max": NUM_SLOTS,
                                      "tooltip": "How many of the swatches below to use."})}
        for i in range(NUM_SLOTS):
            req[f"color_{i + 1:02d}"] = ("STRING", {"default": _SLOT_DEFAULTS[i]})
        return {
            "required": req,
            "optional": {
                "extra_hex": ("STRING", {"multiline": True, "default": "",
                              "tooltip": "More colours, one #hex per line (unlimited)."}),
                "weight_white": ("INT", {"default": 1, "min": 0, "max": 8,
                              "tooltip": "Extra copies of white added — raises the share of white tiles."}),
            },
        }

    RETURN_TYPES = ("PALETTE", "STRING")
    RETURN_NAMES = ("palette", "palette_csv")
    FUNCTION = "build"
    CATEGORY = "LyricSync"

    def build(self, num_colors, extra_hex="", weight_white=1, **kw):
        cols = []
        for i in range(int(num_colors)):
            c = _norm_hex(kw.get(f"color_{i + 1:02d}", ""))
            if c:
                cols.append(c)
        for line in (extra_hex or "").splitlines():
            c = _norm_hex(line)
            if c:
                cols.append(c)
        if not cols:
            cols = list(DEFAULT_PALETTE)
        cols += ["#FFFFFF"] * int(weight_white)
        return (cols, ",".join(cols))
