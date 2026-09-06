# MSCH MCP Bridge

Local ComfyUI browser bridge for changing widget values, setting node modes and reading the current graph.

This component is included in the **[MSCH Nodes pack](../../README.md)**. Install the pack once; no separate installation is needed.

[Full node reference](docs/NODES.md) · [Workflows and outputs](examples/README.md) · [Installation and optional dependencies](../../README.md#installation)

This is an interface extension with zero graph nodes. It supplies HTTP routes and a browser event bridge; it is not a standalone MCP protocol server. Routes inherit access to your ComfyUI server and do not add their own authentication. The browser must be connected for graph updates and edits.
