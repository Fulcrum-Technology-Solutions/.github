"""Real scanner regression tests for FTSC's embedded IA rule."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("semgrep"), "Install Semgrep 1.177.0 for scanner integration tests")
class SupabaseRuleTests(unittest.TestCase):
    def test_public_privileged_reference_fails_and_public_anon_reference_passes(self):
        body = yaml.safe_load((ROOT / ".github/workflows/semgrep.yml").read_text())
        code = body["jobs"]["semgrep"]["steps"][-1]["run"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "source"
            workspace.mkdir()
            rule = root / "rule.yml"

            def capture_rule(command, **kwargs):
                embedded = next(Path(a) for a in command if a.endswith("supabase.yml"))
                rule.write_text(embedded.read_text())

            with patch.dict(os.environ, GITHUB_WORKSPACE=str(workspace),
                            RUNNER_TEMP=str(root), SCAN_PROFILE="ia", SCAN_DIRECTORY="."), \
                    patch("subprocess.run", side_effect=capture_rule):
                exec(compile(code, "semgrep-workflow", "exec"), {})

            for name, source, expected in (
                ("privileged", "const key = process.env.VITE_SUPABASE_SERVICE_ROLE_KEY;", 1),
                ("anon", "const key = process.env.VITE_SUPABASE_ANON_KEY;", 0),
            ):
                with self.subTest(case=name):
                    (workspace / "sample.ts").write_text(source)
                    result = subprocess.run(
                        ["semgrep", "scan", "--config", str(rule), "--error", "--strict",
                         "--metrics=off", "--disable-version-check", "--no-git-ignore", "."],
                        cwd=workspace, capture_output=True, text=True,
                        env=dict(os.environ, SEMGREP_SEND_METRICS="off"),
                    )
                    self.assertEqual(result.returncode, expected, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
