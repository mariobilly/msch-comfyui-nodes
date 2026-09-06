"""ComfyUI-CodeMatrix — turn a video into green ASCII / binary 'code' art."""

from .code_matrix import CodeMatrixASCII

NODE_CLASS_MAPPINGS = {
    "CodeMatrixASCII": CodeMatrixASCII,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CodeMatrixASCII": "Code Matrix (ASCII)",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
