import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_REPO = 'chr0nzz/unraid-templates'


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def test_the_template_does_not_live_here_any_more():
    assert not os.path.exists(os.path.join(ROOT, 'unraid')), \
        f'the template belongs in {TEMPLATE_REPO}, two copies drift apart'
    assert not os.path.exists(os.path.join(ROOT, 'ca_profile.xml'))


def test_the_docs_do_not_send_people_to_the_field_unraid_removed():
    doc = _read('docs', 'unraid.md')
    steps = doc.split('## Configuration')[0]
    assert 'Add this URL to your repository list' not in steps
    assert 'unraid.xyzlab.dev/tm' not in steps, 'that URL cannot be pasted anywhere in current Unraid'
    assert 'templates-user' in steps, 'there has to be a way to install it that still works'


def test_every_template_link_points_at_the_repository_that_has_it():
    doc = _read('docs', 'unraid.md')
    for url in re.findall(r'https://raw\.githubusercontent\.com/\S+?\.xml', doc):
        assert TEMPLATE_REPO in url, f'{url} no longer exists'
    assert TEMPLATE_REPO in doc, 'the guide should say where the template is kept'
