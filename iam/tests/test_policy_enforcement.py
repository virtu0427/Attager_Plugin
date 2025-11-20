import os
import sys
from pathlib import Path
from types import SimpleNamespace

import jwt
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from iam.policy_enforcement import PolicyEnforcementPlugin


class DummyResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data

    def raise_for_status(self):
        return None


@pytest.fixture
def policy_payload():
    return {
        "agent_id": "orchestrator",
        "policies": {
            "prompt_validation": {
                "enabled": True,
                "system_prompt": "test prompt policy",
            },
            "tool_validation": {
                "enabled": True,
                "rules": {
                    "call_remote_agent": {
                        "required_roles": ["admin"],
                    }
                },
            },
        },
    }


@pytest.fixture
def plugin(policy_payload, monkeypatch):
    os.environ["SECRET_KEY"] = "testsecret"

    def fake_get(url, timeout):
        return DummyResponse(policy_payload)

    monkeypatch.setattr("iam.policy_enforcement.requests.get", fake_get)
    return PolicyEnforcementPlugin(
        agent_id="orchestrator",
        gemini_api_key=None,
        policy_server_url="http://dummy",  # intercepted by monkeypatch
        log_server_url="http://dummy",
    )


@pytest.mark.asyncio
async def test_admin_token_allows_tool(plugin):
    token = jwt.encode({"roles": ["admin"]}, "testsecret", algorithm="HS256")
    tool_context = {"headers": {"Authorization": f"Bearer {token}"}}
    tool = SimpleNamespace(name="call_remote_agent")

    result = await plugin.before_tool_callback(
        tool=tool,
        tool_args={},
        tool_context=tool_context,
    )

    assert result is None


@pytest.mark.asyncio
async def test_non_admin_token_blocks_tool(plugin):
    token = jwt.encode({"roles": ["user"]}, "testsecret", algorithm="HS256")
    tool_context = {"headers": {"Authorization": f"Bearer {token}"}}
    tool = SimpleNamespace(name="call_remote_agent")

    result = await plugin.before_tool_callback(
        tool=tool,
        tool_args={},
        tool_context=tool_context,
    )

    assert result is not None
    assert "admin" in result.get("error", "").lower()


@pytest.mark.asyncio
async def test_missing_roles_returns_clear_error(plugin):
    token = jwt.encode({"sub": "user@example.com"}, "testsecret", algorithm="HS256")
    tool_context = {"headers": {"Authorization": f"Bearer {token}"}}
    tool = SimpleNamespace(name="call_remote_agent")

    result = await plugin.before_tool_callback(
        tool=tool,
        tool_args={},
        tool_context=tool_context,
    )

    assert result is not None
    assert "role" in result.get("error", "").lower()


@pytest.mark.asyncio
async def test_callback_context_captures_token(plugin, capsys):
    token = jwt.encode({"roles": ["admin"], "sub": "cbctx"}, "testsecret", algorithm="HS256")
    callback_context = {"headers": {"Authorization": f"Bearer {token}"}}
    tool = SimpleNamespace(name="call_remote_agent")

    result = await plugin.before_tool_callback(
        tool=tool,
        tool_args={},
        tool_context={},
        callback_context=callback_context,
    )

    assert result is None
    output = capsys.readouterr().out
    assert "JWT 로드" in output
    assert "cbctx" in output


@pytest.mark.asyncio
async def test_policy_logging_includes_token_and_rules(plugin, capsys):
    token = jwt.encode({"roles": ["admin"], "sub": "policy-log"}, "testsecret", algorithm="HS256")
    tool_context = {"headers": {"Authorization": f"Bearer {token}"}}
    tool = SimpleNamespace(name="call_remote_agent")

    await plugin.before_tool_callback(
        tool=tool,
        tool_args={},
        tool_context=tool_context,
    )

    await plugin.before_tool_callback(
        tool=tool,
        tool_args={},
        tool_context=tool_context,
    )

    output = capsys.readouterr().out
    assert "정책 적용" in output
    assert "policy-log" in output
    assert "call_remote_agent" in output
    assert "JWT 재사용" in output


def test_fetch_policy_logs_token_with_claims(monkeypatch, policy_payload, capsys):
    os.environ["SECRET_KEY"] = "testsecret"
    token = jwt.encode({"roles": ["admin"], "sub": "fetch-log"}, "testsecret", algorithm="HS256")

    def fake_get(url, timeout):
        return DummyResponse(policy_payload)

    monkeypatch.setattr("iam.policy_enforcement.requests.get", fake_get)

    plugin = PolicyEnforcementPlugin(
        agent_id="orchestrator",
        gemini_api_key=None,
        policy_server_url="http://dummy",
        log_server_url="http://dummy",
    )

    capsys.readouterr()
    plugin.fetch_policy(tool_context={"headers": {"Authorization": f"Bearer {token}"}})

    output = capsys.readouterr().out
    assert "정책 로드 완료" in output
    assert "fetch-log" in output
    assert "admin" in output


def test_fetch_policy_reads_nested_context_token(monkeypatch, policy_payload, capsys):
    os.environ["SECRET_KEY"] = "testsecret"
    token = jwt.encode({"roles": ["admin"], "sub": "nested"}, "testsecret", algorithm="HS256")

    def fake_get(url, timeout):
        return DummyResponse(policy_payload)

    monkeypatch.setattr("iam.policy_enforcement.requests.get", fake_get)

    plugin = PolicyEnforcementPlugin(
        agent_id="orchestrator",
        gemini_api_key=None,
        policy_server_url="http://dummy",
        log_server_url="http://dummy",
    )

    capsys.readouterr()
    plugin.fetch_policy(
        tool_context={
            "context": {
                "raw_request": {
                    "headers": {"authorization": f"Bearer {token}"},
                }
            }
        }
    )

    output = capsys.readouterr().out
    assert "정책 로드 완료" in output
    assert "nested" in output


@pytest.mark.asyncio
async def test_policy_fetch_uses_captured_token(plugin, capsys):
    token = jwt.encode({"roles": ["admin"], "sub": "fetch-callback"}, "testsecret", algorithm="HS256")
    capsys.readouterr()
    tool = SimpleNamespace(name="call_remote_agent")

    await plugin.before_tool_callback(
        tool=tool,
        tool_args={},
        tool_context={},
        callback_context={"headers": {"Authorization": f"Bearer {token}"}},
    )

    output = capsys.readouterr().out
    assert "정책 로드 완료" in output
    assert "fetch-callback" in output
