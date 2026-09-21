import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_TMP = Path(tempfile.mkdtemp(prefix="tm-tests-"))
_CONFIG_DIR = _TMP / "config"
_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

SETTINGS_PATH = _CONFIG_DIR / "manager.yml"
DYNAMIC_PATH = _CONFIG_DIR / "dynamic.yml"
BACKUP_DIR = _TMP / "backups"

SETTINGS_PATH.write_text(
    "domains:\n"
    "  - example.com\n"
    "cert_resolver: letsencrypt\n"
    "traefik_api_url: http://traefik:8080\n"
    "auth_enabled: true\n"
    "setup_complete: true\n"
    "must_change_password: false\n"
    "password_hash: '$2b$12$abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQR'\n"
)
DYNAMIC_PATH.write_text("http:\n  routers: {}\n  services: {}\n")
STATIC_PATH = _CONFIG_DIR / "traefik.yml"
STATIC_PATH.write_text("providers:\n  docker: {}\n")

CONFIG_DIR_PATHS = [str(DYNAMIC_PATH)]

os.environ["SETTINGS_PATH"] = str(SETTINGS_PATH)
os.environ["CONFIG_PATHS"] = str(DYNAMIC_PATH)
os.environ["BACKUP_DIR"] = str(BACKUP_DIR)
os.environ["TRAEFIK_API_URL"] = "http://traefik.invalid:8080"
os.environ["STATIC_CONFIG_PATH"] = str(STATIC_PATH)
_GIT_CONFIG = _TMP / "gitconfig"
_GIT_CONFIG.write_text(
    "[user]\n\tname = Traefik Manager Tests\n\temail = tests@localhost\n"
    "[init]\n\tdefaultBranch = main\n"
)
os.environ["GIT_CONFIG_GLOBAL"] = str(_GIT_CONFIG)
os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
import core.monitor as _tm_monitor

if not hasattr(_tm_monitor, 'real_start'):
    _tm_monitor.real_start = _tm_monitor.start
    _tm_monitor.start = lambda: False

import app as tm

EMPTY_CONFIG = "http:\n  routers: {}\n  services: {}\n"


@pytest.fixture(autouse=True)
def clean_config():
    DYNAMIC_PATH.write_text(EMPTY_CONFIG)
    _reset_settings()
    _reset_rate_limits()
    yield
    DYNAMIC_PATH.write_text(EMPTY_CONFIG)


def _reset_rate_limits():
    try:
        import app as _app
        _app.limiter.reset()
    except Exception:
        pass
    from core import auth as _auth_mod
    _auth_mod.reset_otp_attempts()


def _reset_settings():
    s = tm.load_settings()
    tm.save_settings(
        domains=s["domains"],
        cert_resolver=s["cert_resolver"],
        traefik_api_url=s["traefik_api_url"],
        auth_enabled=s["auth_enabled"],
        password_hash=s["password_hash"],
        visible_tabs=s["visible_tabs"],
        disabled_routes={},
        managed_middlewares={},
        must_change_password=False,
        setup_password_reset=False,
        session_epoch=0,
        admin_password_fp='',
    )


@pytest.fixture
def client():
    c = tm.app.test_client()
    with c.session_transaction() as s:
        s["authenticated"] = True
        s["csrf_token"] = "testtoken"
    return c


@pytest.fixture
def anon_client():
    return tm.app.test_client()


@pytest.fixture
def restore_core_env():
    yield
    import importlib
    import core.env as env_mod
    import core.config as config_mod
    os.environ["SETTINGS_PATH"] = str(SETTINGS_PATH)
    os.environ["CONFIG_PATHS"] = str(DYNAMIC_PATH)
    os.environ["BACKUP_DIR"] = str(BACKUP_DIR)
    os.environ["STATIC_CONFIG_PATH"] = str(STATIC_PATH)
    os.environ.pop("CONFIG_PATH", None)
    importlib.reload(env_mod)
    importlib.reload(config_mod)


@pytest.fixture
def config_path():
    return DYNAMIC_PATH


@pytest.fixture
def app_module():
    return tm


def read_config():
    from ruamel.yaml import YAML
    yaml = YAML()
    with open(DYNAMIC_PATH) as f:
        return yaml.load(f) or {}


def write_config(text):
    DYNAMIC_PATH.write_text(text)


def post_form(client, path, **form):
    form.setdefault("csrf_token", "testtoken")
    return client.post(path, data=form, headers={
        "X-CSRF-Token": "testtoken",
        "X-Requested-With": "fetch",
    })


def post_json(client, path, payload):
    import json
    body = dict(payload)
    body.setdefault("csrf_token", "testtoken")
    return client.post(path, data=json.dumps(body), content_type="application/json",
                       headers={"X-CSRF-Token": "testtoken", "X-Requested-With": "fetch"})
