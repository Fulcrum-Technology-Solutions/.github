"""Execute the reusable workflow's actual toolchain contract against fixtures."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml


class ToolchainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        workflow = Path(__file__).parents[1] / '.github/workflows/node-quality.yml'
        steps = yaml.safe_load(workflow.read_text())['jobs']['quality']['steps']
        self.script = next(s['run'] for s in steps if s.get('id') == 'toolchain')
        self.install = next(s['run'] for s in steps if s.get('name') == 'Install declared npm version')
        self.major = subprocess.check_output(['node', '-p', "process.versions.node.split('.')[0]"], text=True).strip()
        self.manifest = {'packageManager': 'npm@11.19.0', 'engines': {'node': f'{self.major}.x', 'npm': '11.19.0'}}
        (self.root / '.node-version').write_text(self.major + '\n')
        self.output = self.root / 'output'

    def run_contract(self):
        (self.root / 'package.json').write_text(json.dumps(self.manifest))
        return subprocess.run([os.sys.executable, '-c', self.script], cwd=self.root,
                              env=dict(os.environ, GITHUB_OUTPUT=str(self.output)), capture_output=True, text=True)

    def test_valid_contract_exports_exact_npm(self):
        result = self.run_contract()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_text(), 'npm-version=11.19.0\n')

    def test_missing_range_or_injected_manager_fails(self):
        for value in ['', 'npm@^11', 'pnpm@11.19.0', 'npm@11.19.0\nother=value', 'npm@11.19.0;touch injected']:
            with self.subTest(value=value):
                self.manifest['packageManager'] = value
                self.assertNotEqual(self.run_contract().returncode, 0)
                self.assertFalse(self.output.exists())

    def test_mismatched_or_missing_runtime_file_fails(self):
        (self.root / '.node-version').write_text('999\n')
        self.assertNotEqual(self.run_contract().returncode, 0)
        (self.root / '.node-version').unlink()
        self.assertNotEqual(self.run_contract().returncode, 0)

    def test_engine_drift_fails(self):
        for engines in [{}, {'node': '>=22', 'npm': '11.19.0'}, {'node': f'{self.major}.x', 'npm': '11.1.0'}]:
            with self.subTest(engines=engines):
                self.manifest['engines'] = engines
                self.assertNotEqual(self.run_contract().returncode, 0)

    def test_install_failure_or_wrong_version_blocks(self):
        binary = self.root / 'npm'
        env = dict(os.environ, PATH=str(self.root)+os.pathsep+os.environ['PATH'], NPM_VERSION='11.19.0')
        for body in ['exit 7', 'echo 11.1.0']:
            binary.write_text('#!/bin/sh\n'+body+'\n')
            binary.chmod(0o755)
            result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', self.install], env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
