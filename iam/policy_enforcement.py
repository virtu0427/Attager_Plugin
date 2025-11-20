"""Reusable IAM policy enforcement plugin for ADK-based agents."""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence
from dataclasses import dataclass

import google.generativeai as genai
import requests
from google.adk.plugins.base_plugin import BasePlugin

try:  # Optional imports for building ADK responses gracefully
    from google.genai.types import Content, Part
    from google.adk.models.llm_response import LlmResponse
except ImportError:  # pragma: no cover - fallback for environments without these extras
    Content = None  # type: ignore[assignment]
    Part = None  # type: ignore[assignment]
    LlmResponse = None  # type: ignore[assignment]


class PolicyEnforcementPlugin(BasePlugin):
    """IAM 기반 정책 집행 플러그인."""

    _DEFAULT_MODEL = "gemini-2.0-flash"

    def __init__(
        self,
        *,
        agent_id: str,
        gemini_api_key: Optional[str],
        policy_server_url: str,
        log_server_url: str,
    ) -> None:
        super().__init__(name=f"policy_enforcement_{agent_id}")
        self.agent_id = agent_id
        self.policy_server_url = policy_server_url.rstrip("/")
        self.log_server_url = log_server_url.rstrip("/")
        self.gemini_api_key = gemini_api_key
        self._models: Dict[str, Any] = {}
        self.policy: Dict[str, Any] = {}

        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            self._models[self._DEFAULT_MODEL] = genai.GenerativeModel(self._DEFAULT_MODEL)

        self.fetch_policy()

    # ------------------------------------------------------------------
    # Policy retrieval helpers
    # ------------------------------------------------------------------
    def fetch_policy(self) -> None:
        """Fetch the latest IAM policy for the configured agent."""
        try:
            resp = requests.get(
                f"{self.policy_server_url}/api/iam/policy/{self.agent_id}",
                timeout=3,
            )
            resp.raise_for_status()
            self.policy = resp.json()
            print(f"[PolicyPlugin] {self.agent_id} 정책 로드 완료")
        except Exception as exc:  # pragma: no cover - network failures during runtime
            print(f"[PolicyPlugin] 정책 로드 실패: {exc}")
            self.policy = {}

    # ------------------------------------------------------------------
    # ADK callbacks
    # ------------------------------------------------------------------
    async def before_model_callback(
        self,
        *,
        callback_context: Any,
        llm_request: Any,
        **kwargs: Any,
    ) -> Optional[Any]:
        """Validate user prompts before the LLM is invoked."""
        if not self._policy_enabled():
            return None

        prompt_rules = self._get_prompt_rules()
        if not prompt_rules:
            return None

        user_prompt = self._extract_user_message(llm_request)
        if not user_prompt:
            return None

        rule = prompt_rules[0]
        system_prompt = rule.get("system_prompt", "")
        model_name = rule.get("model")

        verdict = await self._inspect_with_llm(system_prompt, user_prompt, model_name)
        print(f"[PolicyPlugin][{self.agent_id}] 프롬프트 판정: {verdict}")

        if verdict != "SAFE":
            self._send_log(
                {
                    "agent_id": self.agent_id,
                    "policy_type": "prompt_validation",
                    "prompt": user_prompt,
                    "verdict": "VIOLATION",
                    "reason": "사용자 프롬프트가 IAM 정책을 위반했습니다.",
                }
            )
            violation_message = (
                f"[{self.agent_id}] 죄송합니다. 귀하의 요청이 시스템 정책에 위반되어 처리할 수 없습니다.\n\n"
                "위반 사유: 시스템 프롬프트에서 정의한 보안 및 사용 정책을 준수하지 않는 요청입니다.\n"
                "정책에 부합하는 요청을 다시 시도해주시기 바랍니다."
            )
            return self._create_llm_response(violation_message)

        return None

    async def before_tool_callback(
        self,
        *,
        tool: Any,
        tool_args: Dict[str, Any],
        tool_context: Any,
    ) -> Optional[Dict[str, Any]]:
        """Validate tool invocations against IAM tool rules."""
        if not self._policy_enabled():
            return None

        tool_rules = self._get_tool_rules()
        if not tool_rules:
            return None

        tool_name = getattr(tool, "name", str(tool))
        print(f"[PolicyPlugin][{self.agent_id}] 툴 검증: {tool_name} {tool_args}")

        rule = tool_rules.get(tool_name)
        if not rule:
            return None

        user_ctx = self._extract_user_context(tool_context)

        violation = self._check_tool_rule(tool_name, tool_args, rule, user_ctx)
        if violation:
            self._send_log(
                {
                    "agent_id": self.agent_id,
                    "policy_type": "tool_validation",
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "verdict": "BLOCKED",
                    "reason": violation,
                }
            )
            print(f"[PolicyPlugin][{self.agent_id}] 툴 차단: {violation}")
            return {"error": f"Tool call blocked: {violation}"}

        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _policy_enabled(self) -> bool:
        if not self.policy:
            return False
        enabled = self.policy.get("enabled", True)
        if isinstance(enabled, str):
            enabled = enabled.lower() not in {"false", "0", "off"}
        return bool(enabled)

    def _get_prompt_rules(self) -> Sequence[Dict[str, Any]]:
        rules = self.policy.get("prompt_validation_rules", []) or []
        enabled_rules = []
        for rule in rules:
            enabled = rule.get("enabled", True)
            if isinstance(enabled, str):
                enabled = enabled.lower() not in {"false", "0", "off"}
            if enabled and rule.get("system_prompt"):
                enabled_rules.append(rule)
        return enabled_rules

    def _get_tool_rules(self) -> Dict[str, Dict[str, Any]]:
        rules = self.policy.get("tool_validation_rules") or {}
        if isinstance(rules, dict):
            return rules
        return {}

    def _extract_user_message(self, llm_request: Any) -> str:
        message = ""
        if hasattr(llm_request, "contents") and llm_request.contents:
            for content in reversed(llm_request.contents):
                role = getattr(content, "role", None)
                if role == "user" and getattr(content, "parts", None):
                    for part in content.parts:
                        text = getattr(part, "text", None)
                        if text:
                            message += text
                    break
        return message

    async def _inspect_with_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        model_name: Optional[str],
    ) -> str:
        if not system_prompt or not self.gemini_api_key:
            return "SAFE"

        model = self._resolve_model(model_name)
        if model is None:
            return "SAFE"

        try:
            inspect_prompt = (
                f"{system_prompt}\n\n"
                f"검사 대상 프롬프트:\n\"{user_prompt}\"\n\n"
                "응답은 SAFE 또는 VIOLATION 둘 중 하나로만 해주세요."
            )
            response = model.generate_content([inspect_prompt])
            verdict = (response.text or "").strip().split()[0].upper()
            return verdict if verdict in {"SAFE", "VIOLATION"} else "SAFE"
        except Exception as exc:  # pragma: no cover - runtime LLM failures
            print(f"[PolicyPlugin] LLM 검증 실패: {exc}")
            return "SAFE"

    def _resolve_model(self, model_name: Optional[str]):
        name = model_name or self._DEFAULT_MODEL
        if name in self._models:
            return self._models[name]
        if not self.gemini_api_key:
            return None
        try:
            model = genai.GenerativeModel(name)
            self._models[name] = model
            return model
        except Exception as exc:  # pragma: no cover - runtime model resolution issues
            print(f"[PolicyPlugin] 모델 로드 실패({name}): {exc}")
            return self._models.get(self._DEFAULT_MODEL)

    def _check_tool_rule(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        rule: Dict[str, Any],
        user_ctx: "_UserContext",
    ) -> Optional[str]:
        allowed_agents = rule.get("allowed_agents")
        if allowed_agents:
            agent_name = tool_args.get("agent_name") or tool_args.get("agent")
            if agent_name and agent_name not in allowed_agents:
                return f"Agent '{agent_name}' is not allowed for {tool_name}"

        max_task_length = rule.get("max_task_length")
        if isinstance(max_task_length, int):
            task = tool_args.get("task", "") or ""
            if len(task) > max_task_length:
                return f"Task length ({len(task)}) exceeds maximum ({max_task_length})"

        requires_auth = rule.get("requires_auth")
        if isinstance(requires_auth, str):
            requires_auth = requires_auth.lower() not in {"false", "0", "off"}
        if requires_auth:
            auth_token = tool_args.get("auth_token") or user_ctx.jwt_token
            if not auth_token:
                return "Authentication required for this tool"

            # 표준 Authorization 스킴을 도구 인자에 전파 (툴 구현부가 필요 시 활용)
            if user_ctx.jwt_scheme and "auth_scheme" not in tool_args:
                tool_args["auth_scheme"] = user_ctx.jwt_scheme
            if user_ctx.user_email and "user_email" not in tool_args:
                tool_args["user_email"] = user_ctx.user_email
            tool_args.setdefault("auth_token", auth_token)

        max_results = rule.get("max_results")
        if isinstance(max_results, int):
            limit = tool_args.get("limit")
            if isinstance(limit, int) and limit > max_results:
                return f"Requested limit ({limit}) exceeds maximum ({max_results})"

        return None

    def _create_llm_response(self, message: str):
        if Content and Part and LlmResponse:
            try:
                response_content = Content(role="model", parts=[Part(text=message)])
                return LlmResponse(content=response_content)
            except Exception as exc:  # pragma: no cover
                print(f"[PolicyPlugin] LlmResponse 생성 실패: {exc}")
        raise RuntimeError(message)

    def _send_log(self, payload: Dict[str, Any]) -> None:
        try:
            requests.post(
                f"{self.log_server_url}/api/logs",
                json=payload,
                timeout=2,
            )
        except Exception:  # pragma: no cover - logging best-effort
            pass

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------
    def _extract_user_context(self, tool_context: Any) -> "_UserContext":
        """Pull JWT/email information from the runner state.

        ADK의 ToolContext는 상태 정보를 `state` 딕셔너리에 보관한다. 오케스트레이터가
        `state_delta`로 전달한 JWT 토큰/스킴/이메일 값을 우선적으로 추출하여 도구 검증 시
        사용할 수 있도록 한다.
        """

        state = getattr(tool_context, "state", None) or {}
        jwt_token = state.get("user_jwt_token") or state.get("user_auth_header")
        jwt_scheme = state.get("user_jwt_scheme")
        user_email = state.get("user_email")

        # user_auth_header는 "Bearer <token>" 형태일 수 있으므로 분리
        if jwt_token and not jwt_scheme and isinstance(jwt_token, str) and " " in jwt_token:
            scheme, _, token = jwt_token.partition(" ")
            jwt_scheme = scheme or None
            jwt_token = token or jwt_token

        return _UserContext(jwt_token=jwt_token, jwt_scheme=jwt_scheme, user_email=user_email)


@dataclass
class _UserContext:
    jwt_token: Optional[str]
    jwt_scheme: Optional[str]
    user_email: Optional[str]
