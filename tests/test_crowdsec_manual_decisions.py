import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _js():
    with open(os.path.join(ROOT, 'static', 'js', 'crowdsec.js'), encoding='utf-8') as fh:
        return fh.read()


def _app():
    with open(os.path.join(ROOT, 'app.py'), encoding='utf-8') as fh:
        return fh.read()


def test_manual_counts_as_added_by_hand():
    js = _js()
    assert 'ATK_BY_HAND' in js, 'CrowdSec labels UI-added decisions manual on newer versions'
    m = re.search(r'const ATK_BY_HAND\s*=\s*\{([^}]*)\}', js)
    assert m and 'cscli' in m.group(1) and 'manual' in m.group(1)


def test_neither_by_hand_origin_is_treated_as_a_subscription():
    js = _js()
    m = re.search(r'const ATK_SUBSCRIBED\s*=\s*\{([^}]*)\}', js)
    assert m, 'the subscribed set moved'
    assert 'manual' not in m.group(1) and 'cscli' not in m.group(1), \
        'a hand added decision is yours, not a subscription'


def test_the_by_hand_chip_matches_both_origins():
    js = _js()
    assert "origin: 'byhand'" in js
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, 'app.py'), encoding='utf-8') as fh:
        src = fh.read()
    m = re.search(r"def _cs_is_byhand\(d: dict\) -> bool:\n(.*?)\n", src)
    assert m and 'cscli' in m.group(1) and 'manual' in m.group(1), \
        'clicking the chip must show manual decisions as well as cscli ones'


def test_the_other_bucket_no_longer_swallows_manual():
    js = _js()
    m = re.search(r'const otherNames = Object\.keys\(origins\)\.filter\(([^;]*)\);', js)
    assert m, 'the other bucket moved'
    assert 'ATK_BY_HAND' in m.group(1)


def test_adding_a_decision_drops_the_cached_stream():
    src = _app()
    start = src.index('def api_cs_add_decision(') if 'def api_cs_add_decision(' in src else src.index("@app.route('/api/crowdsec/decisions', methods=['POST'])")
    body = src[start:src.index('\n@app.route', start + 10)]
    assert 'cs_stream_reset()' in body, (
        'decisions are served from a cache with a freshness window, so a newly added '
        'decision is invisible until it expires')


def test_deleting_a_decision_drops_the_cached_stream():
    src = _app()
    start = src.index('def api_cs_unban(')
    body = src[start:src.index('\n@app.route', start)]
    assert 'cs_stream_reset()' in body


def test_the_reset_helper_actually_clears_everything():
    import core.crowdsec as crowd
    crowd._cs_stream_cache.update({'fp': 'x', 'items': {'1': {}}, 'synced': 'now', 'ready': True})
    crowd.cs_stream_reset()
    assert crowd._cs_stream_cache['items'] == {}
    assert crowd._cs_stream_cache['ready'] is False
