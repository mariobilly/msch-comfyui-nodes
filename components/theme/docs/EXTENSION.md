# Theme extension

This package registers `msch.theme` in the ComfyUI frontend. It has no graph inputs, graph outputs or image renderer.

It matches node definitions whose Python module is an `msch-*` custom-node package, or whose node name starts with `msch` or `mario`. Its palette uses carbon `#0B0D0E`, bone `#E8E0CF`, steel `#344B5C`, espresso `#56382D`, ochre `#C58A32` and acid `#C7F432`.

Install a visual package such as [MSCH Code Matrix](https://github.com/mariobilly/msch-code-matrix), install this theme, restart ComfyUI and refresh the browser. Load that package's demo workflow and add a new node if an existing card has retained its old appearance. The result is a change to node-card styling in the editor, not to the rendered video.

The extension was checked for syntax and import registration. Its appearance has not been validated against every frontend renderer. No screenshot in this repository is presented as a verified live UI capture.
