from google.adk.plugins.base_plugin import BasePlugin
from typing import Optional, Dict, Any
import google.generativeai as genai
import requests
import os
import json

# LLM 응답을 생성하기 위한 import
try:
    from google.genai.types import Content, Part
    from google.adk.models.llm_response import LlmResponse
except ImportError:
    # fallback
    Content = None
    Part = None
    LlmResponse = None

class PolicyEnforcementPlugin(BasePlugin):
    """IAM 기반 정책 집행 플러그인 - 프롬프트, 툴 인자, 응답 검증"""
    
    def __init__(self, agent_id: str, gemini_api_key: str, policy_server_url: str, log_server_url: str):
        super().__init__(name=f"policy_enforcement_{agent_id}")
        self.agent_id = agent_id
        self.policy_server_url = policy_server_url
        self.log_server_url = log_server_url
        
        # Gemini 설정 (프롬프트 검증용)
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
        else:
            self.model = None
        
        # 정책 캐시
        self.policies = None
        self.fetch_policies()
    
    def fetch_policies(self):
        """IAM 서버에서 에이전트별 정책 가져오기"""
        try:
            resp = requests.get(f"{self.policy_server_url}/api/iam/policy/{self.agent_id}", timeout=3)
            resp.raise_for_status()
            self.policies = resp.json()
            print(f"[PolicyPlugin] {self.agent_id} 정책 로드 완료")
        except Exception as e:
            print(f"[PolicyPlugin] 정책 로드 실패: {e}")
            self.policies = {"policies": {}}
    
    async def before_model_callback(
        self,
        *,
        callback_context,
        llm_request,
        **kwargs
    ):
        """프롬프트 검증 - LLM 호출 전"""
        if not self.policies or not self.policies.get("policies", {}).get("prompt_validation", {}).get("enabled"):
            return None
        
        # 최신 사용자 메시지 추출
        user_prompt = self._extract_user_message(llm_request)
        
        # 디버깅
        print(f"[PolicyPlugin][{self.agent_id}] 프롬프트 검사: {user_prompt[:100]}..." if len(user_prompt) > 100 else f"[PolicyPlugin][{self.agent_id}] 프롬프트 검사: {user_prompt}")
        
        # 정책 검증
        prompt_policy = self.policies["policies"]["prompt_validation"]
        system_prompt = prompt_policy.get("system_prompt", "")
        
        verdict = await self._inspect_with_llm(system_prompt, user_prompt)
        print(f"[PolicyPlugin][{self.agent_id}] 판정: {verdict}")
        
        if verdict != "SAFE":
            # 위반 로그 전송
            self._send_log({
                "agent_id": self.agent_id,
                "event": "prompt_validation",
                "policy_type": "prompt",
                "user_prompt": user_prompt,
                "verdict": "VIOLATION",
                "reason": "프롬프트가 시스템 정책을 위반했습니다."
            })
            
            # 거부 메시지 반환
            violation_message = (
                f"[{self.agent_id}] 죄송합니다. 귀하의 요청이 시스템 정책에 위반되어 처리할 수 없습니다.\n\n"
                "위반 사유: 시스템 프롬프트에서 정의한 보안 및 사용 정책을 준수하지 않는 요청입니다.\n"
                "정책에 부합하는 요청을 다시 시도해주시기 바랍니다."
            )
            
            return self._create_llm_response(violation_message)
        
        # 통과
        return None
    
    async def before_tool_callback(
        self,
        *,
        tool,
        tool_args: Dict[str, Any],
        tool_context
    ) -> Optional[Dict]:
        """툴 인자 검증 - 툴 호출 전"""
        if not self.policies or not self.policies.get("policies", {}).get("tool_validation", {}).get("enabled"):
            return None
        
        tool_name = tool.name if hasattr(tool, 'name') else str(tool)
        
        print(f"[PolicyPlugin][{self.agent_id}] 툴 검증: {tool_name} {tool_args}")
        
        tool_policy = self.policies["policies"]["tool_validation"]
        rules = tool_policy.get("rules", {})
        
        # 툴별 규칙 확인
        if tool_name in rules:
            rule = rules[tool_name]
            violation = self._check_tool_rule(tool_name, tool_args, rule)
            
            if violation:
                # 위반 로그
                self._send_log({
                    "agent_id": self.agent_id,
                    "event": "tool_validation",
                    "policy_type": "tool",
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "verdict": "BLOCKED",
                    "reason": violation
                })
                
                # 툴 호출 차단 - 에러 메시지 반환
                print(f"[PolicyPlugin][{self.agent_id}] 툴 차단: {violation}")
                return {"error": f"Tool call blocked: {violation}"}
        
        # 통과
        return None
    
    def _extract_user_message(self, llm_request) -> str:
        """최신 사용자 메시지만 추출"""
        user_prompt = ""
        if hasattr(llm_request, 'contents') and llm_request.contents:
            for content in reversed(llm_request.contents):
                if hasattr(content, 'role') and content.role == 'user':
                    if hasattr(content, 'parts') and content.parts:
                        for part in content.parts:
                            if hasattr(part, 'text') and part.text is not None:
                                user_prompt += part.text
                    break
        return user_prompt
    
    async def _inspect_with_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Gemini를 사용한 프롬프트 검증"""
        if not self.model or not user_prompt:
            return "SAFE"
        
        try:
            inspect_prompt = (
                f"{system_prompt}\n\n"
                f"검사 대상 프롬프트:\n\"{user_prompt}\"\n\n"
                "응답은 SAFE 또는 VIOLATION 둘 중 하나로만 해주세요."
            )
            response = self.model.generate_content([inspect_prompt])
            result = response.text.strip().split()[0].upper()
            return result
        except Exception as e:
            print(f"[PolicyPlugin] LLM 검증 실패: {e}")
            return "SAFE"  # 오류 시 통과 (fail-open)
    
    def _check_tool_rule(self, tool_name: str, tool_args: Dict, rule: Dict) -> Optional[str]:
        """툴 규칙 검증"""
        # allowed_agents 확인
        if "allowed_agents" in rule:
            agent_name = tool_args.get("agent_name", "")
            if agent_name and agent_name not in rule["allowed_agents"]:
                return f"Agent '{agent_name}' is not allowed for this tool"
        
        # max_task_length 확인
        if "max_task_length" in rule:
            task = tool_args.get("task", "")
            if len(task) > rule["max_task_length"]:
                return f"Task length ({len(task)}) exceeds maximum ({rule['max_task_length']})"
        
        # requires_auth 확인
        if rule.get("requires_auth") and not tool_args.get("auth_token"):
            return "Authentication required for this tool"
        
        # max_results 확인
        if "max_results" in rule:
            limit = tool_args.get("limit", 9999)
            if limit > rule["max_results"]:
                return f"Requested limit ({limit}) exceeds maximum ({rule['max_results']})"
        
        return None
    
    def _create_llm_response(self, message: str):
        """LLM 응답 객체 생성"""
        try:
            if Content is not None and Part is not None and LlmResponse is not None:
                response_content = Content(
                    role="model",
                    parts=[Part(text=message)]
                )
                return LlmResponse(content=response_content)
        except Exception as e:
            print(f"[PolicyPlugin] LlmResponse 생성 실패: {e}")
        
        # fallback: RuntimeError
        raise RuntimeError(message)
    
    def _send_log(self, payload: Dict[str, Any]):
        """로그 서버에 전송"""
        try:
            requests.post(f"{self.log_server_url}/api/log", json=payload, timeout=2)
        except Exception:
            pass

