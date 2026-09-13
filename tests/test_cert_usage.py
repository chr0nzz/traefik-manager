from datetime import datetime, timedelta, timezone

import pytest

from core import cert_usage as cu
from core import config as cfg


def _cert(main, sans=(), resolver='letsencrypt', not_after=None):
    return {'main': main, 'sans': list(sans), 'resolver': resolver,
            'not_after': not_after, 'source': 'acme.json'}


def _app(rule, tls=True, tls_domains=(), protocol='http'):
    return {'rule': rule, 'tls': tls, 'protocol': protocol, 'tlsDomains': list(tls_domains)}


def _verdict(certs, apps, **kw):
    kw.setdefault('routers_ok', True)
    kw.setdefault('configs_ok', True)
    return cu.analyze(certs, apps, **kw)


@pytest.mark.parametrize('rule,expected', [
    ('Host(`a.example.com`)', (['a.example.com'], False)),
    ('Host(`a.example.com`) && !Host(`b.example.com`)', (['a.example.com'], False)),
    ('! Host(`b.example.com`)', ([], False)),
    ('Host(`a.com`) || Host(`c.com`)', (['a.com', 'c.com'], False)),
    ('HostSNI(`db.example.com`)', (['db.example.com'], False)),
    ('HostSNI(`*`)', (['*'], False)),
    ('Host("a.example.com")', (['a.example.com'], False)),
    ('Host(`a.com`, `b.com`)', (['a.com', 'b.com'], False)),
    ('HostRegexp(`^.+[.]example[.]com$`)', ([], True)),
    ('HostSNIRegexp(`^.+$`)', ([], True)),
    ('Host(`a.com`) && HostRegexp(`^x$`)', (['a.com'], True)),
    ('PathPrefix(`/api`)', ([], False)),
    ('Host(`*.example.com`)', (['*.example.com'], False)),
    ('', ([], False)),
    (None, ([], False)),
])
def test_every_rule_form_traefik_accepts_is_read(rule, expected):
    assert cfg.rule_host_patterns(rule) == expected


def test_the_old_host_reader_still_behaves():
    assert cfg.rule_hosts('Host(`a.com`) && !Host(`b.com`)') == ['a.com']


@pytest.mark.parametrize('cert_domain,host,expected', [
    ('example.com', 'example.com', True),
    ('*.example.com', 'a.example.com', True),
    ('*.example.com', 'a.b.example.com', False),
    ('*.example.com', 'example.com', False),
    ('*.example.com', '*.example.com', True),
    ('example.com', 'a.example.com', False),
    ('*.b.example.com', 'a.b.example.com', True),
    ('a.*.example.com', 'a.b.example.com', False),
    ('*', 'localhost', True),
    ('', 'example.com', False),
])
def test_wildcards_match_exactly_one_label(cert_domain, host, expected):
    assert cu.cert_covers_host(cert_domain, host) is expected


def test_names_are_compared_without_case_or_a_trailing_dot():
    assert cu.cert_covers_host(cu.normalize('EXAMPLE.COM'), cu.normalize('example.com.'))
    assert cu.normalize('Bücher.example.com').startswith('xn--')


@pytest.mark.parametrize('pattern,cert_domain,expected', [
    ('app.example.com', '*.example.com', True),
    ('app.example.com', 'app.example.com', True),
    ('a.b.example.com', '*.example.com', False),
    ('example.com', '*.example.com', False),
    ('*.example.com', 'app.example.com', True),
    ('*.example.com', 'a.b.example.com', False),
    ('**.example.com', 'a.b.c.example.com', True),
    ('**.example.com', 'example.com', True),
    ('**.example.com', 'other.com', False),
    ('*', 'anything.com', True),
])
def test_a_rule_pattern_is_matched_against_the_certificate(pattern, cert_domain, expected):
    assert cu.router_pattern_covers(pattern, cert_domain) is expected


def test_a_wildcard_certificate_serving_a_route_is_used():
    out = _verdict([_cert('*.example.com')], [_app('Host(`app.example.com`)')])
    assert out['certs'][0]['unused'] is False


def test_a_certificate_nothing_serves_is_unused():
    out = _verdict([_cert('old.example.com')], [_app('Host(`app.example.com`)')])
    assert out['certs'][0]['unused'] is True


def test_a_tcp_route_counts_through_host_sni():
    out = _verdict([_cert('db.example.com')], [_app('HostSNI(`db.example.com`)', protocol='tcp')])
    assert out['certs'][0]['unused'] is False


def test_a_passthrough_route_terminates_no_tls_here():
    apps = [_app('HostSNI(`db.example.com`)', tls={'passthrough': True}, protocol='tcp')]
    assert cu.terminates_tls(apps[0]) is False


def test_a_wildcard_request_does_not_make_every_sibling_look_used():
    certs = [_cert('sonarr.example.com'), _cert('dead.example.com'),
             _cert('example.com', ['*.example.com'])]
    apps  = [_app('Host(`sonarr.example.com`)', tls_domains=[{'main': 'example.com', 'sans': ['*.example.com']}])]
    out   = _verdict(certs, apps)
    verdicts = {r['main']: r['unused'] for r in out['certs']}
    assert verdicts['dead.example.com'] is True, \
        'one route asking for a wildcard hid every dead per-subdomain certificate'
    assert verdicts['sonarr.example.com'] is False, 'a route serves it'
    assert verdicts['example.com'] is False, 'this is the certificate that was asked for'


