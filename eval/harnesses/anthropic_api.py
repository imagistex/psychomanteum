#!/usr/bin/env python3
"""
eval/harnesses/anthropic_api.py — raw Anthropic API adapter (clean channel).

WHY THIS EXISTS. The `claude` CLI adapter is CONTAMINATED: the vendor wrapper
injects hidden system context even under --bare (the verified contamination_caveat
that makes every CLI capture RELATIVE-ONLY). The Messages API gives a true
(system, user) pair — what we author is the ENTIRE prompt. This un-defers the
"paid API/SDK adapters are deferred" note in /psychomanteum-scry and upgrades a
frontier-Claude cell from relative-only to CLEAN capture. Built for the
la-claude far-control question: does a self-authored facet re-summon in a bare
instance of the author's own weights?

ROUTING. Registers as the "anthropic" provider at import time (see
harnesses/__init__.py). Model strings route here via an `anthropic:` prefix:
    "anthropic:claude-fable-5"
    "anthropic:claude-opus-4-8"
Bare "anthropic" resolves to the default model below.

CONTRACT. Identical to ollama.py:
    _generate_anthropic(system, user, model, timeout, params) -> gen._result(...)
optionally AUGMENTED with a compact `gen_meta` (stop_reason + token usage; the
API exposes NO logprobs, so there is no perplexity signal for these cells —
recorded absence, not an oversight).

HONESTY NOTES (design decisions, recorded here so provenance survives us):
  * NO sampling params are ever sent. The Fable 5 / Opus 4.7+ family REJECTS
    temperature/top_p/top_k (400) and thinking config (thinking is always-on;
    the raw chain of thought is never returned). Rather than fork behavior by
    model id, this adapter sends none for ANY model and records `params`
    provenance-only (exactly like the CLI adapters). Only max_tokens is honored
    (an enforced output cap, universally accepted).
  * NO refusal fallbacks, deliberately. The API's server-side fallback would
    transparently re-serve a declined request on a DIFFERENT model — an opus
    answer wearing a fable-5 label inside a far-control cell. Vessel identity
    outranks availability: a refusal is recorded as a FAILED cell, with the
    stop_details category in the error.
  * Empty/whitespace system => the `system` parameter is OMITTED entirely
    (the baseline condition is a truly bare vessel, not an empty-string prompt).
  * THINKING HEADROOM. On always-thinking models (Fable 5 family) `max_tokens`
    bounds thinking + text COMBINED, and the thinking is invisible. A visible
    budget of 200 (the lab's usual num_predict) would yield cells that are all
    hidden reasoning and no text. The requested budget (max_tokens/num_predict
    in `params`) is therefore treated as the VISIBLE budget; _THINKING_HEADROOM
    is added on top of it at request time. Within a model row all three scry
    conditions share identical settings, so per-model verdicts stay fair; the
    cross-model length asymmetry vs num_predict-capped ollama cells is a
    capture-class difference (already surfaced by the aggregator's MIXED
    warning) and is recorded per-cell in gen_meta.
  * Auth: ANTHROPIC_API_KEY via the SDK's default resolution chain. The key
    never appears in results, logs, or this repo.
"""
from __future__ import annotations

import os
import sys
from typing import Dict, Optional

# Put eval/ on sys.path so `import generate` resolves however this is launched
# (mirrors ollama.py's bootstrap).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generate as gen  # noqa: E402

_PROVIDER = "anthropic"
_PREFIX = "anthropic:"
_CAPTURE = "anthropic-api"
_DEFAULT_MODEL = "claude-fable-5"
_DEFAULT_MAX_TOKENS = 1024
_THINKING_HEADROOM = 4096  # see docstring: max_tokens covers invisible thinking too


def _strip_prefix(model: str) -> str:
    """`anthropic:<model-id>` -> `<model-id>`; bare provider -> default model."""
    m = (model or "").strip()
    if m.lower().startswith(_PREFIX):
        m = m.split(":", 1)[1].strip()
    if not m or m.lower() == _PROVIDER:
        return _DEFAULT_MODEL
    return m


def _generate_anthropic(
    system: str,
    user: str,
    model: str,
    timeout: int = 180,
    params: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    # LAZY import so a missing dependency yields a clean per-call error instead of
    # breaking registration (same discipline as the ollama adapter).
    try:
        import anthropic
    except Exception as e:  # pragma: no cover - environment-dependent
        return gen._result(
            "", model, _CAPTURE, False,
            "anthropic sdk unavailable: %s (fix: .venv/bin/pip install anthropic)" % e,
            params,
        )

    model_id = _strip_prefix(model)
    p = params or {}
    # accept either max_tokens (our name) or num_predict (the lab's ollama name)
    try:
        visible_budget = int(p.get("max_tokens") or p.get("num_predict") or _DEFAULT_MAX_TOKENS)
    except (TypeError, ValueError):
        visible_budget = _DEFAULT_MAX_TOKENS
    # thinking headroom: see module docstring — the cap includes invisible thinking
    max_tokens = visible_budget + _THINKING_HEADROOM

    kwargs: Dict[str, object] = {
        "model": model_id,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": user}],
    }
    sys_text = (system or "").strip()
    if sys_text:
        kwargs["system"] = sys_text  # baseline (empty system) omits the param

    try:
        client = anthropic.Anthropic()  # ANTHROPIC_API_KEY / SDK resolution chain
        resp = client.with_options(timeout=float(timeout)).messages.create(**kwargs)
    except anthropic.AuthenticationError as e:
        return gen._result("", model, _CAPTURE, False,
                           "auth failed (set ANTHROPIC_API_KEY): %s" % e, params)
    except anthropic.APIStatusError as e:
        return gen._result("", model, _CAPTURE, False,
                           "api error %s: %s" % (e.status_code, getattr(e, "message", e)), params)
    except anthropic.APIConnectionError as e:
        return gen._result("", model, _CAPTURE, False, "connection error: %s" % e, params)
    except Exception as e:
        return gen._result("", model, _CAPTURE, False,
                           "failed to invoke anthropic api: %s" % e, params)

    stop = getattr(resp, "stop_reason", None)
    if stop == "refusal":
        category = None
        sd = getattr(resp, "stop_details", None)
        if sd is not None:
            category = getattr(sd, "category", None)
        # No fallback BY DESIGN (see module docstring): record the failed cell.
        return gen._result(
            "", model, _CAPTURE, False,
            "refusal (category=%s) — recorded as failed cell; no fallback by design" % category,
            params,
        )

    text = "".join(
        b.text for b in (resp.content or []) if getattr(b, "type", None) == "text"
    ).strip()
    if not text:
        return gen._result("", model, _CAPTURE, False,
                           "empty output (stop_reason=%s)" % stop, params)

    out = gen._result(text, model, _CAPTURE, True, None, params)
    usage = getattr(resp, "usage", None)
    out["gen_meta"] = {
        "stop_reason": stop,
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "response_model": getattr(resp, "model", None),
        # provenance: this adapter NEVER sends sampling knobs (see docstring);
        # `params` above records what was REQUESTED, this records what was SENT.
        "sampling_params_sent": False,
        "visible_budget_requested": visible_budget,
        "max_tokens_sent": max_tokens,
        # no logprobs on the Messages API => no perplexity signal for these cells
        "logprobs_available": False,
    }
    return out


# Register at import time (harnesses/__init__.py imports this module best-effort).
gen.register_adapter(_PROVIDER, _generate_anthropic)
