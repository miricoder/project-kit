"""Tests for the pipeline state engine and its gate logic.

The gate rules are the reason this plugin can be trusted, so they are tested directly:
a gate passes only on a recorded ruling, and a conditional ruling with an open fix does
not pass.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "pipeline" / "scripts"))

import state  # noqa: E402


class StateTestCase(unittest.TestCase):
    """Isolates both pipeline.json and the user-level registry into a temp dir."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self._saved_env = os.environ.get("PROJECT_KIT_REGISTRY")
        os.environ["PROJECT_KIT_REGISTRY"] = str(self.dir / "registry.json")
        self.addCleanup(self._restore)
        self.addCleanup(self.tmp.cleanup)

    def _restore(self):
        if self._saved_env is None:
            os.environ.pop("PROJECT_KIT_REGISTRY", None)
        else:
            os.environ["PROJECT_KIT_REGISTRY"] = self._saved_env

    def fresh(self, mode="auto", max_usd=25.0):
        return state.new_state("demo", mode, max_usd)


class NewStateTest(StateTestCase):
    def test_every_phase_and_gate_starts_unstarted(self):
        st = self.fresh()
        self.assertEqual(set(st["phases"]), set(state.PHASES))
        self.assertEqual(set(st["gates"]), set(state.GATES))
        self.assertTrue(all(p["status"] == "not started" for p in st["phases"].values()))

    def test_rejects_unknown_mode(self):
        with self.assertRaises(state.StateError):
            state.new_state("demo", "turbo")

    def test_round_trip_through_disk(self):
        st = self.fresh()
        state.set_phase(st, "ideate", "complete", ["docs/research.md"])
        state.save(st, self.dir)
        self.assertEqual(state.load(self.dir)["phases"]["ideate"]["status"], "complete")

    def test_load_refuses_unknown_schema_version(self):
        st = self.fresh()
        st["schema_version"] = 999
        state.state_path(self.dir).write_text(json.dumps(st))
        with self.assertRaises(state.StateError):
            state.load(self.dir)

    def test_load_without_a_state_file_explains_itself(self):
        with self.assertRaises(state.StateError) as caught:
            state.load(self.dir)
        self.assertIn("/pipeline init", str(caught.exception))


class SetPhaseTest(StateTestCase):
    def test_rejects_unknown_phase_and_status(self):
        st = self.fresh()
        with self.assertRaises(state.StateError):
            state.set_phase(st, "nonsense", "complete")
        with self.assertRaises(state.StateError):
            state.set_phase(st, "ideate", "finished")

    def test_artifacts_accumulate_without_duplicates(self):
        st = self.fresh()
        state.set_phase(st, "ideate", "in progress", ["a.md"])
        state.set_phase(st, "ideate", "complete", ["a.md", "b.md"])
        self.assertEqual(st["phases"]["ideate"]["artifacts"], ["a.md", "b.md"])

    def test_blocking_records_a_reason_and_completing_clears_it(self):
        st = self.fresh()
        state.set_phase(st, "design", "blocked", reason="waiting on API keys")
        self.assertEqual(st["phases"]["design"]["blocked_reason"], "waiting on API keys")
        state.set_phase(st, "design", "complete")
        self.assertNotIn("blocked_reason", st["phases"]["design"])


class GateTest(StateTestCase):
    def test_no_ruling_means_the_gate_has_not_passed(self):
        self.assertFalse(state.gate_passed(self.fresh(), "judge"))

    def test_sound_passes(self):
        st = self.fresh()
        state.record_ruling(st, "judge", "SOUND", 1)
        self.assertTrue(state.gate_passed(st, "judge"))

    def test_fix_first_with_an_open_fix_does_not_pass(self):
        st = self.fresh()
        state.record_ruling(st, "judge", "FIX FIRST", 1, ["schema needs a migration"])
        self.assertFalse(state.gate_passed(st, "judge"))

    def test_fix_first_with_no_open_fixes_passes(self):
        st = self.fresh()
        state.record_ruling(st, "judge", "FIX FIRST", 2, [])
        self.assertTrue(state.gate_passed(st, "judge"))

    def test_reject_does_not_pass(self):
        st = self.fresh()
        state.record_ruling(st, "judge", "REJECT", 1)
        self.assertFalse(state.gate_passed(st, "judge"))

    def test_split_and_needs_info_do_not_pass(self):
        for ruling in ("SPLIT", "NEEDS INFO"):
            with self.subTest(ruling=ruling):
                st = self.fresh()
                state.record_ruling(st, "judge", ruling, 1)
                self.assertFalse(state.gate_passed(st, "judge"))

    def test_every_round_is_appended_to_the_history(self):
        st = self.fresh()
        state.record_ruling(st, "judge", "REJECT", 1, ["a"])
        state.record_ruling(st, "judge", "SOUND", 2)
        self.assertEqual([r["round"] for r in st["rounds"]], [1, 2])

    def test_rejects_unknown_gate(self):
        with self.assertRaises(state.StateError):
            state.record_ruling(self.fresh(), "vibes", "SOUND", 1)


