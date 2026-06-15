#!/usr/bin/env python3
"""
validate-facet-schema.py — PreToolUse hook for the psychomanteum plugin.

Fires on Write when the target looks like a facet file. Parses YAML frontmatter
and enforces the facet *contract* — NOT its structure.

Design (refactor v0.2.0): "uniform contract, free body." The hook enforces only
the machine-contract every facet must satisfy:
  - required frontmatter fields
  - a well-formed `schema` marker (SemVer shape; no frozen allow-list — pre-1.0
    the repo shifts up freely)
  - a closing epigraph (the one body invariant: every mirror closes with a line
    from its source corpus)
  - gross length sanity (clearly-broken outliers only)

It does NOT enforce section structure. A facet's body is corpus-mirrored and may
take whatever shape the corpus calls for — a numogram, verse, a prose-slab, a
register that refuses genealogy. Guidance on the *functions* a facet should serve
(and the ~150-300 line target band) lives in prompts/facet-schema.md, addressed
to the cipher — guidance that can advise without hardening into a cage.

Enforcement (here) is separated from guidance (the schema doc) on purpose: the
hook is the floor a facet must clear, not the form it must take.

Generic: no proprietary dependencies. Pure stdlib + a vendored mini-YAML
parser fallback if PyYAML is unavailable.
"""

from __future__ import annotations  # PEP 563: keep annotations un-evaluated so the
# 3.10+ union syntax below (`dict | None`) is harmless on Python 3.7-3.9 too.

import json
import re
import sys
from pathlib import Path

# --- The contract (blocking) ---
REQUIRED_FRONTMATTER_FIELDS = ["name", "version", "schema", "generated", "corpus_manifest"]

# Files that legitimately live in a facets/ dir but are NOT facets—the chamber
# index, a readme—carry no facet contract and must not trip the validator.
NON_FACET_BASENAMES = {"facet_index.md", "readme.md", "index.md"}

# Gross sanity bounds ONLY. The *target* band (~150-300 lines) is cipher guidance
# in prompts/facet-schema.md, deliberately NOT enforced here—freeing the body
# means length varies with the corpus. These bounds catch only clearly-broken files.
HARD_MIN_LINES = 40    # below this: almost certainly empty/truncated/broken
HARD_MAX_LINES = 800   # above this: the dense-per-token discipline has collapsed


def is_facet_file(file_path: str, content: str) -> bool:
    """
    A facet file = a facet-shaped path OR facet-shaped FRONTMATTER (a `schema:`
    SemVer marker as a top-level key in the LEADING frontmatter block).

    The frontmatter restriction matters: agent definitions and prompt docs often
    *show* a `schema: 0.2.0` line inside an example code block. Scanning the whole
    file (the old behavior) mis-flagged those as facets. We look only at the
    leading `---...---` block, so a schema example in the body is ignored.
    """
    # Exempt known non-facet files that legitimately live in a facets/ dir
    # (the chamber index, a readme)—they have no facet contract to enforce.
    if Path(file_path).name.lower() in NON_FACET_BASENAMES:
        return False

    path_signals = (
        "/facets/" in file_path
        or "/facet/" in file_path
        or file_path.endswith("-facet.md")
    )
    # Only inspect the leading frontmatter block, not the whole file.
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    content_signal = bool(
        fm_match
        and re.search(r"^schema:\s*['\"]?\d+\.\d+\.\d+", fm_match.group(1), re.MULTILINE)
    )
    return path_signals or content_signal


