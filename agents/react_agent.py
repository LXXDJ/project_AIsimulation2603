from environment.state import GameState
from environment.personality import Personality
from llm.client import LLMClient
from memory.compressor import compress_history
from .base_agent import BaseAgent


REFLECTION_PROMPT = """
당신은 회사원 시뮬레이션의 전략 컨설턴트입니다.
에이전트가 지난 {window}일간 실행한 행동과 결과를 분석하고, 생존과 승진을 위한 구체적 행동 배분을 처방하세요.

[!] 중요: 성향에 맞는 행동만 반복하면 특정 스탯만 올라가고 승진 요건을 못 채워 해고됩니다.
승진에 필요한 스탯(업무능력, 성과, 상사신뢰, 평판) 중 부족한 것을 집중적으로 올리는 행동을 처방하세요.
성향과 다른 행동이라도 생존을 위해 반드시 필요합니다.

{personality_section}

[ 승진 요건 vs 현재 스탯 ]
{promotion_gap}

[ 해고/퇴직 조건 ]
- 성과 부진: 성과 < 20 AND 상사신뢰 < 20 → 즉시 해고
- 승진 미달: 경력 5년차에 대리 미만, 8년차에 과장 미만, 15년차에 부장 미만 → 권고사직/명예퇴직
- 희망퇴직: 경력 12년+ 시 직급·스트레스·성향에 따라 자발적 퇴직 가능성
  [!] 스트레스가 높고 체력이 낮으면 희망퇴직 확률이 크게 상승한다!
  스트레스 80+ → 퇴직확률 +15%, 체력 20 이하 → +10%
  반대로 스트레스 20 이하, 체력 80 이상이면 퇴직 욕구가 크게 감소한다.
- 번아웃: 스트레스 90+ AND 체력 10 이하 30일 지속 → 자진퇴사

[!][!] 체력/스트레스 관리 필수 원칙 [!][!]
- 체력 30 이하 또는 스트레스 70 이상이면 반드시 휴가를 처방에 포함하세요.
- 야근은 스트레스를 급격히 올리고 체력을 깎으므로, 스트레스 50 이상일 때는 절대 처방하지 마세요.
- 장기 생존이 승진보다 중요합니다. 죽으면 승진도 없습니다.

[ 행동별 효과 참고 ]
- 프로젝트에 집중한다: 업무능력↑ 성과↑ (승진 핵심)
- 야근한다: 업무능력↑ 성과↑↑ (단, 스트레스↑↑ 체력↓↓ — 남용 금지!)
- 상사와 점심을 먹는다: 상사신뢰↑ (승진 핵심)
- 동료를 도와준다: 동료관계↑ 평판↑
- 자기계발을 한다: 업무능력↑
- 정치적으로 행동한다: 정치능력↑ 상사신뢰↑ (단, 평판에 도움 안됨)
- 휴가를 쓴다: 스트레스↓↓ 체력↑↑ (생존 핵심!)

[ 지난 {window}일 행동 기록 ]
{history_summary}

[ 현재 상태 ]
{current_state}

[ 에피소딕 메모리 (주요 과거 경험) ]
{memory_text}

다음 형식으로 정확히 응답하세요:

평가: (지난 기간 행동 비율과 스탯 변화를 수치로 평가. 어떤 행동을 너무 많이/적게 했는지 지적)
문제점: (승진 요건 대비 가장 부족한 스탯을 구체적 수치와 함께 지적. 해고 데드라인까지 남은 시간도 언급)
처방: 다음 90일 행동 배분 (30일 기준):
- (행동명) X일 (이유)
- (행동명) Y일 (이유)
- (행동명) Z일 (이유)
합계 30일. 반드시 부족한 스탯을 올리는 행동을 최우선으로 배분하세요.
""".strip()


SYSTEM_PROMPT = """
당신은 회사원 시뮬레이션 에이전트입니다.
목표: 20년(7300일) 안에 최대한 높은 직급과 연봉을 달성하고 해고되지 않는다.
{personality_section}

[ 이직 전략 ]
- 이직 결과는 현재 스탯에 따라 달라진다: 시장가치 높으면 연봉 30~40%↑+직급 점프, 낮으면 오히려 더 힘든 환경으로.
- '이직 준비를 한다'를 반복(10~15일)하면 이직 발생. 성과·평판이 높을 때 이직하라.

매 턴마다 현재 상태를 보고, 다음 형식으로 응답하세요:

Thought: (현재 상황에 대한 간단한 판단)
Action: (아래 행동 중 하나를 정확히 그대로 출력)

가능한 행동 목록:
{actions}
""".strip()

