import importlib.util
from pathlib import Path

from click.testing import CliRunner


def load_launcher():
    launcher_path = Path(__file__).resolve().parents[1] / "main.py"
    spec = importlib.util.spec_from_file_location("local_launcher", launcher_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_runs_local_server_with_default_options(monkeypatch):
    launcher = load_launcher()
    calls = []
    monkeypatch.setattr(launcher.uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))

    result = CliRunner().invoke(launcher.main)

    assert result.exit_code == 0
    assert calls == [
        (
            ("app.main:app",),
            {
                "host": "127.0.0.1",
                "port": 8000,
                "reload": False,
                "env_file": Path(__file__).resolve().parents[1] / ".env",
            },
        )
    ]


def test_main_enables_reload_when_requested(monkeypatch):
    launcher = load_launcher()
    calls = []
    monkeypatch.setattr(launcher.uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))

    result = CliRunner().invoke(launcher.main, ["--reload"])

    assert result.exit_code == 0
    assert calls[0][1]["reload"] is True


def test_main_passes_custom_port_to_uvicorn(monkeypatch):
    launcher = load_launcher()
    calls = []
    monkeypatch.setattr(launcher.uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))

    result = CliRunner().invoke(launcher.main, ["--port", "9000"])

    assert result.exit_code == 0
    assert calls[0][1]["port"] == 9000


def test_main_rejects_invalid_port():
    launcher = load_launcher()

    result = CliRunner().invoke(launcher.main, ["--port", "65536"])

    assert result.exit_code == 2


def test_main_rejects_unknown_options():
    launcher = load_launcher()

    result = CliRunner().invoke(launcher.main, ["--host", "0.0.0.0"])

    assert result.exit_code == 2
