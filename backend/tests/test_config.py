import pytest
from pydantic import ValidationError

from app.config import BACKEND_DIR, Settings
from app.main import create_app


def test_environment_is_loaded_by_app_factory(monkeypatch):
    monkeypatch.setenv("AGENTGATE_APP_NAME", "Configured AgentGate")
    monkeypatch.setenv("AGENTGATE_ENVIRONMENT", "test")
    monkeypatch.setenv("AGENTGATE_CORS_ORIGINS", '["http://localhost:4321"]')

    settings = create_app().state.settings
    assert settings.app_name == "Configured AgentGate"
    assert settings.environment == "test"
    assert settings.cors_origins == ["http://localhost:4321"]


def test_environment_file_and_process_override(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENTGATE_APP_NAME", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("AGENTGATE_APP_NAME=From file\n", encoding="utf-8")
    assert Settings(_env_file=env_file).app_name == "From file"

    monkeypatch.setenv("AGENTGATE_APP_NAME", "From process")
    assert Settings(_env_file=env_file).app_name == "From process"


def test_environment_file_path_does_not_depend_on_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert Settings.model_config["env_file"] == BACKEND_DIR / ".env"
    assert BACKEND_DIR.is_absolute()


def test_invalid_environment_fails_configuration(monkeypatch):
    monkeypatch.setenv("AGENTGATE_ENVIRONMENT", "typo")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_cors_requires_a_list():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins="*")