BATCH_SYSTEM_PROMPT = """
당신은 회사원 시뮬레이션 에이전트입니다.
목표: 20년(7300일) 안에 최대한 높은 직급과 연봉을 달성하고 해고되지 않는다.
{personality_section}

[ 이직 전략 가이드 ]
- 이직 결과는 현재 '시장가치(업무능력·성과·평판)'에 따라 극적으로 달라진다.
  • 시장가치 높음(72+): 프리미엄 오퍼 — 연봉 30~40%↑, 직급 점프 가능, 좋은 환경에서 시작
  • 시장가치 보통(48~71): 일반 조건 — 연봉 15%↑, 적응 부담 있음
  • 시장가치 낮음(~47): 도피성 이직 — 연봉 5%↑에 그치고, 새 환경이 오히려 더 힘들어짐
- 스탯이 충분히 높을 때 이직하면 연봉·직급을 단번에 끌어올릴 수 있다.
- 반대로 성과·평판이 낮은 상태에서 이직하면 더 나쁜 환경으로 이직해 악순환에 빠진다.
- '이직 준비를 한다'를 반복(10~15일)하면 이직 발생. 헤드헌터 연락 시 준비 기간 단축.
- 같은 직급 2년 이상 정체 시 이직이 경력 돌파구가 될 수 있다.

{memory_section}
현재 상태를 보고 앞으로 {n}일간의 행동 계획을 세우세요.

[!] 핵심 원칙: "최우선 전략 지침"이 위에 있다면, 그 처방된 행동 배분을 반드시 따르세요.
성향에 맞는 행동만 반복하면 특정 스탯만 편중되어 승진 요건을 못 채우고 해고됩니다.
처방된 비율대로 행동을 배분하되, 스트레스가 80 이상이면 휴가를 우선 배치하세요.

다음 형식으로 정확히 응답하세요:

Thought: (현재 상황 판단 — 특히 전략 지침에서 지적한 부족 스탯을 어떻게 올릴지)
Day 1: (행동)
Day 2: (행동)
...
Day {n}: (행동)

가능한 행동 목록 (정확히 그대로 출력):
{actions}
""".strip()


