import logging


def _info_lines(caplog, path):
    return [r for r in caplog.records if r.levelno >= logging.INFO and path in r.getMessage()]


def test_health_checks_from_a_monitor_do_not_log_at_info(client, caplog):
    caplog.set_level(logging.DEBUG)
    res = client.get('/api/health', environ_base={'REMOTE_ADDR': '192.0.2.10'})
    assert res.status_code == 200
    assert not _info_lines(caplog, '/api/health')


def test_other_requests_still_log_at_info(client, caplog):
    caplog.set_level(logging.DEBUG)
    client.get('/api', environ_base={'REMOTE_ADDR': '192.0.2.10'})
    assert _info_lines(caplog, '→ GET /api')