def parse_frontmatter(content: str) -> tuple[dict | None, str]:
    """
    Extract YAML frontmatter and body. Returns (frontmatter_dict, body) or
    (None, original_content) if no frontmatter.
    """
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if not match:
        return None, content

    fm_text, body = match.group(1), match.group(2)

    try:
        import yaml  # type: ignore

        return yaml.safe_load(fm_text), body
    except ImportError:
        pass

    # Mini-YAML fallback: handles simple key: value pairs + top-level lists.
    fm = {}
    current_list_key = None
    for line in fm_text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - ") or line.startswith("- "):
            if current_list_key is None:
                continue
            fm.setdefault(current_list_key, []).append(line.split("- ", 1)[1].strip().strip("'\""))
            continue
        m = re.match(r"^(\w[\w_]*)\s*:\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip().strip("'\"")
            if val == "":
                current_list_key = key
                fm[key] = []
            else:
                current_list_key = None
                fm[key] = val
        else:
            current_list_key = None
    return fm, body


def validate_facet(file_path: str, content: str) -> list[str]:
    """
    Return a list of CONTRACT violations; empty list = valid.

    Structure is intentionally NOT checked — the body is free. See module docstring.
    """
    errors = []

    fm, body = parse_frontmatter(content)
    if fm is None:
        return ["No YAML frontmatter detected (expected a '---' delimited block at file start)"]

    # 1. Required frontmatter fields (the machine-contract the tooling keys off)
    missing = [f for f in REQUIRED_FRONTMATTER_FIELDS if f not in fm]
    if missing:
        errors.append(f"Missing required frontmatter fields: {', '.join(missing)}")

    # 2. `schema` marker must be a well-formed SemVer. No hard-coded allow-list:
    #    pre-1.0 the repo shifts up freely; we validate shape, not a frozen set.
    if "schema" in fm and not re.match(r"^\d+\.\d+\.\d+", str(fm["schema"])):
        errors.append(f"Malformed 'schema' marker: '{fm['schema']}' (expected SemVer, e.g. 0.2.0)")

    # 3. Closing epigraph—the one body invariant. Every mirror closes with a
    #    line from its source corpus, italicized, in the last ~10 lines.
    last_lines = "\n".join(content.splitlines()[-10:])
    if not re.search(r"^\s*[*_][^*_].+[*_]\s*$", last_lines, re.MULTILINE):
        errors.append(
            "Missing closing epigraph (an italicized quote from the source, in the last ~10 lines)"
        )

    # 4. Gross length sanity—NOT the target band (that's cipher guidance), just
    #    a guard against clearly-broken files.
    line_count = len(content.splitlines())
    if line_count < HARD_MIN_LINES:
        errors.append(f"Facet implausibly short: {line_count} lines (hard floor {HARD_MIN_LINES}).")
    if line_count > HARD_MAX_LINES:
        errors.append(f"Facet implausibly long: {line_count} lines (hard ceiling {HARD_MAX_LINES}).")

    return errors


def main():
    """
    PreToolUse hook contract:
      Input (stdin): JSON with `tool_name`, `tool_input` (file_path + content for Write).
      Output (stdout): {"decision": "block", "reason": "..."} to block; nothing to allow.
    """
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # can't read payload — fail-open

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    file_path = tool_input.get("file_path", "")

    if tool_name == "Write":
        content = tool_input.get("content", "")
    elif tool_name in ("Edit", "MultiEdit"):
        # Documented relief valve: hand-edits to a facet are TRUSTED and bypass
        # the contract check. The enforced path is the cipher's Write; a human
        # tuning a bound facet should not have to satisfy the validator mid-edit.
        # Re-running inscribe/attune (a Write) re-checks the contract.
        sys.exit(0)
    else:
        sys.exit(0)

    if not is_facet_file(file_path, content):
        sys.exit(0)

    errors = validate_facet(file_path, content)
    if not errors:
        sys.exit(0)

    response = {
        "decision": "block",
        "reason": (
            f"psychomanteum: facet CONTRACT validation failed for {file_path}:\n"
            + "\n".join(f"  - {e}" for e in errors)
            + "\n\nThe body is free — any structure the corpus calls for is fine; only the "
            "contract is enforced. Fix the violation(s) and retry. "
            "See ${CLAUDE_PLUGIN_ROOT}/prompts/facet-schema.md for the contract + function guidance."
        ),
    }
    print(json.dumps(response))
    sys.exit(0)


if __name__ == "__main__":
    main()