class BlockersTest(StateTestCase):
    def complete_through(self, st, last):
        for phase in state.PHASES[: state.PHASES.index(last) + 1]:
            state.set_phase(st, phase, "complete")
        return st

    def test_first_phase_is_runnable_immediately(self):
        self.assertEqual(state.blockers(self.fresh(), "ideate"), [])

    def test_a_later_phase_is_blocked_by_an_incomplete_earlier_phase(self):
        reasons = state.blockers(self.fresh(), "design")
        self.assertTrue(any("ideate" in r for r in reasons))

    def test_initiate_is_blocked_by_the_judge_gate_even_when_phases_are_done(self):
        st = self.complete_through(self.fresh(), "verdict")
        reasons = state.blockers(st, "initiate")
        self.assertEqual(len(reasons), 1, reasons)
        self.assertIn("judge gate has not passed", reasons[0])

    def test_initiate_unblocks_once_the_judge_gate_passes(self):
        st = self.complete_through(self.fresh(), "verdict")
        state.record_ruling(st, "judge", "SOUND", 1)
        self.assertEqual(state.blockers(st, "initiate"), [])

    def test_open_fixes_are_named_in_the_blocker_message(self):
        st = self.complete_through(self.fresh(), "verdict")
        state.record_ruling(st, "judge", "FIX FIRST", 1, ["x", "y"])
        self.assertIn("2 fix(es) still open", " ".join(state.blockers(st, "initiate")))

    def test_an_exceeded_budget_blocks_every_phase(self):
        st = self.fresh(max_usd=1.0)
        state.add_spend(st, 1.0)
        self.assertTrue(any("budget exceeded" in r for r in state.blockers(st, "ideate")))


class ModeTest(StateTestCase):
    def test_manual_pauses_after_every_phase(self):
        st = self.fresh(mode="manual")
        self.assertTrue(all(state.should_pause_after(st, p) for p in state.PHASES))

    def test_yolo_pauses_after_none(self):
        st = self.fresh(mode="yolo")
        self.assertFalse(any(state.should_pause_after(st, p) for p in state.PHASES))

    def test_auto_pauses_only_at_the_four_checkpoints(self):
        st = self.fresh(mode="auto")
        paused = [p for p in state.PHASES if state.should_pause_after(st, p)]
        self.assertEqual(paused, list(state.AUTO_CHECKPOINTS))

    def test_set_mode_rejects_an_unknown_mode(self):
        with self.assertRaises(state.StateError):
            state.set_mode(self.fresh(), "wild")


class BudgetTest(StateTestCase):
    def test_spend_accumulates_and_trips_at_the_ceiling(self):
        st = self.fresh(max_usd=2.0)
        state.add_spend(st, 1.0)
        self.assertFalse(state.budget_exceeded(st))
        state.add_spend(st, 1.0)
        self.assertTrue(state.budget_exceeded(st))

    def test_negative_spend_is_refused(self):
        with self.assertRaises(state.StateError):
            state.add_spend(self.fresh(), -5)


class NextPhaseTest(StateTestCase):
    def test_next_is_the_first_incomplete_phase(self):
        st = self.fresh()
        state.set_phase(st, "ideate", "complete")
        self.assertEqual(state.next_phase(st), "proposal")

    def test_next_is_none_when_everything_is_complete(self):
        st = self.fresh()
        for phase in state.PHASES:
            state.set_phase(st, phase, "complete")
        self.assertIsNone(state.next_phase(st))
        self.assertEqual(state.describe_next(st), "all phases complete")

    def test_a_blocked_phase_is_still_the_next_one_and_says_why(self):
        st = self.fresh()
        state.set_phase(st, "ideate", "blocked", reason="need the idea")
        self.assertEqual(state.next_phase(st), "ideate")
        self.assertIn("blocked before /ideate", state.describe_next(st))


class RegistryTest(StateTestCase):
    def test_upsert_replaces_the_row_for_the_same_path(self):
        st = self.fresh()
        state.registry_upsert(st, self.dir)
        state.set_phase(st, "ideate", "complete")
        state.registry_upsert(st, self.dir)
        rows = state.registry_load()["projects"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["phase"], "proposal")

    def test_separate_paths_get_separate_rows(self):
        st = self.fresh()
        other = self.dir / "other"
        other.mkdir()
        state.registry_upsert(st, self.dir)
        state.registry_upsert(st, other)
        self.assertEqual(len(state.registry_load()["projects"]), 2)

    def test_launched_reflects_the_launch_phase(self):
        st = self.fresh()
        state.registry_upsert(st, self.dir)
        self.assertFalse(state.registry_load()["projects"][0]["launched"])
        state.set_phase(st, "launch", "complete")
        state.registry_upsert(st, self.dir)
        self.assertTrue(state.registry_load()["projects"][0]["launched"])


