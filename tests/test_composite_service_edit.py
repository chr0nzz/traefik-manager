import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVER = os.path.join(ROOT, 'scripts', 'test_composite_service_edit.mjs')


def test_the_composite_edit_driver_ships_with_the_repo():
    assert os.path.isfile(DRIVER)


def test_editing_a_composite_service_keeps_its_backend_names():
    node = shutil.which('node')
    if not node:
        pytest.skip('node is not installed, run scripts/test_composite_service_edit.mjs where it is')
    proc = subprocess.run([node, DRIVER], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, 'the composite edit driver failed:\n%s\n%s' % (proc.stdout, proc.stderr)
