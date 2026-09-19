"""Exercise reusable workflow inputs and failures without network credentials."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def workflow(name):
    return yaml.safe_load((WORKFLOWS / name).read_text())


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.report = self.root / "report.json"
        self.env = dict(os.environ, GITHUB_WORKSPACE=str(self.workspace),
                        RUNNER_TEMP=str(self.root), REPORT=str(self.report))
        self.env["PATH"] = str(self.bin) + os.pathsep + self.env["PATH"]
        scanner = self.bin / "semgrep"
        scanner.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
rules = [pathlib.Path(a).read_text() for a in args if a.endswith("supabase.yml")]
pathlib.Path(os.environ["REPORT"]).write_text(json.dumps({"args": args, "rules": rules, "cwd": os.getcwd()}))
sys.exit(int(os.environ.get("SCANNER_EXIT", "0")))
''')
        scanner.chmod(0o755)

    def run_scan(self, profile="general", directory=".", exit_code=0):
        step = workflow("semgrep.yml")["jobs"]["semgrep"]["steps"][-1]
        env = dict(self.env, SCAN_PROFILE=profile, SCAN_DIRECTORY=directory,
                   SCANNER_EXIT=str(exit_code))
        return subprocess.run([os.sys.executable, "-c", step["run"]], env=env,
                              capture_output=True, text=True)

    def test_profiles_select_only_intended_rules(self):
        for profile in ("general", "javascript", "ia", "legacy-ia"):
            with self.subTest(profile=profile):
                result = self.run_scan(profile)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(self.report.read_text())
                self.assertIn("--strict", report["args"])
                self.assertIn("--error", report["args"])
                self.assertEqual("p/react" in report["args"], profile != "general")
                self.assertEqual(bool(report["rules"]), profile in ("ia", "legacy-ia"))
                for content in report["rules"]:
                    self.assertEqual(yaml.safe_load(content)["rules"][0]["severity"], "ERROR")

    def test_invalid_profile_fails_before_scanner(self):
        result = self.run_scan("typo")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.report.exists())

    def test_missing_outside_and_symlink_directories_fail(self):
        (self.workspace / "outside").symlink_to(self.root, target_is_directory=True)
        for directory in ("missing", "..", str(self.root), "outside"):
            with self.subTest(directory=directory):
                self.assertNotEqual(self.run_scan(directory=directory).returncode, 0)
                self.assertFalse(self.report.exists())

    def test_subdirectory_with_spaces_is_supported(self):
        target = self.workspace / "source folder"
        target.mkdir()
        result = self.run_scan(directory="source folder")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.report.read_text())["cwd"], str(target.resolve()))

    def test_findings_and_scanner_failures_do_not_pass(self):
        for code in (1, 2, 7):
            with self.subTest(exit_code=code):
                self.assertNotEqual(self.run_scan(exit_code=code).returncode, 0)

    def test_audit_input_cannot_inject_shell_commands(self):
        step = workflow("dependency-audit.yml")["jobs"]["audit"]["steps"][-1]
        npm = self.bin / "npm"
        npm.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$REPORT"\nexit "${SCANNER_EXIT:-0}"\n')
        npm.chmod(0o755)
        for level in ("high", "critical", "moderate", "low", "info", "none"):
            result = subprocess.run(["bash", "-e", "-c", step["run"]],
                                    env=dict(self.env, AUDIT_LEVEL=level), capture_output=True)
            self.assertEqual(result.returncode, 0)
            self.assertIn("--audit-level=" + level, self.report.read_text())
        self.report.unlink()
        result = subprocess.run(["bash", "-e", "-c", step["run"]],
                                env=dict(self.env, AUDIT_LEVEL='high; touch injected'),
                                cwd=self.workspace, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.report.exists())
        self.assertFalse((self.workspace / "injected").exists())
        result = subprocess.run(["bash", "-e", "-c", step["run"]],
                                env=dict(self.env, AUDIT_LEVEL="high", SCANNER_EXIT="1"),
                                capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_compatibility_default_and_action_pins(self):
        # PyYAML YAML 1.1 treats GitHub's 'on' key as True.
        config = workflow("semgrep.yml")[True]["workflow_call"]["inputs"]
        self.assertEqual(config["profile"]["default"], "legacy-ia")
        for path in WORKFLOWS.glob("*.yml"):
            data = yaml.safe_load(path.read_text())
            self.assertEqual(data["permissions"], {"contents": "read"})
            for job in data["jobs"].values():
                for step in job.get("steps", []):
                    if "uses" in step and not step["uses"].startswith("./"):
                        self.assertRegex(step["uses"], r"@[a-f0-9]{40}$")


if __name__ == "__main__":
    unittest.main()
