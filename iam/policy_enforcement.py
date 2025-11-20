"""Reusable IAM policy enforcement plugin for ADK-based agents."""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, Optional, Sequence

import jwt
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
        self._jwt_secret = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY")
        self._jwt_public_key = os.getenv("JWT_PUBLIC_KEY")
        self._jwt_algorithm = os.getenv("JWT_ALGORITHM") or os.getenv("ALGORITHM") or "HS256"
        self._jwt_audience = os.getenv("JWT_AUDIENCE")
        self._last_auth_token: str | None = None
        self._captured_token_hint: str | None = None
        self._last_policy_fetch_token: str | None = None

        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            self._models[self._DEFAULT_MODEL] = genai.GenerativeModel(self._DEFAULT_MODEL)

        self.fetch_policy()

    # ------------------------------------------------------------------
    # Policy retrieval helpers
    # ------------------------------------------------------------------
    def fetch_policy(
        self,
        *,
        tool_context: Any = None,
        tool_args: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> None:
        """Fetch the latest IAM policy for the configured agent."""
        token_for_logging = self._extract_auth_token(tool_context, tool_args or {})
        token_changed = token_for_logging != self._last_policy_fetch_token
        should_refresh = force or token_changed or not self.policy

        try:
            if should_refresh:
                resp = requests.get(
                    f"{self.policy_server_url}/api/iam/policy/{self.agent_id}",
                    timeout=3,
                )
                resp.raise_for_status()
                self.policy = resp.json()
                if token_for_logging:
                    self._last_policy_fetch_token = token_for_logging

            self._log_policy_fetch(token_for_logging or self._last_policy_fetch_token or "")
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
        self._capture_auth_from_context(callback_context)
        self.fetch_policy(tool_context=callback_context)
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
        callback_context: Any = None,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """Validate tool invocations against IAM tool rules."""
        self._capture_auth_from_context(callback_context or tool_context)
        self.fetch_policy(tool_context=callback_context or tool_context, tool_args=tool_args)

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

        violation = self._check_tool_rule(tool_name, tool_args, rule, tool_context)
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
        if not rules:
            policies = self.policy.get("policies")
            if isinstance(policies, dict):
                prompt_validation = policies.get("prompt_validation") or {}
                system_prompt = prompt_validation.get("system_prompt", "")
                model = prompt_validation.get("model")
                enabled = prompt_validation.get("enabled", True)
                if system_prompt:
                    rules = [
                        {
                            "system_prompt": system_prompt,
                            "model": model,
                            "enabled": enabled,
                        }
                    ]

        enabled_rules = []
        for rule in rules:
            enabled = rule.get("enabled", True)
            if isinstance(enabled, str):
                enabled = enabled.lower() not in {"false", "0", "off"}
            if enabled and rule.get("system_prompt"):
                enabled_rules.append(rule)
        return enabled_rules

    def _get_tool_rules(self) -> Dict[str, Dict[str, Any]]:
        rules = self.policy.get("tool_validation_rules")

        if not rules:
            policies = self.policy.get("policies")
            if isinstance(policies, dict):
                tool_validation = policies.get("tool_validation") or {}
                enabled = tool_validation.get("enabled", True)
                if isinstance(enabled, str):
                    enabled = enabled.lower() not in {"false", "0", "off"}
                if not enabled:
                    return {}
                rules = tool_validation.get("rules")

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
        tool_context: Any,
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
        if requires_auth and not self._extract_auth_token(tool_context, tool_args):
            return "Authentication required for this tool"

        required_roles = rule.get("required_roles") or rule.get("required_role")
        normalized_roles = self._normalize_required_roles(required_roles)
        if normalized_roles:
            claims = self._get_auth_claims(tool_context, tool_args)
            user_roles = self._extract_roles_from_claims(claims)
            if not user_roles:
                return "Role information missing from JWT token"
            if not self._roles_satisfied(user_roles, normalized_roles):
                return f"Tool '{tool_name}' requires role(s): {', '.join(normalized_roles)}"

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
    # Authentication helpers
    # ------------------------------------------------------------------
    def _log_policy_fetch(self, token: str) -> None:
        base_message = f"[PolicyPlugin] {self.agent_id} 정책 로드 완료"

        if not token:
            print(f"{base_message} (auth_token=<none>)")
            return

        claims = self._decode_jwt(token)
        roles = self._extract_roles_from_claims(claims)
        subject = claims.get("sub") or claims.get("email") or claims.get("user") or "<unknown>"
        token_preview = token if len(token) <= 18 else f"{token[:10]}...{token[-6:]}"
        print(f"{base_message} (subject={subject}, roles={roles or []}, token={token_preview})")

    def _capture_auth_from_context(self, callback_context: Any) -> None:
        token = self._extract_token_from_container(callback_context)
        if token:
            self._captured_token_hint = token

    def _extract_auth_token(self, tool_context: Any, tool_args: Dict[str, Any]) -> str:
        tool_args = tool_args or {}
        candidates = [
            tool_args.get("auth_token"),
            tool_args.get("token"),
            tool_args.get("Authorization"),
            tool_args.get("authorization"),
        ]

        candidates.append(self._extract_token_from_container(tool_context))
        candidates.append(self._extract_token_from_container(getattr(tool_context, "metadata", None)))

        if self._captured_token_hint:
            candidates.append(self._captured_token_hint)

        if self._last_auth_token:
            candidates.append(self._last_auth_token)

        for candidate in candidates:
            cleaned = self._sanitize_bearer(candidate)
            if cleaned:
                return cleaned
        return ""

    def _extract_token_from_container(self, container: Any, _visited: Optional[set[int]] = None) -> str:
        if not container:
            return ""

        if _visited is None:
            _visited = set()

        ident = id(container)
        if ident in _visited:
            return ""
        _visited.add(ident)

        if isinstance(container, dict):
            headers = container.get("headers") or container
            for key in ("Authorization", "authorization", "auth_token", "token"):
                if key in headers:
                    return self._sanitize_bearer(headers.get(key))

            for nested_key in (
                "headers",
                "metadata",
                "context",
                "raw_request",
                "request",
                "envelope",
            ):
                nested = headers.get(nested_key)
                cleaned = self._extract_token_from_container(nested, _visited)
                if cleaned:
                    return cleaned

            for value in headers.values():
                cleaned = self._extract_token_from_container(value, _visited)
                if cleaned:
                    return cleaned

        if isinstance(container, (list, tuple, set)):
            for item in container:
                cleaned = self._extract_token_from_container(item, _visited)
                if cleaned:
                    return cleaned

        for attr in ("headers", "metadata", "context", "raw_request", "request"):
            candidate = getattr(container, attr, None)
            cleaned = self._extract_token_from_container(candidate, _visited)
            if cleaned:
                return cleaned

        return ""

    def _get_auth_claims(self, tool_context: Any, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        token = self._extract_auth_token(tool_context, tool_args)
        if not token:
            return {}
        claims = self._decode_jwt(token)
        if claims:
            repeated_token = token == self._last_auth_token
            self._log_token_inspection(token, claims, repeated=repeated_token)
            self._log_policy_binding(token, claims)
            self._last_auth_token = token
        return claims

    def _decode_jwt(self, token: str) -> Dict[str, Any]:
        options = {"verify_signature": bool(self._jwt_secret or self._jwt_public_key)}
        verify_args: Dict[str, Any] = {"algorithms": [self._jwt_algorithm]}

        if self._jwt_audience:
            verify_args["audience"] = self._jwt_audience

        key = self._jwt_public_key or self._jwt_secret
        try:
            if key:
                return jwt.decode(token, key=key, options=options, **verify_args)
            return jwt.decode(token, options={"verify_signature": False})
        except Exception as exc:  # pragma: no cover - runtime token parsing
            print(f"[PolicyPlugin] JWT decode 실패: {exc}")
            return {}

    def _log_token_inspection(self, token: str, claims: Dict[str, Any], *, repeated: bool = False) -> None:
        roles = self._extract_roles_from_claims(claims)
        subject = claims.get("sub") or claims.get("email") or claims.get("user")
        token_preview = token if len(token) <= 18 else f"{token[:10]}...{token[-6:]}"
        event = "JWT 재사용" if repeated else "JWT 로드"
        print(
            "[PolicyPlugin][{}] {}: sub={}, roles={}, token={}".format(
                self.agent_id, event, subject or "<unknown>", roles or [], token_preview
            )
        )

    def _log_policy_binding(self, token: str, claims: Dict[str, Any]) -> None:
        roles = self._extract_roles_from_claims(claims)
        subject = claims.get("sub") or claims.get("email") or claims.get("user") or "<unknown>"
        token_preview = token if len(token) <= 18 else f"{token[:10]}...{token[-6:]}"
        rule_keys = sorted(self._get_tool_rules().keys())
        rule_summary = ", ".join(rule_keys) if rule_keys else "<no tool rules>"
        print(
            "[PolicyPlugin][{}] 정책 적용: subject={}, roles={}, token={}, rules={}".format(
                self.agent_id, subject, roles or [], token_preview, rule_summary
            )
        )

    def _normalize_required_roles(self, required_roles: Any) -> list[str]:
        if not required_roles:
            return []
        if isinstance(required_roles, str):
            required_roles = [required_roles]
        if isinstance(required_roles, Iterable):
            return [str(role).strip().lower() for role in required_roles if str(role).strip()]
        return []

    def _extract_roles_from_claims(self, claims: Dict[str, Any]) -> list[str]:
        if not isinstance(claims, dict):
            return []
        roles: list[str] = []
        for key in ("roles", "role", "permissions", "scopes", "scope"):
            value = claims.get(key)
            if isinstance(value, str):
                roles.extend(item.strip().lower() for item in value.split() if item.strip())
            elif isinstance(value, Iterable):
                roles.extend(str(item).strip().lower() for item in value if str(item).strip())
        return roles

    def _roles_satisfied(self, user_roles: list[str], required_roles: list[str]) -> bool:
        user_role_set = {role.lower() for role in user_roles}
        return any(role.lower() in user_role_set for role in required_roles)

    @staticmethod
    def _sanitize_bearer(token: Any) -> str:
        if not token:
            return ""
        token_str = str(token).strip()
        if token_str.lower().startswith("bearer "):
            return token_str[7:].strip()
        return token_str
