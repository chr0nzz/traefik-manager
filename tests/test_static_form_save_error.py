import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVER = os.path.join(ROOT, 'scripts', 'test_static_form_save_error.mjs')


def test_the_driver_ships_with_the_repo():
    assert os.path.isfile(DRIVER), (
        'scripts/test_static_form_save_error.mjs is the only executable coverage for the static '
        'config forms staying open when a save is refused')


def test_a_refused_save_keeps_the_form_open():
    node = shutil.which('node')
    if not node:
        pytest.skip('node is not installed, run scripts/test_static_form_save_error.mjs where it is')
    proc = subprocess.run([node, DRIVER], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, (
        'the static form save error driver failed:\n%s\n%s' % (proc.stdout, proc.stderr))
