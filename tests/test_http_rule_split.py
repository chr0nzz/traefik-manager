import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVER = os.path.join(ROOT, 'scripts', 'test_http_rule_split.mjs')


def test_the_host_rule_driver_ships_with_the_repo():
    assert os.path.isfile(DRIVER), (
        'scripts/test_http_rule_split.mjs is the only executable coverage for how the route form '
        'decides between the simple and advanced rule editor; without it a multi-host rule can be '
        'rewritten on save again (issue 179)')


def test_editing_a_route_never_rewrites_a_rule_the_form_cannot_show():
    node = shutil.which('node')
    if not node:
        pytest.skip('node is not installed, run scripts/test_http_rule_split.mjs where it is')
    proc = subprocess.run([node, DRIVER], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, 'the host rule driver failed:\n%s\n%s' % (proc.stdout, proc.stderr)
