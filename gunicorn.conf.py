import os


def _int(name, default, low, high):
    try:
        value = int(str(os.environ.get(name, '')).strip() or default)
    except ValueError:
        return default
    return max(low, min(high, value))


bind               = os.environ.get('GUNICORN_BIND', '0.0.0.0:5000')
worker_class       = 'gthread'
workers            = _int('WEB_CONCURRENCY', 2, 1, 16)
threads            = _int('GUNICORN_THREADS', 4, 1, 64)
timeout            = _int('GUNICORN_TIMEOUT', 60, 15, 900)
graceful_timeout   = _int('GUNICORN_GRACEFUL_TIMEOUT', 30, 5, 300)
keepalive          = _int('GUNICORN_KEEPALIVE', 5, 0, 75)
worker_connections = _int('GUNICORN_WORKER_CONNECTIONS', 200, 16, 2000)
loglevel           = os.environ.get('GUNICORN_LOG_LEVEL', 'info')
