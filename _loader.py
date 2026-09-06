"""Load independent node components and handle migration from separate installs."""
from __future__ import annotations

import importlib
import logging
from pathlib import Path

log = logging.getLogger("msch_nodes")


def legacy_installations(component: dict, roots: list[Path]) -> list[Path]:
    """Only active, directly installed folders count; backups/disabled folders do not."""
    return [root / name for root in roots for name in component["legacy_names"]
            if (root / name / "__init__.py").is_file()]


def load_components(package: str, definitions: list[dict], roots: list[Path], importer=None):
    importer = importer or importlib.import_module
    classes, names, loaded, skipped, errors = {}, {}, [], {}, {}
    for component in definitions:
        key = component["module"]
        legacy = legacy_installations(component, roots)
        if legacy:
            skipped[key] = [str(path) for path in legacy]
            log.warning("MSCH Nodes: using existing %s install; remove/disable the separate pack "
                        "and restart to migrate this component. See MIGRATION.md.", key)
            continue
        try:
            module = importer(f"{package}.components.{key}")
            mapping = module.NODE_CLASS_MAPPINGS
            if set(mapping) != set(component["nodes"]):
                raise ValueError(f"Expected node IDs {component['nodes']}, received {list(mapping)}")
            duplicate = set(classes).intersection(mapping)
            if duplicate:
                raise ValueError(f"Duplicate node IDs: {sorted(duplicate)}")
            display_names = getattr(module, "NODE_DISPLAY_NAME_MAPPINGS", {})
            classes.update(mapping)
            names.update({node: display_names.get(node, node) for node in mapping})
            loaded.append(component)
        except Exception as exc:
            errors[key] = f"{type(exc).__name__}: {exc}"
            log.exception("MSCH Nodes: %s could not load; the other components remain available.", key)
    return classes, names, loaded, skipped, errors
