"""ComfyUI entry point; bare test collection does not initialize the server."""
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = "./web"

if __package__:
    from ._pack import (
        NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS,
        LOADED_COMPONENTS, SKIPPED_COMPONENTS, LOAD_ERRORS,
    )

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
