import core.env as env
from conftest import CONFIG_DIR_PATHS, SETTINGS_PATH


def test_core_env_still_points_at_the_conftest_paths():
    assert env.SETTINGS_PATH == str(SETTINGS_PATH), (
        'a test file reloaded core.env under its own environment and never put it back, so every '
        'file after it reads a dead tmp_path: %r' % env.SETTINGS_PATH)
    assert env.CONFIG_PATHS == CONFIG_DIR_PATHS, (
        'core.config was left pointing at another test the dynamic config: %r' % env.CONFIG_PATHS)
