import importlib
from pathlib import Path


def test_settings_resolve_state_dir_relative_to_tb_home(monkeypatch, tmp_path):
    monkeypatch.setenv("TB_HOME", str(tmp_path))

    import config.settings as settings_module

    settings_module = importlib.reload(settings_module)
    try:
        settings = settings_module.Settings(state_dir="state")
        assert settings_module.APP_HOME == tmp_path.resolve()
        assert settings.state_dir == str((tmp_path / "state").resolve())
        assert settings_module.Settings.model_config["env_file"] == str(tmp_path / ".env")
    finally:
        monkeypatch.delenv("TB_HOME", raising=False)
        importlib.reload(settings_module)


def test_settings_keep_absolute_state_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("TB_HOME", str(tmp_path / "app-home"))
    absolute_state = tmp_path / "custom-state"

    import config.settings as settings_module

    settings_module = importlib.reload(settings_module)
    try:
        settings = settings_module.Settings(state_dir=str(absolute_state))
        assert settings.state_dir == str(absolute_state.resolve())
    finally:
        monkeypatch.delenv("TB_HOME", raising=False)
        importlib.reload(settings_module)