def test_a_wildcard_certificate_still_covers_what_a_route_serves():
    certs = [_cert('example.com', ['*.example.com']), _cert('dead.example.com')]
    apps  = [_app('Host(`app.example.com`)')]
    verdicts = {r['main']: r['unused'] for r in _verdict(certs, apps)['certs']}
    assert verdicts['example.com'] is False, 'app.example.com is served from it'
    assert verdicts['dead.example.com'] is True


def test_a_generated_default_certificate_is_matched_exactly_too():
    configs = [{'tls': {'stores': {'default': {'defaultGeneratedCert': {
        'resolver': 'le', 'domain': {'main': 'fallback.example.org', 'sans': ['*.example.org']}}}}}}]
    certs = [_cert('fallback.example.org', ['*.example.org']), _cert('dead.example.org')]
    verdicts = {r['main']: r['unused'] for r in
                _verdict(certs, [_app('Host(`app.example.com`)')], configs=configs)['certs']}
    assert verdicts['fallback.example.org'] is False
    assert verdicts['dead.example.org'] is True, \
        'the generated certificate names a wildcard, it does not serve every subdomain'


def test_a_pre_issued_certificate_is_not_unused():
    apps = [_app('Host(`app.example.com`)', tls_domains=[{'main': '*.other.com', 'sans': ['other.com']}])]
    out  = _verdict([_cert('*.other.com')], apps)
    assert out['certs'][0]['unused'] is False, 'tls.domains pre-issues on purpose'


def test_the_default_generated_certificate_is_not_unused():
    configs = [{'tls': {'stores': {'default': {'defaultGeneratedCert': {
        'resolver': 'le', 'domain': {'main': 'fallback.example.org', 'sans': ['x.example.org']}}}}}}]
    out = _verdict([_cert('fallback.example.org')], [_app('Host(`app.example.com`)')], configs=configs)
    assert out['certs'][0]['unused'] is False, 'it is served whenever nothing else matches'


def test_a_route_disabled_in_the_ui_still_holds_its_certificate():
    app = _app('Host(`app.example.com`)')
    app['enabled'] = False
    out = _verdict([_cert('app.example.com')], [app])
    assert out['certs'][0]['unused'] is False, 'disabling is reversible, deleting the cert is not'


@pytest.mark.parametrize('kwargs,reason', [
    ({'routers_ok': False}, cu.UNKNOWN_NO_ROUTERS),
    ({'configs_ok': False}, cu.UNKNOWN_CONFIG),
])
def test_an_incomplete_picture_never_calls_anything_unused(kwargs, reason):
    out = cu.analyze([_cert('old.example.com')], [_app('Host(`app.example.com`)')], **kwargs)
    assert out['unused_known'] is False
    assert out['why'] == reason
    assert out['certs'][0]['unused'] is False


def test_a_regexp_router_makes_the_answer_unknowable():
    out = _verdict([_cert('old.example.com')], [_app('HostRegexp(`^.+$`)')])
    assert out['unused_known'] is False and out['why'] == cu.UNKNOWN_REGEXP


def test_a_catch_all_router_can_be_served_any_certificate():
    out = _verdict([_cert('old.example.com')], [_app('HostSNI(`*`)', protocol='tcp')])
    assert out['unused_known'] is False and out['why'] == cu.UNKNOWN_CATCH_ALL


def test_a_catch_all_without_tls_does_not_block_the_answer():
    out = _verdict([_cert('old.example.com')], [_app('HostSNI(`*`)', tls=False, protocol='tcp')])
    assert out['unused_known'] is True


def test_a_certificate_with_no_domain_is_left_alone():
    out = _verdict([_cert('', [])], [_app('Host(`app.example.com`)')])
    assert out['certs'][0]['unused'] is False and out['certs'][0]['why']


def test_expiry_is_independent_of_everything_else():
    past   = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    future = (datetime.now(timezone.utc) + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    out = cu.analyze([_cert('a.com', not_after=past), _cert('b.com', not_after=future),
                      _cert('c.com', not_after=None), _cert('d.com', not_after='nonsense')],
                     [], routers_ok=False)
    assert [c['expired'] for c in out['certs']] == [True, False, False, False]


def test_an_expired_certificate_in_use_is_still_in_use():
    past = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    out  = _verdict([_cert('app.example.com', not_after=past)], [_app('Host(`app.example.com`)')])
    assert out['certs'][0]['expired'] is True and out['certs'][0]['unused'] is False


def test_a_resolver_missing_from_the_static_config_is_orphaned():
    out = _verdict([_cert('a.com', resolver='gone')], [], resolvers=['letsencrypt'])
    assert out['certs'][0]['orphaned'] is True


def test_a_resolver_that_is_configured_is_not_orphaned():
    out = _verdict([_cert('a.com', resolver='letsencrypt')], [], resolvers=['letsencrypt', 'ovh'])
    assert out['certs'][0]['orphaned'] is False


def test_without_the_static_config_no_resolver_is_called_orphaned():
    out = _verdict([_cert('a.com', resolver='gone')], [], resolvers=None)
    assert out['certs'][0]['orphaned'] is False
    assert out['resolvers_known'] is False
    assert out['certs'][0]['resolver_why'] == cu.UNKNOWN_NO_STATIC


def test_a_file_certificate_has_no_resolver_to_orphan():
    out = _verdict([_cert('a.com', resolver='file')], [], resolvers=['letsencrypt'])
    assert out['certs'][0]['orphaned'] is False and 'resolver_why' not in out['certs'][0]
