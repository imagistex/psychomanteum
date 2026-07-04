#!/usr/bin/env python3
"""
eval/test_scry.py — tests for multi-model SCRY.

Covers the two things the R4 build must get right, WITHOUT any real model or agent
(generate() is monkeypatched with a deterministic fake, so this proves the
cross-model orchestration with zero spend and runs in CI):

  1. THE R4 NO-COLLISION PLUMBING. scry.generate_for_model writes each model into
     its OWN per-model dir, so two models never overwrite each other — and a
     characterization test shows the naive single-file path DOES collide
     ("last model wins"), documenting why per-model dirs exist.
  2. THE DUAL-SCHEMA AGGREGATOR. scry_aggregate.read_dashboard handles BOTH the
     current (headline.*) and legacy (signals.*) dashboard shapes, the verdict
     gate, fingerprint-mismatch detection, mixed-capture warnings, and the
     self-perplexity roll-up — plus the driver persisting gen_meta.

Run:  python eval/test_scry.py
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import generate                       # noqa: E402
import generation_driver             # noqa: E402
import scry                          # noqa: E402
import scry_aggregate as agg         # noqa: E402
from harnesses import ollama as ol   # noqa: E402

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LEGACY_DASH = os.path.join(_REPO, "archive", "eval-runs",
                            "ccru-acolyte-lean-2026-05-31", "dashboard.json")

BATTERY = {"probes": [
    {"id": "anchor-loss", "source": "anchor", "keyword": "loss",
     "prompt": "Describe loss.", "content_distance": 0.4},
    {"id": "cd-sewer", "source": "cross-domain", "keyword": "sewer",
     "prompt": "Describe a sewer.", "content_distance": 0.9},
]}


def _fake_generate(system, user, model, timeout=180, params=None):
    """Deterministic: output carries the MODEL string (so cross-contamination is
    detectable) + a per-condition gen_meta perplexity (facet/distractor lower than
    baseline) so the driver-persist + self-perplexity paths are exercised."""
    res = generate._result(("[%s] %s" % (model, user)).strip(), model,
                           "fake-local", True, None, params)
    res["gen_meta"] = {"perplexity": (3.0 if (system or "").strip() else 4.0), "n_tokens": 5}
    return res


def _current_dashboard(model, lens, voice, control="clean", cell="surprise"):
    return {"facet_name": "foucauldian", "target_model": model,
            "capture_method": "fake-local", "tier": "lean",
            "negative_control_verdict": control,
            "headline": {"lens_transfer": {"accuracy": 0.8, "enactment": 0.7, "lens_transfer": lens},
                         "pairwise_voice": {"voice_winrate": voice}},
            "surprise": {"cell": cell},
            "surface_checks": {"perplexity_drop": "unavailable"}}


class ScryTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="scry-test-")
        self.battery = os.path.join(self.tmp, "battery.json")
        with open(self.battery, "w") as fh:
            json.dump(BATTERY, fh)
        self.facet = os.path.join(self.tmp, "facet.md")
        self.distractor = os.path.join(self.tmp, "distractor.md")
        with open(self.facet, "w") as fh:
            fh.write("FACET: the lineage's operation.\n")
        with open(self.distractor, "w") as fh:
            fh.write("DISTRACTOR: a different lineage.\n")
        self._orig_generate = generate.generate
        generate.generate = _fake_generate

    def tearDown(self):
        generate.generate = self._orig_generate
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _gen_model(self, name, model):
        return scry.generate_for_model(
            run_dir=self.tmp,
            model_entry={"name": name, "model": model},
            facet_path=self.facet, distractor_path=self.distractor,
            battery_path=self.battery, tier="lean",
            facet_name="foucauldian", distractor_facet="distractor")


# ============================================================================
# 1. R4 — no collision across models
# ============================================================================

class TestNoCollision(ScryTestBase):
    def test_per_model_dirs_are_separate(self):
        self._gen_model("alpha", "fake:alpha")
        self._gen_model("beta", "fake:beta")
        pa = os.path.join(self.tmp, "alpha", "generations.json")
        pb = os.path.join(self.tmp, "beta", "generations.json")
        self.assertTrue(os.path.exists(pa) and os.path.exists(pb))
        a = json.load(open(pa)); b = json.load(open(pb))
        self.assertEqual(a["target_model"], "fake:alpha")
        self.assertEqual(b["target_model"], "fake:beta")
        # every alpha cell carries alpha's model string; NONE carries beta's.
        a_blob = json.dumps(a)
        self.assertIn("[fake:alpha]", a_blob)
        self.assertNotIn("[fake:beta]", a_blob)

    def test_both_files_have_all_cells(self):
        self._gen_model("alpha", "fake:alpha")
        self._gen_model("beta", "fake:beta")
        for name in ("alpha", "beta"):
            g = json.load(open(os.path.join(self.tmp, name, "generations.json")))
            # 2 probes x 3 conditions = 6 captured cells, all ok
            cells = [c for p in g["probes"] for c in p["generations"].values()]
            self.assertEqual(len(cells), 6)
            self.assertTrue(all(c["ok"] for c in cells))

    def test_naive_shared_path_collides(self):
        """Characterization: pointing TWO models at ONE generations.json drops the
        first (resume invalidates other-model cells). This is the bug per-model
        dirs prevent — kept as a guardrail so the design rationale is testable."""
        shared = os.path.join(self.tmp, "shared.json")
        generation_driver.run_battery(self.battery, self.facet, self.distractor,
                                      shared, model="fake:alpha")
        generation_driver.run_battery(self.battery, self.facet, self.distractor,
                                      shared, model="fake:beta")
        final = json.load(open(shared))
        self.assertEqual(final["target_model"], "fake:beta")
        self.assertNotIn("[fake:alpha]", json.dumps(final))  # alpha lost — the collision


# ============================================================================
# 2. Driver persists gen_meta + params (so logprobs/perplexity survive)
# ============================================================================

class TestGenMetaPersisted(ScryTestBase):
    def test_gen_meta_in_cells(self):
        self._gen_model("alpha", "fake:alpha")
        g = json.load(open(os.path.join(self.tmp, "alpha", "generations.json")))
        facet_cell = g["probes"][0]["generations"]["facet"]
        self.assertIn("gen_meta", facet_cell)
        self.assertEqual(facet_cell["gen_meta"]["perplexity"], 3.0)


# ============================================================================
# 3. Manifest + fingerprint
# ============================================================================

class TestManifest(ScryTestBase):
    def test_fingerprint_and_roster(self):
        roster = [{"name": "alpha", "model": "fake:alpha", "provider": "claude", "contaminated": False},
                  {"name": "beta", "model": "fake:beta", "provider": "claude", "contaminated": False}]
        out, manifest = scry.write_manifest(
            run_dir=self.tmp, facet_name="foucauldian", facet_path=self.facet,
            distractor_facet="distractor", distractor_path=self.distractor,
            battery_path=self.battery, tier="lean", battery_spec="describe",
            roster=roster, judge_model="opus", params=None)
        self.assertTrue(os.path.exists(out))
        self.assertEqual(manifest["n_probes"], 2)
        self.assertEqual(manifest["battery_fingerprint"], agg.fingerprint_probes(BATTERY["probes"]))
        self.assertEqual(manifest["judge"]["model"], "opus")
        self.assertEqual(manifest["cost_estimate"]["total_generations"], 2 * 2 * 3)


# ============================================================================
# 4. Dual-schema reader + verdict gate (pure)
# ============================================================================

class TestDashboardReader(unittest.TestCase):
    def test_legacy_archive_dashboard(self):
        d = json.load(open(_LEGACY_DASH))
        r = agg.read_dashboard(d)
        self.assertEqual(r["schema"], "legacy")
        self.assertIsNone(r["steer_to_region"])          # legacy has no lens composite
        self.assertIn("steer_to_region", r["missing"])
        self.assertIsNotNone(r["voice_winrate"])         # voice extracted from signals.*
        self.assertEqual(r["negative_control"], "clean")

    def test_current_schema_dashboard(self):
        r = agg.read_dashboard(_current_dashboard("m", 0.74, 0.66))
        self.assertEqual(r["schema"], "current")
        self.assertEqual(r["steer_to_region"], 0.74)
        self.assertEqual(r["voice_winrate"], 0.66)
        self.assertEqual(r["missing"], [])

    def test_unknown_schema(self):
        r = agg.read_dashboard({"facet_name": "x"})
        self.assertEqual(r["schema"], "unknown")
        self.assertIsNone(r["steer_to_region"])

    def test_verdict_gate(self):
        self.assertEqual(agg.verdict(0.9, "clean"), "cast")
        self.assertEqual(agg.verdict(0.5, "clean"), "half-cast")
        self.assertEqual(agg.verdict(0.1, "clean"), "mute")
        self.assertEqual(agg.verdict(0.9, "confounded"), "uninterpretable")
        self.assertEqual(agg.verdict(0.9, None), "uninterpretable")
        self.assertEqual(agg.verdict(None, "clean"), "n/a")

    def test_self_perplexity(self):
        gens = {"probes": [
            {"generations": {"facet": {"gen_meta": {"perplexity": 3.0}},
                             "baseline": {"gen_meta": {"perplexity": 4.0}}}},
            {"generations": {"facet": {"gen_meta": {"perplexity": 3.0}},
                             "baseline": {"gen_meta": {"perplexity": 4.0}}}},
        ]}
        sp = agg._self_perplexity(gens)
        self.assertEqual(sp["facet"], 3.0)
        self.assertEqual(sp["baseline"], 4.0)
        self.assertEqual(sp["facet_minus_baseline"], -1.0)


# ============================================================================
# 5. End-to-end aggregation
# ============================================================================

class TestAggregate(ScryTestBase):
    def _build_run(self, controls=("clean", "clean"), tamper_beta_battery=False):
        roster = [{"name": "alpha", "model": "fake:alpha", "provider": "ollama", "contaminated": False},
                  {"name": "beta", "model": "fake:beta", "provider": "ollama", "contaminated": False}]
        scry.write_manifest(run_dir=self.tmp, facet_name="foucauldian", facet_path=self.facet,
                            distractor_facet="distractor", distractor_path=self.distractor,
                            battery_path=self.battery, tier="lean", battery_spec="describe",
                            roster=roster, judge_model="opus", params=None)
        self._gen_model("alpha", "fake:alpha")
        self._gen_model("beta", "fake:beta")
        # stub dashboards: alpha casts, beta mutes
        json.dump(_current_dashboard("fake:alpha", 0.80, 0.70, controls[0]),
                  open(os.path.join(self.tmp, "alpha", "dashboard.json"), "w"))
        json.dump(_current_dashboard("fake:beta", 0.15, 0.10, controls[1]),
                  open(os.path.join(self.tmp, "beta", "dashboard.json"), "w"))
        if tamper_beta_battery:
            gp = os.path.join(self.tmp, "beta", "generations.json")
            g = json.load(open(gp))
            g["probes"][0]["prompt"] = "Describe TAMPERED."
            json.dump(g, open(gp, "w"))

    def test_end_to_end_clean(self):
        self._build_run()
        out = agg.aggregate(self.tmp)
        self.assertEqual(len(out["rows"]), 2)
        by = {r["name"]: r for r in out["rows"]}
        self.assertEqual(by["alpha"]["verdict"], "cast")
        self.assertEqual(by["beta"]["verdict"], "mute")
        self.assertTrue(all(r["fingerprint_ok"] for r in out["rows"]))
        self.assertEqual(len(out["constellation"]["spectrum"]), 2)
        self.assertEqual(len(out["constellation"]["orbit"]), 2)
        # alpha generated under the fake adapter -> self-perplexity rolled up
        self.assertIn("self_perplexity", by["alpha"])
        # no fingerprint/mixed-capture/control warnings in the clean case
        joined = " ".join(out["warnings"])
        self.assertNotIn("MISMATCH", joined)
        self.assertNotIn("MIXED", joined)
        self.assertTrue(out["interpretive_voice"])

    def test_confounded_control_uninterpretable(self):
        self._build_run(controls=("confounded", "clean"))
        out = agg.aggregate(self.tmp)
        by = {r["name"]: r for r in out["rows"]}
        self.assertEqual(by["alpha"]["verdict"], "uninterpretable")
        self.assertTrue(any("uninterpretable" in w for w in out["warnings"]))

    def test_fingerprint_mismatch_warns(self):
        self._build_run(tamper_beta_battery=True)
        out = agg.aggregate(self.tmp)
        by = {r["name"]: r for r in out["rows"]}
        self.assertFalse(by["beta"]["fingerprint_ok"])
        self.assertTrue(any("MISMATCH" in w for w in out["warnings"]))


# ============================================================================
# 6. ollama adapter pure helpers (no live server)
# ============================================================================

class TestOllamaHelpers(unittest.TestCase):
    def test_strip_prefix(self):
        self.assertEqual(ol._strip_prefix("ollama:qwen2.5:7b-instruct"), "qwen2.5:7b-instruct")
        self.assertEqual(ol._strip_prefix("ollama:hf.co/x/talkie:Q4_K_M"), "hf.co/x/talkie:Q4_K_M")
        self.assertEqual(ol._strip_prefix("qwen2.5:7b"), "qwen2.5:7b")  # no prefix -> unchanged

    def test_options_from_params(self):
        o = ol._options_from_params({"temperature": 0.7, "seed": 1, "max_tokens": 256, "ignored": 9})
        self.assertEqual(o, {"temperature": 0.7, "seed": 1, "num_predict": 256})

    def test_aggregate_perplexity(self):
        lp = [{"logprob": -0.5}, {"logprob": -1.5}]   # mean -1.0 -> ppl e^1.0
        out = ol._aggregate_perplexity(lp)
        self.assertEqual(out["n_tokens"], 2)
        self.assertEqual(out["mean_logprob"], -1.0)
        self.assertAlmostEqual(out["perplexity"], 2.7183, places=3)
        self.assertIsNone(ol._aggregate_perplexity([]))

    def test_registered_and_routed(self):
        self.assertIn("ollama", generate._ADAPTERS)
        self.assertEqual(generate._resolve_provider("ollama:anything"), "ollama")


# ============================================================================
# 7. Roster dir-collision guard (the R4 collision, sideways via slug collapse)
# ============================================================================

class TestRosterCollision(unittest.TestCase):
    def test_slug_collision_raises(self):
        with self.assertRaises(ValueError):
            scry.resolve_roster(["ollama:foo/bar", "ollama:foo:bar"])  # both -> ollama-foo-bar

    def test_case_insensitive_collision_raises(self):
        with self.assertRaises(ValueError):
            scry.resolve_roster(["ollama:Qwen", "ollama:qwen"])  # same dir on APFS/Windows

    def test_distinct_names_ok(self):
        r = scry.resolve_roster(["qwen2.5", "ollama:mistral:7b"])
        self.assertEqual(len(r), 2)


# ============================================================================
# 8. Interpretive voice + numeric coercion + overflow (honesty/robustness)
# ============================================================================

class TestInterpretiveAndCoercion(unittest.TestCase):
    def test_interpretive_excludes_uninterpretable(self):
        rows = [{"name": "alpha", "steer_to_region": 0.9, "verdict": "uninterpretable"},
                {"name": "beta", "steer_to_region": 0.5, "verdict": "half-cast"}]
        v = agg._interpretive_voice(rows)
        self.assertIn("beta", v)
        self.assertNotIn("alpha casts truest", v)   # never crown an untrusted row

    def test_interpretive_none_interpretable(self):
        rows = [{"name": "a", "steer_to_region": 0.9, "verdict": "uninterpretable"}]
        self.assertIn("glass stays dark", agg._interpretive_voice(rows))

    def test_string_steer_coerced_not_crash(self):
        r = agg.read_dashboard({"headline": {"lens_transfer": {"lens_transfer": "0.8"},
                                             "pairwise_voice": {"voice_winrate": "bad"}},
                                "negative_control_verdict": "clean"})
        self.assertEqual(r["steer_to_region"], 0.8)     # numeric string coerced
        self.assertIsNone(r["voice_winrate"])           # garbage -> None
        self.assertEqual(agg.verdict(r["steer_to_region"], "clean"), "cast")  # no TypeError

    def test_perplexity_overflow_guarded(self):
        out = ol._aggregate_perplexity([{"logprob": -1e9}])  # exp(1e9) overflows
        self.assertNotIn("perplexity", out)             # skipped, never raises
        self.assertEqual(out["n_tokens"], 1)


# ============================================================================
# 9. Aggregator robustness: one corrupt file must not kill the whole run
# ============================================================================

class TestAggregateRobust(ScryTestBase):
    def test_corrupt_dashboard_skips_not_crashes(self):
        roster = [{"name": "alpha", "model": "fake:alpha", "provider": "ollama", "contaminated": False},
                  {"name": "beta", "model": "fake:beta", "provider": "ollama", "contaminated": False}]
        scry.write_manifest(self.tmp, "foucauldian", self.facet, "distractor", self.distractor,
                            self.battery, "lean", "describe", roster, "opus", None)
        self._gen_model("alpha", "fake:alpha")
        self._gen_model("beta", "fake:beta")
        json.dump(_current_dashboard("fake:alpha", 0.80, 0.70, "clean"),
                  open(os.path.join(self.tmp, "alpha", "dashboard.json"), "w"))
        with open(os.path.join(self.tmp, "beta", "dashboard.json"), "w") as fh:
            fh.write("{ this is not valid json")
        out = agg.aggregate(self.tmp)            # must NOT raise
        by = {r["name"]: r for r in out["rows"]}
        self.assertEqual(by["alpha"]["verdict"], "cast")     # alpha still scored
        self.assertEqual(by["beta"]["schema"], "unreadable")
        self.assertTrue(any("unreadable" in w for w in out["warnings"]))

    def test_unverified_provenance_not_crowned(self):
        # dashboard present (would cast) but generations.json MISSING -> the battery
        # is unverifiable -> the row must NOT be crowned or plotted.
        roster = [{"name": "alpha", "model": "fake:alpha", "provider": "ollama", "contaminated": False}]
        scry.write_manifest(self.tmp, "foucauldian", self.facet, "distractor", self.distractor,
                            self.battery, "lean", "describe", roster, "opus", None)
        os.makedirs(os.path.join(self.tmp, "alpha"), exist_ok=True)
        json.dump(_current_dashboard("fake:alpha", 0.9, 0.8, "clean"),
                  open(os.path.join(self.tmp, "alpha", "dashboard.json"), "w"))
        # deliberately NO generations.json
        out = agg.aggregate(self.tmp)
        a = out["rows"][0]
        self.assertIsNone(a["fingerprint_ok"])
        self.assertEqual(a["verdict"], "uninterpretable")   # unverifiable -> not a cast
        self.assertEqual(out["constellation"]["spectrum"], [])
        self.assertIn("glass stays dark", out["interpretive_voice"])


# ============================================================================
# 10. ollama adapter call path (mocked client — no live server)
# ============================================================================

class _Resp:
    def __init__(self, d):
        self._d = d
    def model_dump(self):
        return self._d


class TestOllamaMocked(unittest.TestCase):
    def _install_fake(self, chat_impl):
        import types
        m = types.ModuleType("ollama")

        class C:
            def __init__(self, *a, **k):
                pass
            def chat(self, **kw):
                return chat_impl(kw)
        m.Client = C
        self._saved = sys.modules.get("ollama")
        sys.modules["ollama"] = m

    def tearDown(self):
        if getattr(self, "_saved", "missing") != "missing":
            if self._saved is not None:
                sys.modules["ollama"] = self._saved
            else:
                sys.modules.pop("ollama", None)

    def test_parsing_and_gen_meta(self):
        def chat(kw):
            assert kw.get("logprobs") is True          # requested by default
            return _Resp({"message": {"content": "  hello  "}, "eval_count": 5,
                          "prompt_eval_count": 10, "eval_duration": 5e8, "done_reason": "stop",
                          "logprobs": [{"logprob": -0.5}, {"logprob": -1.5}]})
        self._install_fake(chat)
        r = ol._generate_ollama("sys", "user", "ollama:m", 60, {"temperature": 0.7})
        self.assertTrue(r["ok"])
        self.assertEqual(r["output"], "hello")          # trimmed
        self.assertEqual(r["capture_method"], "ollama-local")
        gm = r["gen_meta"]
        self.assertEqual(gm["tokens_out"], 5)
        self.assertEqual(gm["tokens_in"], 10)
        self.assertEqual(gm["tok_per_s"], 10.0)
        self.assertEqual(gm["finish"], "stop")
        self.assertAlmostEqual(gm["perplexity"], 2.7183, places=3)

    def test_retry_without_logprobs(self):
        calls = []
        def chat(kw):
            calls.append("logprobs" in kw)
            if "logprobs" in kw:
                raise RuntimeError("server rejects logprobs field")
            return _Resp({"message": {"content": "ok"}})
        self._install_fake(chat)
        r = ol._generate_ollama("", "u", "ollama:m", 60, None)
        self.assertTrue(r["ok"])
        self.assertEqual(r["output"], "ok")
        self.assertEqual(calls, [True, False])          # tried WITH then WITHOUT the kwarg

    def test_empty_output_fails(self):
        self._install_fake(lambda kw: _Resp({"message": {"content": "   "}}))
        r = ol._generate_ollama("", "u", "ollama:m", 60, None)
        self.assertFalse(r["ok"])
        self.assertIn("empty output", r["error"])

    def test_missing_client_returns_error(self):
        self._saved = sys.modules.get("ollama")
        sys.modules["ollama"] = None                    # `import ollama` -> ImportError
        r = ol._generate_ollama("", "u", "ollama:m", 60, None)
        self.assertFalse(r["ok"])
        self.assertIn("not installed", r["error"])

    def test_none_params_recorded_faithfully(self):
        # default (None) params MUST be recorded as None (not {}), or the driver
        # stamps {} and default reruns never resume (_params_match({}, None) fails).
        self._install_fake(lambda kw: _Resp({"message": {"content": "ok"}}))
        self.assertIsNone(ol._generate_ollama("", "u", "ollama:m", 60, None)["params"])
        self.assertEqual(ol._generate_ollama("", "u", "ollama:m", 60, {"seed": 0})["params"],
                         {"seed": 0})


# ============================================================================
# 11. Resume: params in the reuse key + legacy back-compat
# ============================================================================

class TestResume(ScryTestBase):
    def test_changed_params_invalidates(self):
        e = {"name": "alpha", "model": "fake:alpha"}
        common = dict(facet_path=self.facet, distractor_path=self.distractor,
                      battery_path=self.battery, tier="lean",
                      facet_name="f", distractor_facet="d")
        s1 = scry.generate_for_model(self.tmp, e, params={"seed": 0}, **common)
        self.assertEqual(s1["completed"], 6)
        s2 = scry.generate_for_model(self.tmp, e, params={"seed": 0}, **common)
        self.assertEqual(s2["skipped"], 6)              # identical params -> all reused
        s3 = scry.generate_for_model(self.tmp, e, params={"seed": 1}, **common)
        self.assertEqual(s3["skipped"], 0)              # changed params -> regenerated
        self.assertEqual(s3["completed"], 6)

    def test_legacy_cells_without_params_reused(self):
        out = os.path.join(self.tmp, "legacy", "generations.json")
        os.makedirs(os.path.dirname(out))
        legacy = {"probes": [{"id": p["id"], "prompt": p["prompt"], "generations": {
            c: {"output": "old", "ok": True, "model": "fake:leg"}
            for c in ("facet", "baseline", "distractor")}} for p in BATTERY["probes"]]}
        json.dump(legacy, open(out, "w"))
        s = generation_driver.run_battery(self.battery, self.facet, self.distractor, out,
                                          model="fake:leg", params={"seed": 9})
        # legacy cells carry no params -> match anything -> reused, not regenerated
        self.assertEqual(s["skipped"], 6)
        self.assertEqual(s["completed"], 0)


def main():
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    n = result.testsRun
    print("\n[scry] %d/%d passed" % (n - len(result.failures) - len(result.errors), n))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