if __name__ == "__main__":
    unittest.main()


class PluginGuardTest(StateTestCase):
    """Running the pipeline inside the plugin's own source would write the user's project
    files into the tool. Reported from real testing, so it is guarded mechanically."""

    def make_plugin(self, name="project-kit"):
        # realpath: on macOS the temp dir lives under /var, a symlink to /private/var, and
        # plugin_root_of resolves symlinks.
        root = Path(os.path.realpath(self.dir)) / "fake-plugin"
        (root / ".claude-plugin").mkdir(parents=True)
        (root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": name}))
        return root

    def test_detects_the_plugin_root_from_within(self):
        root = self.make_plugin()
        nested = root / "skills" / "ideate"
        nested.mkdir(parents=True)
        self.assertEqual(state.plugin_root_of(nested), root)

    def test_detects_the_plugin_root_at_the_root_itself(self):
        root = self.make_plugin()
        self.assertEqual(state.plugin_root_of(root), root)

    def test_returns_none_for_an_ordinary_directory(self):
        self.assertIsNone(state.plugin_root_of(self.dir))

    def test_ignores_a_different_plugin(self):
        other = self.make_plugin(name="some-other-plugin")
        self.assertIsNone(state.plugin_root_of(other))

    def test_ignores_a_corrupt_manifest(self):
        root = self.dir / "broken"
        (root / ".claude-plugin").mkdir(parents=True)
        (root / ".claude-plugin" / "plugin.json").write_text("{ not json")
        self.assertIsNone(state.plugin_root_of(root))

    def test_init_refuses_inside_the_plugin(self):
        root = self.make_plugin()
        result = state.main(["-C", str(root), "init", "--project", "x"])
        self.assertEqual(result, 1)
        self.assertFalse((root / state.STATE_FILE).exists())


class SlugifyTest(unittest.TestCase):
    def test_lowercases_and_hyphenates(self):
        self.assertEqual(state.slugify("Houseplant Tracker"), "houseplant-tracker")

    def test_collapses_runs_and_trims(self):
        self.assertEqual(state.slugify("--My  App!!--"), "my-app")

    def test_falls_back_when_nothing_survives(self):
        self.assertEqual(state.slugify("!!!"), "project")

    def test_keeps_an_already_clean_name(self):
        self.assertEqual(state.slugify("houseplant-tracker"), "houseplant-tracker")


class InitDefaultsTest(StateTestCase):
    def test_project_name_defaults_to_the_directory_name(self):
        target = self.dir / "My Plant App"
        target.mkdir()
        self.assertEqual(state.main(["-C", str(target), "init"]), 0)
        saved = json.loads((target / state.STATE_FILE).read_text())
        self.assertEqual(saved["project"], "my-plant-app")

    def test_explicit_project_name_wins(self):
        target = self.dir / "whatever"
        target.mkdir()
        state.main(["-C", str(target), "init", "--project", "chosen"])
        self.assertEqual(
            json.loads((target / state.STATE_FILE).read_text())["project"], "chosen")


class ContainerDirectoryTest(StateTestCase):
    """Running in ~/projects wrote pipeline.json among unrelated work and named the
    project after the parent folder. An empty dir or a git repo is fine; anything else
    with contents is not."""

    def test_an_empty_directory_is_a_fine_home(self):
        target = self.dir / "empty"
        target.mkdir()
        self.assertIsNone(state.looks_like_a_container(target))

    def test_a_git_repository_is_a_fine_home(self):
        target = self.dir / "brownfield"
        (target / ".git").mkdir(parents=True)
        (target / "main.py").write_text("x = 1")
        self.assertIsNone(state.looks_like_a_container(target))

    def test_a_folder_of_unrelated_work_is_not(self):
        target = self.dir / "projects"
        for name in ("app-a", "notes", "other"):
            (target / name).mkdir(parents=True)
        reason = state.looks_like_a_container(target)
        self.assertIsNotNone(reason)
        self.assertIn("3 item(s)", reason)

    def test_dotfiles_alone_do_not_make_it_a_container(self):
        target = self.dir / "fresh"
        target.mkdir()
        (target / ".DS_Store").write_text("")
        self.assertIsNone(state.looks_like_a_container(target))

    def test_init_refuses_a_container_and_suggests_a_subdirectory(self):
        target = self.dir / "projects"
        (target / "existing").mkdir(parents=True)
        self.assertEqual(
            state.main(["-C", str(target), "init", "--project", "houseplant-tracker"]), 1)
        self.assertFalse((target / state.STATE_FILE).exists())

    def test_here_overrides_the_refusal(self):
        target = self.dir / "projects"
        (target / "existing").mkdir(parents=True)
        self.assertEqual(state.main(["-C", str(target), "init", "--here"]), 0)
        self.assertTrue((target / state.STATE_FILE).exists())
