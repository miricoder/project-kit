"""Tests for skills/devops/scripts/ship.py: the mechanical half of /devops, /test, /security
and /launch.

The important ones are the refusals: nothing is recorded deployed unless the script reached
it, no gate passes unless the script ran it, and launch is not complete until a rollback
has been rehearsed against production.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import unittest.mock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "devops" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "pipeline" / "scripts"))

import ship  # noqa: E402
import state  # noqa: E402

FEATURE = """Feature: Things

  Scenario: a task is filed
    Given a capture
    Then a task exists

  Scenario: an expense is filed
    Given a capture
    Then an expense exists
"""

TESTS = '''def test_task():
    """Scenario: a task is filed"""

def test_expense():
    """Scenario: an expense is filed"""
'''

PASS = f'"{sys.executable}" -c "raise SystemExit(0)"'
FAIL = f'"{sys.executable}" -c "raise SystemExit(3)"'
FAKE_KEY = "sk-ant-" + "api03-" + "A" * 30


class Health(BaseHTTPRequestHandler):
    status = 200

    def do_GET(self):  # noqa: N802
        code = 200 if self.path == "/health" and Health.status == 200 else Health.status
        if self.path != "/health":
            code = 404
        self.send_response(code)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def log_message(self, *_):
        pass


class ShipTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Health)
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        Health.status = 200
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name) / "demo"
        self.dir.mkdir()
        env = {"PROJECT_KIT_REGISTRY": str(Path(self.tmp.name) / "registry.json"),
               "PROJECT_KIT_ALLOW_HTTP": "1"}
        patcher = unittest.mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        (self.dir / "docs").mkdir()
        (self.dir / "docs" / "acceptance.feature").write_text(FEATURE)
        (self.dir / "tests").mkdir()
        (self.dir / "tests" / "test_things.py").write_text(TESTS)
        (self.dir / ".github" / "workflows").mkdir(parents=True)
        (self.dir / ".github" / "workflows" / "ci.yml").write_text(
            f"jobs:\n  test:\n    steps:\n      - run: {PASS}\n")
        (self.dir / ".github" / "workflows" / "deploy.yml").write_text(
            "jobs:\n  deploy-staging:\n    steps:\n      - run: sh scripts/deploy.sh staging\n")
        (self.dir / ".github" / "dependabot.yml").write_text("version: 2\nupdates: []\n")
        (self.dir / "CHANGELOG.md").write_text("# Changelog\n\n## 1.0.0\n\n- first release\n")
        (self.dir / "docs" / "threat-model.md").write_text(
            "# Threat model\n\n## Assets\n\nUser data.\n\n## Threats\n\nStolen session.\n\n"
            "## Mitigations\n\nHttpOnly cookies.\n")
        st = state.new_state("demo", "yolo")
        for phase in state.PHASES[:state.PHASES.index("build") + 1]:
            st["phases"][phase]["status"] = "complete"
        st["gates"]["judge"].update(status="complete", ruling="SOUND")
        st["build"] = {"test_command": PASS, "tests": ["tests"]}
        state.save(st, self.dir)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "T")
        self.commit("initial")

    # ------------------------------------------------------------------ helpers

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.dir, capture_output=True, text=True,
                              check=True).stdout.strip()

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def pk(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ship.main(["-C", str(self.dir), *args])
        return code, out.getvalue(), err.getvalue()

    def ok(self, *args):
        code, out, err = self.pk(*args)
        self.assertEqual(code, 0, err)
        return json.loads(out) if out.strip() else None

    def refused(self, *args):
        code, _, err = self.pk(*args)
        self.assertEqual(code, 1, f"expected a refusal for {args}")
        return err

    def state(self):
        return state.load(self.dir)

    def to_devops_done(self):
        self.ok("config", "--target", "cloudrun", "--health", "/health", "--env", "DATABASE_URL")
        self.ok("record", "staging", "--url", self.url)   # pipeline.json changes; that is fine
        self.ok("release", "v1.0.0")
        self.ok("done", "devops")
        self.commit("devops done")

    def to_security_done(self):
        self.to_devops_done()
        self.ok("test")
        self.ok("audit")

    # ------------------------------------------------------------------ smoke and record

    def test_smoke_reports_up_and_down(self):
        self.assertTrue(ship.smoke(self.url, "/health")["ok"])
        Health.status = 503
        self.assertFalse(ship.smoke(self.url, "/health")["ok"])
        self.assertFalse(ship.smoke("http://127.0.0.1:9", "/health")["ok"])

    def test_record_refuses_when_the_deployment_does_not_answer(self):
        self.ok("config", "--target", "cloudrun", "--health", "/health")
        Health.status = 500
        err = self.refused("record", "staging", "--url", self.url)
        self.assertIn("smoke check failed", err)
        self.assertEqual(ship.deploys(self.state()), [])

    def test_record_needs_a_target(self):
        self.assertIn("no deploy target", self.refused("record", "staging", "--url", self.url))

    def test_config_refuses_values(self):
        code, _, err = self.pk("config", "--env", "API_KEY=secret")
        self.assertEqual(code, 2)
        self.assertIn("names only", err)

    def test_staging_deploy_is_allowed_before_build_is_complete(self):
        st = self.state()
        st["phases"]["build"]["status"] = "in progress"
        state.save(st, self.dir)
        self.ok("config", "--target", "cloudrun", "--health", "/health")
        self.ok("record", "staging", "--url", self.url)
        self.assertEqual(len(ship.deploys(self.state(), "staging")), 1)

    def test_production_is_refused_before_the_security_gate(self):
        self.ok("config", "--target", "cloudrun", "--health", "/health")
        err = self.refused("record", "production", "--url", self.url)
        self.assertIn("security gate has not passed", err)

    def test_production_must_be_https(self):
        with unittest.mock.patch.dict(os.environ, {"PROJECT_KIT_ALLOW_HTTP": "0"}):
            self.assertTrue(ship.https_required("http://example.com"))
            self.assertFalse(ship.https_required("https://example.com"))

    # ------------------------------------------------------------------ devops

    def test_the_state_file_does_not_make_the_tree_dirty(self):
        self.ok("config", "--target", "cloudrun")
        self.assertEqual(ship.dirty(self.dir), [])
        (self.dir / "app.py").write_text("x = 1\n")
        self.assertEqual(len(ship.dirty(self.dir)), 1)

    def test_release_refuses_without_staging_changelog_or_clean_tree(self):
        self.ok("config", "--target", "cloudrun", "--health", "/health")
        (self.dir / "CHANGELOG.md").write_text("# Changelog\n")
        err = self.refused("release", "v1.0.0")
        self.assertIn("not clean", err)
        self.assertIn("CHANGELOG.md has no entry", err)
        self.assertIn("not been deployed to staging", err)
        self.assertIn("not a semantic version", self.refused("release", "latest"))

    def test_devops_done_refuses_without_ci_running_the_tests(self):
        (self.dir / ".github" / "workflows" / "ci.yml").write_text("jobs: {}\n")
        self.ok("config", "--target", "cloudrun", "--health", "/health")
        err = self.refused("done", "devops")
        self.assertIn("no CI file runs the project's test command", err)
        self.assertIn("no release tagged", err)

    def test_devops_done_refuses_without_continuous_deploy_or_dependency_updates(self):
        (self.dir / ".github" / "workflows" / "deploy.yml").unlink()
        (self.dir / ".github" / "dependabot.yml").unlink()
        self.ok("config", "--target", "cloudrun", "--health", "/health")
        err = self.refused("done", "devops")
        self.assertIn("no CI job deploys to staging", err)
        self.assertIn("no dependency updates configured", err)

    def test_devops_done_refuses_while_build_is_unfinished(self):
        st = self.state()
        st["phases"]["build"]["status"] = "in progress"
        state.save(st, self.dir)
        self.assertIn("build is in progress", self.refused("done", "devops"))

    def test_devops_completes_with_ci_release_and_staging(self):
        self.to_devops_done()
        self.assertEqual(self.state()["phases"]["devops"]["status"], "complete")
        self.assertEqual(self.git("tag"), "v1.0.0")

    # ------------------------------------------------------------------ test gate

    def test_test_gate_fails_on_an_unmapped_scenario_and_writes_the_report(self):
        self.to_devops_done()
        (self.dir / "tests" / "test_things.py").write_text('"""Scenario: a task is filed"""\n')
        err = self.refused("test")
        self.assertIn("scenario not named in any test: 'an expense is filed'", err)
        st = self.state()
        self.assertEqual(st["gates"]["test"]["ruling"], "FAIL")
        self.assertFalse(state.gate_passed(st, "test"))
        self.assertIn("Result:** FAIL", (self.dir / ship.TEST_REPORT).read_text())

    def test_test_gate_fails_when_the_suite_fails(self):
        self.to_devops_done()
        st = self.state()
        st["build"]["test_command"] = FAIL
        state.save(st, self.dir)
        self.assertIn("test command failed (exit 3)", self.refused("test"))

    def test_test_gate_refuses_before_devops(self):
        self.assertIn("devops is not started", self.refused("test"))

    def test_test_gate_passes(self):
        self.to_devops_done()
        out = self.ok("test")
        self.assertTrue(out["passed"])
        st = self.state()
        self.assertTrue(state.gate_passed(st, "test"))
        self.assertEqual(st["phases"]["test"]["status"], "complete")
        self.assertIn("Scenarios mapped:** 2 of 2", (self.dir / ship.TEST_REPORT).read_text())

    # ------------------------------------------------------------------ security gate

    def test_scan_finds_a_secret_that_was_committed_and_then_removed(self):
        (self.dir / "settings.py").write_text(f'KEY = "{FAKE_KEY}"\n')
        self.commit("oops")
        (self.dir / "settings.py").write_text('KEY = os.environ["KEY"]\n')
        self.commit("remove key")
        findings = ship.scan_secrets(self.dir)
        self.assertTrue(any(f.startswith("history ") and "Anthropic" in f for f in findings))
        self.assertFalse(any(f.startswith("settings.py") for f in findings))

    def test_scan_ignores_localhost_database_urls(self):
        (self.dir / "a.py").write_text('URL = "postgresql://user:password@localhost/db"\n')
        self.commit("local db")
        self.assertEqual(ship.scan_secrets(self.dir), [])

    def test_audit_fails_on_a_secret_in_history(self):
        (self.dir / "leak.txt").write_text(FAKE_KEY + "\n")
        self.commit("leak")
        self.git("rm", "-q", "leak.txt")
        self.commit("unleak")
        self.to_devops_done()
        self.ok("test")
        err = self.refused("audit")
        self.assertIn("secret: history", err)
        self.assertEqual(self.state()["gates"]["security"]["ruling"], "FAIL")

    def test_audit_fails_without_a_complete_threat_model(self):
        self.to_devops_done()
        self.ok("test")
        (self.dir / "docs" / "threat-model.md").write_text("# Threat model\n\n## Assets\n\nTODO\n")
        err = self.refused("audit")
        self.assertIn("no '## Threats' section", err)
        self.assertIn("TODO/TBD", err)

    def test_unaudited_dependencies_fail_the_gate(self):
        (self.dir / "requirements.txt").write_text("fastapi==0.115.0\n")
        with unittest.mock.patch.object(ship.shutil, "which", return_value=None):
            audits = ship.dependency_audits(self.dir)
        self.assertEqual([a["ok"] for a in audits], [False])
        self.assertIn("pip-audit is not installed", audits[0]["detail"])

    def test_audit_passes(self):
        self.to_security_done()
        st = self.state()
        self.assertTrue(state.gate_passed(st, "security"))
        self.assertIn("none found", (self.dir / ship.AUDIT_REPORT).read_text())

    # ------------------------------------------------------------------ launch

    def test_production_needs_the_version_on_staging_first(self):
        self.to_security_done()
        err = self.refused("record", "production", "--url", self.url, "--version", "deadbeef")
        self.assertIn("never deployed to staging", err)

    def test_launch_refuses_until_a_rollback_is_rehearsed(self):
        self.to_security_done()
        self.ok("record", "production", "--url", self.url, "--version", "v1.0.0")
        self.assertIn("rollback not rehearsed", self.refused("done", "launch"))
        self.ok("record", "production", "--url", self.url, "--version", "v0.9.0",
                "--kind", "rollback")
        self.assertIn("never restored", self.refused("done", "launch"))
        self.ok("record", "production", "--url", self.url, "--version", "v1.0.0",
                "--kind", "restore")
        out = self.ok("done", "launch")
        self.assertEqual(out["next"], "all phases complete")
        self.assertEqual(self.state()["phases"]["launch"]["status"], "complete")

    def test_launch_refuses_when_production_is_down_now(self):
        self.to_security_done()
        for version, kind in (("v1.0.0", "deploy"), ("v0.9.0", "rollback"),
                              ("v1.0.0", "restore")):
            self.ok("record", "production", "--url", self.url, "--version", version,
                    "--kind", kind)
        Health.status = 502
        self.assertIn("production is not answering now", self.refused("done", "launch"))

    def test_launch_refuses_when_production_is_not_the_release(self):
        self.to_security_done()
        st = self.state()
        st["ship"]["deploys"].append({"env": "production", "kind": "deploy", "url": self.url,
                                      "version": "cafe123", "at": "x", "smoke": {}})
        state.save(st, self.dir)
        self.assertIn("not release v1.0.0", self.refused("done", "launch"))


if __name__ == "__main__":
    unittest.main()
