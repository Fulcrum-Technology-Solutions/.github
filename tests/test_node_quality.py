"""Execute audit selection against real Git histories and test command failures."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

WORKFLOW = Path(__file__).parents[1] / ".github/workflows/node-quality.yml"


class NodeQualityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "CI Test")
        self.git("config", "user.email", "ci-test@example.invalid")
        (self.repo / "package.json").write_text('{"name":"fixture"}')
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.steps = yaml.safe_load(WORKFLOW.read_text())["jobs"]["quality"]["steps"]
        self.scope = next(step["run"] for step in self.steps if step.get("id") == "scope")
        self.output = self.root / "output"

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.repo, text=True)

    def select(self, path="README.md", **overrides):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("changed")
        self.git("add", ".")
        self.git("commit", "-qm", "change")
        env = dict(os.environ, EVENT_NAME="pull_request", CHANGE_ONLY="true",
                   PR_BASE=self.base, PR_HEAD=self.git("rev-parse", "HEAD").strip(),
                   BASE_REF="develop", RELEASE_BRANCH="main", AUDIT_LEVEL="high",
                   GITHUB_WORKSPACE=str(self.repo), GITHUB_OUTPUT=str(self.output))
        env.update(overrides)
        result = subprocess.run([os.sys.executable, "-c", self.scope], env=env,
                                cwd=self.repo, text=True, capture_output=True)
        return result, self.output.read_text() if self.output.exists() else ""

    def test_ordinary_integration_change_skips_audit(self):
        result, output = self.select("src/component.ts")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, "audit=false\n")

    def test_dependency_and_workflow_changes_audit(self):
        for path in ("package.json", "web/package-lock.json", ".npmrc", "npm-shrinkwrap.json", ".github/workflows/ci.yml"):
            with self.subTest(path=path):
                result, output = self.select(path)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(output.endswith("audit=true\n"))
                self.git("reset", "--hard", self.base)

    def test_release_and_scheduled_audits_do_not_depend_on_changed_files(self):
        for key, value in (("BASE_REF", "main"), ("EVENT_NAME", "schedule"),
                           ("EVENT_NAME", "push"), ("CHANGE_ONLY", "false")):
            with self.subTest(key=key, value=value):
                result, output = self.select(**{key: value})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(output.endswith("audit=true\n"))
                self.git("reset", "--hard", self.base)

    def test_rename_away_from_manifest_still_audits(self):
        self.git("mv", "package.json", "old-manifest.txt")
        result, output = self.select()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, "audit=true\n")

    def test_deleted_manifest_still_audits(self):
        self.git("rm", "package.json")
        result, output = self.select()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, "audit=true\n")

    def test_base_branch_only_dependency_change_is_not_a_pr_change(self):
        self.git("checkout", "-qb", "target")
        (self.repo / "package.json").write_text('{"name":"target-change"}')
        self.git("commit", "-qam", "base advanced")
        target = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "-qb", "feature", self.base)
        result, output = self.select("src/component.ts", PR_BASE=target)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, "audit=false\n")

    def test_invalid_or_unavailable_revisions_fail_instead_of_skipping(self):
        for revision in ("", "not-a-sha", "1" * 40):
            with self.subTest(revision=revision):
                result, output = self.select(PR_BASE=revision)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(output, "")
                self.git("reset", "--hard", self.base)

    def test_nonblocking_or_injected_audit_threshold_is_rejected(self):
        for level in ("none", "high; touch injected"):
            result, output = self.select(AUDIT_LEVEL=level)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output, "")
            self.assertFalse((self.repo / "injected").exists())
            self.git("reset", "--hard", self.base)

    def test_each_command_failure_remains_a_failure(self):
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        npm = bin_dir / "npm"
        npm.write_text('#!/bin/sh\nexit 7\n')
        npm.chmod(0o755)
        env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ["PATH"], AUDIT_LEVEL="high")
        for step in self.steps:
            if step.get("run", "").startswith("npm "):
                with self.subTest(step=step["name"]):
                    result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", step["run"]], env=env)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("continue-on-error", step)


if __name__ == "__main__":
    unittest.main()
