from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, Tuple

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ReDNACoreDemo.devx.backend import api, stack_api, supervisor
from scripts import cppp_bootstrap
from ReDNACoreDemo.devx.backend.readiness_client import poll_stack_readiness
import ReDNACoreDemo.core.api as core_api
from ReDNACoreDemo.devx.backend import config_resolver


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _prepare_stub_environment(tmp_path: Path) -> Tuple[Path, Dict[str, str], Path]:
    root_dir = Path(__file__).resolve().parents[1]
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    mods_dir = tmp_path / "mods"
    (mods_dir / "ReDNACoreDemo" / "devx" / "backend").mkdir(parents=True)
    (mods_dir / "uvicorn").mkdir(parents=True)
    (mods_dir / "httpx").mkdir(parents=True)

    lsof_stub = textwrap.dedent(
        """\
        #!/usr/bin/env bash
        STATE=\"${SMOKE_STUB_STATE}\"
        port=\"\"
        for arg in "$@"; do
          case "$arg" in
            -iTCP:*) port="${arg#-iTCP:}" ;;
          esac
        done
        if [[ -n "$port" && -f "$STATE/port_${port}.up" ]]; then
          exit 0
        fi
        exit 1
        """
    )
    _write_executable(bin_dir / "lsof", lsof_stub)

    curl_stub = textwrap.dedent(
        """\
        #!/usr/bin/env bash
        STATE=\"${SMOKE_STUB_STATE}\"
        url=\"\"
        while [[ $# -gt 0 ]]; do
          case "$1" in
            http://*|https://*)
              url="$1"
              shift
              ;;
            --retry|--retry-delay)
              shift
              shift
              ;;
            --max-time|-f|-s|-S|--silent)
              shift
              ;;
            *)
              shift
              ;;
          esac
        done
        if [[ -z "$url" ]]; then
          exit 0
        fi
        if [[ "$url" == *"/devx/api/stack/ready"* ]]; then
          counter_file="$STATE/ready_counter"
          count=0
          if [[ -f "$counter_file" ]]; then
            count="$(cat "$counter_file")"
          fi
          if [[ "$count" == "0" ]]; then
            echo "1" > "$counter_file"
            exit 0
          fi
          echo '{"ready": true, "status": "ready"}'
          exit 0
        fi
        if [[ "$url" == *"/devx/api/stack/config"* ]]; then
          config_path="$STATE/stack_config.json"
          if [[ -f "$config_path" ]]; then
            cat "$config_path"
          else
            echo '{"core_base":"http://127.0.0.1:8001","ucnrr_base":"http://127.0.0.1:8011","devx_base":"http://127.0.0.1:8100","core_port":8001,"ucnrr_port":8011,"devx_port":8100,"warnings":[],"source":{"core_base":"DEFAULT","ucnrr_base":"DEFAULT","devx_base":"DEFAULT","core_port":"DEFAULT","ucnrr_port":"DEFAULT","devx_port":"DEFAULT"}}'
          fi
          exit 0
        fi
        if [[ "$url" == *"/devx/api/stack/restart"* ]]; then
          exit 0
        fi
        hostport="${url#*://}"
        hostport="${hostport%%/*}"
        port="${hostport##*:}"
        if [[ -f "$STATE/port_${port}.up" ]]; then
          exit 0
        fi
        exit 7
        """
    )
    _write_executable(bin_dir / "curl", curl_stub)

    readiness_stub = textwrap.dedent(
        """\
        class ReadinessResult:
            def __init__(self):
                self.ready = True
                self.resilience_used = True
                self.seeded = True
                self.last_payload = {"ready": True}
                self.last_error = None


        def poll_stack_readiness(**_kwargs):
            print("(seeded window)")
            return ReadinessResult()


        __all__ = ["ReadinessResult", "poll_stack_readiness"]
        """
    )
    (mods_dir / "ReDNACoreDemo" / "__init__.py").write_text("", encoding="utf-8")
    (mods_dir / "ReDNACoreDemo" / "devx" / "__init__.py").write_text("", encoding="utf-8")
    (mods_dir / "ReDNACoreDemo" / "devx" / "backend" / "__init__.py").write_text("", encoding="utf-8")
    (mods_dir / "ReDNACoreDemo" / "devx" / "backend" / "readiness_client.py").write_text(readiness_stub, encoding="utf-8")

    httpx_stub = textwrap.dedent(
        """\
        class Timeout:
            def __init__(self, connect=None, read=None, write=None, **_kwargs):
                self.connect = connect
                self.read = read
                self.write = write

        class _Resp:
            def __init__(self, status_code=200, payload=None):
                self.status_code = status_code
                self._payload = payload or {"ok": True}

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise RuntimeError(f"status {self.status_code}")

            def json(self):
                return dict(self._payload)

            @property
            def text(self):
                try:
                    import json as _json
                    return _json.dumps(self._payload)
                except Exception:  # pragma: no cover - best effort
                    return "{}"

        class Client:
            def __init__(self, timeout=None):
                self.timeout = timeout

            def post(self, url, json=None, **kwargs):
                if url and url.endswith("/devx/api/stack/restart"):
                    return _Resp(status_code=200, payload={"ok": True})
                if json and isinstance(json, dict):
                    evidence = json.get("evidence") or []
                    if evidence and isinstance(evidence[0], dict):
                        value = evidence[0].get("value") or {}
                        if "enum" in value:
                            return _Resp(status_code=200, payload={"ok": True})
                return _Resp(status_code=400, payload={"error": "EVIDENCE_VALIDATION_FAILED"})

            def close(self):
                pass

            def get(self, url, **kwargs):
                return _Resp()

        def post(url, json=None, **kwargs):
            return Client().post(url, json=json, **kwargs)

        def get(url, **kwargs):
            return Client().get(url, **kwargs)

        class ReadTimeout(Exception):
            pass

        class ConnectTimeout(Exception):
            pass

        __all__ = ["Timeout", "Client", "post", "get", "ReadTimeout", "ConnectTimeout"]
        """
    )
    (mods_dir / "httpx" / "__init__.py").write_text(httpx_stub, encoding="utf-8")

    uvicorn_stub = textwrap.dedent(
        """\
        import os
        import sys
        import time
        from pathlib import Path

        state = Path(os.environ["SMOKE_STUB_STATE"])
        port = "0"
        args = sys.argv[1:]
        if "--port" in args:
            idx = args.index("--port")
            if idx + 1 < len(args):
                port = args[idx + 1]
        marker = state / f"port_{port}.up"
        marker.write_text("", encoding="utf-8")
        time.sleep(0.05)
        """
    )
    (mods_dir / "uvicorn" / "__init__.py").write_text("", encoding="utf-8")
    (mods_dir / "uvicorn" / "__main__.py").write_text(uvicorn_stub, encoding="utf-8")

    (state_dir / "ready_counter").write_text("0", encoding="utf-8")

    default_config = {
        "core_base": "http://127.0.0.1:8001",
        "ucnrr_base": "http://127.0.0.1:8011",
        "devx_base": "http://127.0.0.1:8100",
        "core_port": 8001,
        "ucnrr_port": 8011,
        "devx_port": 8100,
        "warnings": [],
        "source": {
            "core_base": "DEFAULT",
            "ucnrr_base": "DEFAULT",
            "devx_base": "DEFAULT",
            "core_port": "DEFAULT",
            "ucnrr_port": "DEFAULT",
            "devx_port": "DEFAULT",
        },
    }
    (state_dir / "stack_config.json").write_text(json.dumps(default_config), encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["PYTHONPATH"] = f"{mods_dir}:{env.get('PYTHONPATH', '')}"
    env["SMOKE_STUB_STATE"] = str(state_dir)
    env["HOME"] = str(tmp_path)
    env["REDNA_HOME"] = str(state_dir / "redna")
    env["STACK_UP_SKIP_BOOTSTRAP"] = "1"
    env["STACK_UP_PYTHON_BIN"] = sys.executable
    env["SMOKE_PYTHON_BIN"] = sys.executable
    return root_dir, env, state_dir


def test_stack_up_uses_resolved_config_ports(tmp_path: Path) -> None:
    root_dir, env, state_dir = _prepare_stub_environment(tmp_path)
    env["STACK_CONFIG_ONLY_FAST"] = "1"
    config_payload = {
        "core_base": "http://127.0.0.1:8004",
        "ucnrr_base": "http://127.0.0.1:8017",
        "devx_base": "http://127.0.0.1:8018",
        "core_port": 8004,
        "ucnrr_port": 8017,
        "devx_port": 8018,
        "warnings": [],
        "source": {
            "core_base": "ENVFILE",
            "ucnrr_base": "ENVFILE",
            "devx_base": "ENVFILE",
            "core_port": "ENVFILE",
            "ucnrr_port": "ENVFILE",
            "devx_port": "ENVFILE",
        },
    }
    env["STACK_CONFIG_JSON"] = json.dumps(config_payload)
    for port in ("8004", "8017", "8018"):
        (state_dir / f"port_{port}.up").write_text("", encoding="utf-8")

    script_path = root_dir / "scripts" / "stack_up.sh"
    result = subprocess.run(
        [str(script_path), "--use-config-only"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    stdout = result.stdout
    assert "CORE_BASE  = http://127.0.0.1:8004" in stdout
    assert "UCNRR_BASE = http://127.0.0.1:8017" in stdout
    assert "DEVX_BASE  = http://127.0.0.1:8018" in stdout
    assert "Stack ready" in stdout


def test_smoke_honors_stack_config_json(tmp_path: Path) -> None:
    root_dir, env, state_dir = _prepare_stub_environment(tmp_path)
    env["STACK_CONFIG_ONLY_FAST"] = "1"
    config_payload = {
        "core_base": "http://127.0.0.1:8004",
        "ucnrr_base": "http://127.0.0.1:8017",
        "devx_base": "http://127.0.0.1:8018",
        "core_port": 8004,
        "ucnrr_port": 8017,
        "devx_port": 8018,
        "warnings": ["ucnrr_base_port_mismatch"],
        "source": {
            "core_base": "ENVFILE",
            "ucnrr_base": "ENVFILE",
            "devx_base": "ENVFILE",
            "core_port": "ENVFILE",
            "ucnrr_port": "ENVFILE",
            "devx_port": "ENVFILE",
        },
    }
    env["STACK_CONFIG_JSON"] = json.dumps(config_payload)
    for port in ("8004", "8017", "8018"):
        (state_dir / f"port_{port}.up").write_text("", encoding="utf-8")

    script_path = root_dir / "scripts" / "smoke.sh"
    result = subprocess.run(
        [str(script_path), "--use-config-only"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    stdout = result.stdout
    assert "core_base : http://127.0.0.1:8004" in stdout
    assert "ucnrr_base: http://127.0.0.1:8017" in stdout
    assert "devx_base : http://127.0.0.1:8018" in stdout
    assert "SMOKE OK" in stdout
@pytest.mark.parametrize("interactive", [False])
def test_bootstrap_script(monkeypatch: pytest.MonkeyPatch, interactive: bool) -> None:
    service_pids: Dict[str, int] = {}

    async def fake_health(service: stack_api.ServiceDefinition, port: int, attempts: int = 10, delay: float = 1.0) -> Dict[str, str]:
        return {"status": "healthy", "port": port}

    def fake_start(service: stack_api.ServiceDefinition, port: int) -> int:
        pid = 1000 + hash(service.key) % 100
        service_pids[service.key] = pid
        return pid

    monkeypatch.setattr(cppp_bootstrap, "_ensure_port", lambda svc: svc.port)
    monkeypatch.setattr(cppp_bootstrap.stack_api, "_start_service_sync", fake_start)
    monkeypatch.setattr(cppp_bootstrap, "_await_health", fake_health)

    rc = cppp_bootstrap.bootstrap_stack(interactive=interactive)
    assert rc == 0
    assert set(service_pids) == {"ucnrr", "core", "devx"}


def test_restart_via_api(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_kill(service: stack_api.ServiceDefinition) -> None:
        return None

    async def fake_start(service: stack_api.ServiceDefinition, port: int) -> int:
        return 4321

    async def fake_wait(service: stack_api.ServiceDefinition, port: int, attempts: int = 10, delay: float = 1.0) -> Dict[str, str]:
        return {"status": "healthy"}

    monkeypatch.setattr(stack_api, "_kill_service", fake_kill)
    monkeypatch.setattr(stack_api, "_start_service", fake_start)
    monkeypatch.setattr(stack_api, "_wait_for_health", fake_wait)
    monkeypatch.setattr(stack_api, "_tail_json", lambda *_args, **_kwargs: [])

    client = TestClient(api.app)
    response = client.post("/devx/api/stack/restart", json={"service": "core", "port": 8015})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "started"
    assert payload["pid"] == 4321


def test_readiness_reports_core_port_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stack_api, "stack_log", lambda *a, **k: None)

    def fake_resolver(overrides=None):
        core_base = os.getenv("CORE_BASE", "http://127.0.0.1:8001")
        core_port = int(os.getenv("CORE_PORT", "8001"))
        return {
            "core_base": core_base,
            "ucnrr_base": "http://127.0.0.1:8011",
            "devx_base": "http://127.0.0.1:8100",
            "core_port": core_port,
            "ucnrr_port": 8011,
            "devx_port": 8100,
            "warnings": [],
            "source": {
                "core_base": "ENV",
                "ucnrr_base": "ENV",
                "devx_base": "ENV",
                "core_port": "ENV",
                "ucnrr_port": "ENV",
                "devx_port": "ENV",
            },
        }

    monkeypatch.setattr(config_resolver, "resolve_stack_config", fake_resolver)
    monkeypatch.setattr(stack_api, "resolve_stack_config", fake_resolver)

    def fake_processes() -> Dict[str, Any]:
        return {
            "core": [
                {
                    "pid": 4242,
                    "port": 8004,
                    "cmd": "python -m uvicorn ReDNACoreDemo.core.api --port 8004",
                }
            ],
            "ucnrr": [],
            "devx": [],
        }

    monkeypatch.setattr(stack_api, "_enumerate_service_processes", fake_processes)
    monkeypatch.setenv("CORE_BASE", "http://127.0.0.1:8001")
    monkeypatch.setenv("CORE_PORT", "8001")
    config_resolver.clear_env_cache()

    client = TestClient(api.app)
    conflict_response = client.get("/devx/api/stack/ready")
    conflict_payload = conflict_response.json()

    assert conflict_payload["ready"] is False
    assert "port_conflict" in conflict_payload["fail_conditions"]
    assert any(item["action"] == "core_port_conflict" for item in conflict_payload["action_required"])

    monkeypatch.setenv("CORE_BASE", "http://127.0.0.1:8004")
    monkeypatch.setenv("CORE_PORT", "8004")
    config_resolver.clear_env_cache()
    stack_api.READINESS_CACHE = stack_api.ReadinessCache()

    resolved_payload = client.get("/devx/api/stack/ready").json()
    assert "port_conflict" not in resolved_payload["fail_conditions"]
    assert resolved_payload["action_required"] == []


def test_supervisor_restarts_core_when_rr_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(supervisor, "stack_log", lambda *a, **k: None)

    state = {
        "services": {
            "core": {"pid": 1111, "last_restart": None, "restart_timestamps": []},
            "ucnrr": {"pid": 2222, "last_restart": None, "restart_timestamps": []},
        },
        "history": [],
    }

    monkeypatch.setattr(supervisor, "_load_state", lambda: state)
    monkeypatch.setattr(supervisor, "_save_state", lambda _state: None)
    monkeypatch.setattr(supervisor, "_pid_alive", lambda pid: pid == 1111)
    monkeypatch.setenv("UCNRR_BASE", "http://127.0.0.1:8011")
    monkeypatch.setattr(supervisor, "_core_requires_env_refresh", lambda _config: True)

    restart_calls: list[Tuple[str, Dict[str, Any]]] = []

    def fake_restart(
        service: supervisor.ServiceName,
        st: Dict[str, Any],
        stack_config: Dict[str, Any],
        reason: str,
        force: bool,
    ) -> Tuple[str, Optional[int]]:
        restart_calls.append((service, {"reason": reason, "force": force}))
        st["services"][service]["pid"] = 3333
        return "restarted", 3333

    monkeypatch.setattr(supervisor, "_restart_service_locked", fake_restart)

    pid = supervisor.ensure_process("core")
    assert pid == 3333
    assert restart_calls and restart_calls[0][0] == "core"


def test_poll_stack_readiness_retries_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    class FlakyClient:
        def __init__(self):
            self.calls = 0

        def get(self, url: str) -> Any:
            self.calls += 1
            if self.calls == 1:
                request = httpx.Request("GET", url)
                raise httpx.ReadTimeout("timeout", request=request)
            return type(
                "Resp",
                (),
                {
                    "status_code": 200,
                    "raise_for_status": staticmethod(lambda: None),
                    "json": staticmethod(lambda: {"ready": True, "status": "ready"}),
                },
            )()

        def close(self) -> None:
            pass

    result = poll_stack_readiness(
        devx_base="http://devx.example",
        core_base="http://core.example",
        timeout=5.0,
        poll_interval=0.0,
        seed_after=5.0,
        restart_after=10.0,
        session=FlakyClient(),
        seed_func=None,
        restart_func=None,
        sleep_func=lambda _: None,
    )

    assert result.ready is True
    assert result.resilience_used is False


def test_core_health_timeout_returns_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCNRR_BASE", "http://127.0.0.1:9999")
    monkeypatch.setenv("CORE_HEALTH_CONNECT_TIMEOUT_MS", "10")
    monkeypatch.setenv("CORE_HEALTH_READ_TIMEOUT_MS", "10")
    monkeypatch.setattr(core_api, "LAST_HEALTH_DEGRADED_LOG_TS", None)
    monkeypatch.setattr(core_api, "stack_log", lambda *a, **k: None, raising=False)

    original_get = httpx.get

    def fake_get(url: str, timeout: httpx.Timeout):
        request = httpx.Request("GET", url)
        raise httpx.ReadTimeout("timeout", request=request)

    monkeypatch.setattr(core_api.httpx, "get", fake_get)

    app = core_api.build_app()
    client = TestClient(app)
    response = client.get("/health")
    payload = response.json()
    assert payload["rr_mode"] == "degraded"
    assert payload["ucnrr_probe_timed_out"] is True

    monkeypatch.setattr(core_api.httpx, "get", original_get)


def test_smoke_bootstrap_full_stack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root_dir, env, state_dir = _prepare_stub_environment(tmp_path)
    env["STACK_CONFIG_ONLY_FAST"] = "1"
    smoke_script = root_dir / 'scripts' / 'smoke.sh'

    result = subprocess.run(
        ['bash', str(smoke_script)],
        cwd=root_dir,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert 'SMOKE OK' in result.stdout

    (state_dir / 'ready_counter').write_text('0', encoding='utf-8')
    stack_env = env.copy()
    stack_env['STACK_UP_SKIP_BOOTSTRAP'] = '1'
    stack_up_script = root_dir / 'scripts' / 'stack_up.sh'
    trace = subprocess.run(
        ['bash', '-x', str(stack_up_script)],
        cwd=root_dir,
        capture_output=True,
        text=True,
        env=stack_env,
    )
    assert trace.returncode == 0, trace.stderr
    assert '✅ Stack ready' in trace.stdout
    assert 'Readiness :' in trace.stdout
    for line in trace.stderr.splitlines():
        stripped = line.strip()
        if stripped.startswith('+ ') and stripped.endswith('/.venv/bin/python'):
            pytest.fail('stack_up.sh invoked bare venv python')
