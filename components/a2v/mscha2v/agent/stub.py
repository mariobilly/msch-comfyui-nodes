"""Phase-2 stub. See mscha2v/agent/README.md for the planned architecture.

Not wired into any node, route, or __init__.py registration -- importing
this module has no side effects, and nothing in mscha2v calls it. It exists
purely so the Phase-2 module boundary is visible in the repo layout ahead of
implementation.
"""

from __future__ import annotations


class AgentNotImplementedError(NotImplementedError):
    """Raised by every stub entry point below -- Phase 2 is not implemented yet."""


def suggest_prompts_for_schedule(schedule_json: str, instruction: str) -> str:
    """Planned Phase-2 entry point: given a Schedule (as JSON) and a natural-
    language instruction ("make the drop hit harder", "add a slow-mo block
    before the chorus"), return an updated Schedule JSON with block
    prompts/timing adjusted accordingly.

    Not implemented. See mscha2v/agent/README.md.
    """
    raise AgentNotImplementedError("mscha2v.agent is a Phase-2 stub; see mscha2v/agent/README.md")


def introspect_graph(workflow_json: str) -> dict:
    """Planned Phase-2 entry point: read the current ComfyUI graph (model,
    resolution, sampler settings already wired to a MschA2V_BeatKSampler) so
    the agent can write prompts that account for what's actually connected,
    instead of guessing.

    Not implemented. See mscha2v/agent/README.md.
    """
    raise AgentNotImplementedError("mscha2v.agent is a Phase-2 stub; see mscha2v/agent/README.md")
