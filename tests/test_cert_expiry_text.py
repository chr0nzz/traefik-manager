import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVER = os.path.join(ROOT, 'scripts', 'test_cert_expiry_text.mjs')


def test_the_expiry_driver_ships_with_the_repo():
    assert os.path.isfile(DRIVER), (
        'scripts/test_cert_expiry_text.mjs is the only executable coverage for how '
        'a certificate past its expiry is worded; without it the card can go back '
        'to counting down into negative days')


def test_expired_certificates_are_worded_not_counted():
    node = shutil.which('node')
    if not node:
        pytest.skip('node is not installed, run scripts/test_cert_expiry_text.mjs where it is')

    proc = subprocess.run([node, DRIVER], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, (
        'the certificate expiry wording driver failed:\n%s\n%s' % (proc.stdout, proc.stderr))