class ReActAgent(BaseAgent):
    """ReAct 에이전트: Thought → Action + 에피소딕 메모리 & 히스토리 압축 & Reflection."""

    base_name = "ReAct"

    def __init__(self, llm: LLMClient, personality: Personality | None = None,
                 llm_reflect: LLMClient | None = None):
        super().__init__(llm, personality, llm_reflect=llm_reflect)
        personality_section = (
            f"\n당신의 성향: {personality.name}\n{personality.description}"
            if personality else ""
        )
        self._system = SYSTEM_PROMPT.format(
            actions=self._actions_list(),
            personality_section=personality_section,
        )
        self._batch_system_template = BATCH_SYSTEM_PROMPT.replace(
            "{personality_section}", personality_section
        )

    def decide(self, state: GameState, observation: str) -> str:
        messages = [{"role": "user", "content": observation}]
        response = self.llm.call(system=self._system, messages=messages)
        return self._parse_action(response)

    def _build_memory_section(self) -> str:
        """에피소딕 메모리 + 히스토리 압축 + Reflection을 프롬프트용 텍스트로 조합한다."""
        parts = []

        # Reflection 결과 (최우선 전략 지침 — 반드시 따라야 함)
        if self._reflection:
            parts.append(
                f"[!][!][!] 최우선 전략 지침 (자기성찰 결과) [!][!][!]\n"
                f"아래 처방된 행동 배분을 반드시 따르세요. 성향과 다르더라도 생존을 위해 필수입니다.\n"
                f"{self._reflection}\n"
                f"[!] 위 처방을 무시하고 성향대로만 행동하면 해고됩니다."
            )

        # 에피소딕 메모리: 최근 중요 사건 10개
        memory_text = self.memory.to_text(n=10)
        if memory_text != "기억 없음":
            parts.append(f"[ 과거 주요 경험 ]\n{memory_text}")

        # 히스토리 압축: 최근 30일 행동 패턴 요약 (LLM 호출)
        if len(self.history) >= 30:
            summary = compress_history(self.history, self.llm, window=30)
            if summary:
                parts.append(f"[ 최근 행동 패턴 요약 ]\n{summary}")

        if not parts:
            return ""
        return "\n\n".join(parts)

    def reflect(self, state: GameState, window: int = 90,
                promotion_requirements: dict | None = None) -> str:
        """지난 N일을 돌아보고 전략 개선점을 도출한다. llm_reflect(고급 모델) 사용."""
        if not self.llm_reflect or len(self.history) < window:
            return ""

        # 히스토리 요약 (최근 window일)
        recent = self.history[-window:]
        history_lines = []
        for h in recent:
            events_part = ""
            if "이벤트" in h.get("observation", "") or "승진" in h.get("observation", ""):
                events_part = f" → {h['observation'][:60]}"
            history_lines.append(f"Day {h['day']}: {h['action']}{events_part}")
        history_summary = "\n".join(history_lines)

        # 현재 상태 텍스트
        current_state = state.to_observation()

        # 에피소딕 메모리
        memory_text = self.memory.to_text(n=5)

        # 승진 요건 vs 현재 스탯 갭 계산
        promotion_gap = self._build_promotion_gap(state, promotion_requirements)

        personality_section = (
            f"에이전트 성향: {self.personality.name}\n{self.personality.description}"
            if self.personality else ""
        )

        prompt = REFLECTION_PROMPT.format(
            window=window,
            personality_section=personality_section,
            history_summary=history_summary,
            current_state=current_state,
            memory_text=memory_text,
            promotion_gap=promotion_gap,
        )

        response = self.llm_reflect.call(
            system=prompt, messages=[{"role": "user", "content": "성찰을 시작하세요."}],
            max_tokens=300,
        )
        self._reflection = response.strip()
        return self._reflection

    @staticmethod
    def _build_promotion_gap(state: GameState, requirements: dict | None) -> str:
        """현재 직급의 승진 요건 대비 부족한 스탯을 텍스트로 정리한다."""
        if not requirements:
            return "승진 요건 정보 없음"
        pos = state.position
        req = requirements.get(pos)
        if not req:
            return f"현재 직급({pos})은 최고 직급이거나 승진 요건이 없습니다."

        stat_map = {
            "skill": ("업무능력", state.skill),
            "performance": ("성과", state.performance),
            "boss_favor": ("상사신뢰", state.boss_favor),
            "reputation": ("평판", state.reputation),
        }
        lines = [f"현재 직급: {pos} → 다음 승진 요건:"]
        for key, (label, current) in stat_map.items():
            required = req.get(key, 0)
            gap = required - current
            status = f"부족 {gap:.0f}" if gap > 0 else "충족 ✓"
            lines.append(f"  {label}: {current:.0f} / {required} ({status})")

        min_days = req.get("min_days", 0)
        days_left = max(0, min_days - state.day)
        if days_left > 0:
            lines.append(f"  최소 근무일: {state.day}일 / {min_days}일 (잔여 {days_left}일)")
        else:
            lines.append(f"  최소 근무일: 충족 ✓")

        # 해고 데드라인 경고
        career_days = state.day
        if career_days < 5 * 365:
            remaining = 5 * 365 - career_days
            lines.append(f"\n[!] 경력 5년 해고심사까지 {remaining}일 남음 — 그때까지 대리 이상 필수!")
        elif career_days < 8 * 365:
            remaining = 8 * 365 - career_days
            lines.append(f"\n[!] 경력 8년 해고심사까지 {remaining}일 남음 — 그때까지 과장 이상 필수!")
        elif career_days < 15 * 365:
            remaining = 15 * 365 - career_days
            lines.append(f"\n[!] 경력 15년 명예퇴직 심사까지 {remaining}일 남음 — 그때까지 부장 이상 필수!")

        return "\n".join(lines)

    def decide_batch(self, state: GameState, observation: str, n: int) -> list[str]:
        memory_section = self._build_memory_section()
        system = self._batch_system_template.format(
            n=n, actions=self._actions_list(), memory_section=memory_section,
        )
        messages = [{"role": "user", "content": observation}]
        response = self.llm.call(system=system, messages=messages, max_tokens=64 * n)
        actions = self._parse_batch(response, n)
        return actions

    def _parse_batch(self, text: str, n: int) -> list[str]:
        """Day 1: ... 형식에서 n개의 행동을 추출한다."""
        actions = []
        for i in range(1, n + 1):
            found = None
            for line in text.splitlines():
                if line.strip().startswith(f"Day {i}:"):
                    found = self._parse_action(line)
                    break
            actions.append(found or "프로젝트에 집중한다")
        return actions
