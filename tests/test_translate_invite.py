import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def test_the_invite_offers_a_way_in_and_two_ways_out():
    html = _read('templates', 'index.html')
    assert 'id="translateInvitePopup"' in html
    assert 'https://hosted.weblate.org/engage/traefik-manager/' in html, 'the invite needs somewhere to send a willing translator'
    assert 'snoozeTranslateInvite()' in html and 'dismissTranslateInvite()' in html, \
        'an invite that cannot be put off or turned off is a nag'
    assert 'template=language-request.yml' in html, 'a reader whose language is missing needs the request form'


def test_a_dismissed_invite_stays_dismissed():
    js = _read('static', 'js', 'settings.js')
    assert "state.dismissed" in js and "snoozedUntil" in js, 'both answers must be remembered'
    assert 'TRANSLATE_INVITE_SNOOZE_DAYS' in js, 'later means a fixed number of days, not until the next reload'
    assert 'catch (e)' in js.split('function _translateInviteState')[1][:400], \
        'unreadable storage must not throw on every page load'


def test_the_invite_does_not_cover_the_update_or_advisory_popups():
    js = _read('static', 'js', 'settings.js')
    stack = js.split('function showTranslateInvite')[1][:700]
    assert 'tmUpdatePopup' in stack and 'securityAdvisoryPopup' in stack, \
        'the invite shares the bottom right corner with two older popups'
    assert 'offsetHeight' in stack, 'it stacks above whatever is already there instead of hiding behind it'
