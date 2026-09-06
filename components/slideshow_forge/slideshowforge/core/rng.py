"""Seeded weighted-choice + guardrail-driven rejection sampler.

All randomness in SlideshowForge flows through a single `random.Random(seed)`
instance, consumed in one fixed order (see timeline_builder.py). This module
only implements the picking mechanics; it never creates its own Random().
"""

MAX_REJECTION_RETRIES = 5

# Guardrails are relaxed in this priority order when a pool is exhausted
# (earliest relaxed first). Keep this list in sync with the guardrail keys
# used in presets.py "guardrails" dicts.
GUARDRAIL_RELAXATION_ORDER = [
    "no_immediate_repeat_transition",
    "no_immediate_repeat_motion",
    "max_consecutive_same_type",
]


def weighted_choice(rng, pool: list):
    """Pick one entry from a list of {"weight": w, ...} dicts."""
    weights = [entry["weight"] for entry in pool]
    return rng.choices(pool, weights=weights, k=1)[0]


def _passes_guardrails(candidate_type: str, history: list, guardrails: dict, active_guardrails: set) -> bool:
    if not history:
        return True

    last = history[-1]

    if "no_immediate_repeat_motion" in active_guardrails and guardrails.get("no_immediate_repeat_motion"):
        if last.get("motion_type") is not None and candidate_type == last.get("motion_type"):
            return False

    if "no_immediate_repeat_transition" in active_guardrails and guardrails.get("no_immediate_repeat_transition"):
        if last.get("transition_type") is not None and candidate_type == last.get("transition_type"):
            return False

    if "max_consecutive_same_type" in active_guardrails:
        max_run = guardrails.get("max_consecutive_same_type")
        if max_run:
            run = 0
            for h in reversed(history):
                h_type = h.get("motion_type") or h.get("transition_type")
                if h_type == candidate_type:
                    run += 1
                else:
                    break
            if run >= max_run:
                return False

    return True


def pick_with_guardrails(rng, pool: list, history: list, guardrails: dict, field: str):
    """Weighted-pick a pool entry, rejecting candidates that violate guardrails.

    `field` is "motion_type" or "transition_type" and selects which history
    key the guardrails check against. On repeated rejection, guardrails are
    relaxed in GUARDRAIL_RELAXATION_ORDER rather than looping forever.
    """
    active_guardrails = set(guardrails.keys())

    while True:
        local_pool = list(pool)
        for _ in range(MAX_REJECTION_RETRIES):
            if not local_pool:
                break
            choice = weighted_choice(rng, local_pool)
            check_history = [{field: h.get(field)} for h in history]
            if _passes_guardrails(choice["type"], check_history, guardrails, active_guardrails):
                return choice
            local_pool = [c for c in local_pool if c is not choice]

        # Pool exhausted under current guardrails: relax one and retry.
        relaxed_any = False
        for key in GUARDRAIL_RELAXATION_ORDER:
            if key in active_guardrails:
                active_guardrails.discard(key)
                relaxed_any = True
                break
        if not relaxed_any:
            # Nothing left to relax; accept an unguarded weighted pick.
            return weighted_choice(rng, pool)


def sample_range(rng, lo: float, hi: float) -> float:
    if lo == hi:
        return lo
    return rng.uniform(lo, hi)
