import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVER = os.path.join(ROOT, 'scripts', 'test_i18n_shim.mjs')


def test_the_shim_driver_ships_with_the_repo():
    assert os.path.isfile(DRIVER), (
        'scripts/test_i18n_shim.mjs is the only executable coverage for t(), tn() and tc() '
        'in static/js/i18n.js')


def test_the_shim_translates_and_falls_back():
    node = shutil.which('node')
    if not node:
        pytest.skip('node is not installed, run scripts/test_i18n_shim.mjs where it is')

    proc = subprocess.run([node, DRIVER], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, (
        'the i18n shim driver failed:\n%s\n%s' % (proc.stdout, proc.stderr))
