import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVER = os.path.join(ROOT, 'scripts', 'test_file_external_empty.mjs')


def test_the_empty_state_driver_ships_with_the_repo():
    assert os.path.isfile(DRIVER)


def test_the_empty_file_external_tab_says_why():
    node = shutil.which('node')
    if not node:
        pytest.skip('node is not installed, run scripts/test_file_external_empty.mjs where it is')
    proc = subprocess.run([node, DRIVER], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, 'the File (external) empty state driver failed:\n%s\n%s' % (proc.stdout, proc.stderr)
