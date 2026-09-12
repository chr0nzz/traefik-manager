import os
import re
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, 'unraid', 'traefik-manager.xml')

VALID_TYPES   = ('Path', 'Port', 'Variable', 'Label', 'Device')
VALID_DISPLAY = ('always', 'always-hide', 'advanced', 'advanced-hide', 'hidden')
VALID_BOOL    = ('true', 'false')


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _root():
    return ET.parse(TEMPLATE).getroot()


def test_the_template_parses_and_says_what_it_is():
    root = _root()
    assert root.tag == 'Container' and root.get('version') == '2'
    for tag in ('Name', 'Repository', 'Overview', 'Icon', 'TemplateURL', 'WebUI', 'Category'):
        el = root.find(tag)
        assert el is not None and (el.text or '').strip(), f'{tag} is required by Community Applications'
    assert (root.findtext('Support') or root.findtext('Project')), \
        'a template with neither Support nor Project gets removed from Community Applications'


def test_every_config_is_on_one_line():
    for line in _read('unraid', 'traefik-manager.xml').splitlines():
        stripped = line.strip()
        if stripped.startswith('<Config'):
            assert stripped.endswith('</Config>'), \
                f'wrapped attributes break the Community Applications parser: {stripped[:60]}'


def test_every_config_uses_values_unraid_understands():
    for cfg in _root().findall('Config'):
        name = cfg.get('Name')
        assert name, 'a Config with no Name renders as a blank field'
        assert cfg.get('Target'), f'{name} has nothing to set'
        assert cfg.get('Type') in VALID_TYPES, f'{name} has Type {cfg.get("Type")!r}'
        assert cfg.get('Display') in VALID_DISPLAY, f'{name} has Display {cfg.get("Display")!r}'
        assert cfg.get('Required') in VALID_BOOL, f'{name} has Required {cfg.get("Required")!r}'
        assert cfg.get('Mask') in VALID_BOOL, f'{name} has Mask {cfg.get("Mask")!r}'
        if cfg.get('Type') == 'Path':
            assert cfg.get('Mode') in ('rw', 'ro', 'rw,slave', 'rw,shared', 'ro,slave', 'ro,shared'), \
                f'{name} is a path with Mode {cfg.get("Mode")!r}'
        if cfg.get('Type') == 'Port':
            assert cfg.get('Mode') in ('tcp', 'udp'), f'{name} is a port with Mode {cfg.get("Mode")!r}'


def test_secrets_are_masked():
    for cfg in _root().findall('Config'):
        target = (cfg.get('Target') or '').upper()
        if target.endswith(('_PASSWORD', '_SECRET', '_KEY')) and target not in ('CROWDSEC_CLIENT_KEY', 'OTP_ENCRYPTION_KEY'):
            assert cfg.get('Mask') == 'true', f'{target} is typed in the clear'


def test_the_template_offers_every_environment_variable_the_app_reads():
    import glob
    found = set()
    for rel in ['app.py'] + [os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, 'core', '*.py'))]:
        src = _read(rel)
        found |= set(re.findall(r"environ\.get\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]", src))
        found |= set(re.findall(r"environ\[\s*['\"]([A-Z][A-Z0-9_]*)['\"]", src))
        found |= set(re.findall(r"_env_bool\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]", src))
        found |= set(re.findall(r"_cs_int_env\(\s*['\"]([A-Z][A-Z0-9_]*)['\"]", src))
    found -= {'HOSTNAME', 'PATH', 'TZ', 'PWD', 'HOME', 'PATH_INFO', 'SCRIPT_NAME',
              'CROWDSEC_STREAM_FRESH_SECONDS'}
    offered = {c.get('Target') for c in _root().findall('Config') if c.get('Type') == 'Variable'}
    missing = sorted(found - offered)
    assert not missing, f'Unraid users cannot set these without editing the container: {missing}'


def test_the_template_url_points_at_itself():
    url = _root().findtext('TemplateURL') or ''
    assert url.endswith('/unraid/traefik-manager.xml'), \
        'Community Applications identifies the template by this URL, it has to match where the file lives'


def test_the_maintainer_profile_is_present_for_community_applications():
    profile = os.path.join(ROOT, 'ca_profile.xml')
    assert os.path.exists(profile), 'submission is blocked without ca_profile.xml in the repository root'
    root = ET.parse(profile).getroot()
    assert root.tag == 'Profile'
    assert (root.findtext('Name') or '').strip(), 'an empty Profile blocks submission'


def test_the_docs_do_not_send_people_to_the_field_unraid_removed():
    doc = _read('docs', 'unraid.md')
    assert 'templates-user' in doc, 'there has to be a way to install it that still works'
    assert 'Add this URL to your repository list' not in doc
    steps = doc.split('## Configuration')[0]
    assert 'unraid.xyzlab.dev/tm' not in steps, 'that URL cannot be pasted anywhere in current Unraid'
