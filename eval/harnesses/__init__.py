"""
eval/harnesses/ — optional, out-of-tree generation adapters.

Importing this package registers each adapter with the `generate` registry as an
import side-effect (every submodule calls `generate.register_adapter(...)` at the
bottom). `generate.py` imports this package best-effort at the end of its own
module, so the core CLI adapters keep working even if an optional adapter's
dependency (e.g. the `ollama` client) is missing — each adapter imports its heavy
dependency lazily, inside the call, so registration itself never fails.

To add a provider: drop a module here that defines an adapter obeying the
contract `(system, user, model, timeout, params) -> result` and calls
`generate.register_adapter("<provider>", fn)` at import, then add it to the
imports below (and teach `generate._resolve_provider` if it should be routable by
model-string).
"""
from __future__ import annotations

# Best-effort per-adapter import: one adapter's failure must not hide the others.
try:
    from . import ollama  # noqa: F401  (registers the "ollama" provider)
except Exception:
    pass

try:
    from . import talkie_server  # noqa: F401  (registers "talkie" via faithful llama-server)
except Exception:
    pass

try:
    from . import anthropic_api  # noqa: F401  (registers "anthropic" — raw Messages API, clean channel)
except Exception:
    pass
