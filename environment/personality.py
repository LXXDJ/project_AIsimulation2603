from dataclasses import dataclass, field


@dataclass
class Personality:
    name: str
    description: str
    # {행동명: {stat: 곱승}} — 정의되지 않은 항목은 기본값 1.0
    action_multipliers: dict[str, dict[str, float]] = field(default_factory=dict)
    # 시작 시 기본 스탯에 더해지는 보너스/페널티
    initial_bonus: dict[str, float] = field(default_factory=dict)
    # 이벤트 티어별 발생 확률 배수 {"company": 1.0, "team": 1.0, "personal": 1.0}
    event_tier_multipliers: dict[str, float] = field(default_factory=dict)
    # 주말 활동 가중치 {"휴식": w, "자기계발": w, "사교": w, "인맥관리": w, "여행": w}
    # 미정의 항목은 기본값 2 적용 (균형형은 전부 미정의 → 동일 확률)
    weekend_weights: dict[str, float] = field(default_factory=dict)

    def get_multiplier(self, action: str, stat: str) -> float:
        return self.action_multipliers.get(action, {}).get(stat, 1.0)

    def get_event_multiplier(self, tier: str) -> float:
        return self.event_tier_multipliers.get(tier, 1.0)


PERSONALITIES: dict[str, Personality] = {
    "균형형": Personality(
        name="균형형",
        description="특별한 강점이나 약점 없이 모든 행동을 평균적으로 수행한다.",
        # 모든 티어 기본값
    ),
    "성과형": Personality(
        name="성과형",
        description=(
            "업무 성과 중심형. 야근과 프로젝트 집중이 특히 효과적이며 스트레스도 잘 견딘다. "
            "반면 사교·정치적 활동은 서툴고 효율이 낮다."
        ),
        action_multipliers={
            "야근한다":           {"skill": 1.4, "performance": 1.5, "stress": 0.8},
            "프로젝트에 집중한다": {"skill": 1.4, "performance": 1.4, "reputation": 1.2, "stress": 0.9},
            "자기계발을 한다":     {"skill": 1.5, "performance": 1.3},
            "상사와 점심을 먹는다": {"boss_favor": 0.7},
            "동료를 도와준다":     {"peer_relation": 0.8},
            "정치적으로 행동한다": {"political_skill": 0.7, "boss_favor": 0.7},
        },
        initial_bonus={"skill": 15.0, "performance": 10.0, "political_skill": -8.0},  # 시작 political_skill: 2
        event_tier_multipliers={"team": 1.5, "personal": 0.7},
        weekend_weights={"자기계발": 5, "휴식": 3, "사교": 1, "인맥관리": 1, "여행": 1},
    ),
    "사교형": Personality(
        name="사교형",
        description=(
            "대인관계 중심형. 상사 관리와 동료 협력이 탁월하고 평판 상승이 빠르다. "
            "단순 업무 집중이나 야근은 상대적으로 비효율적이다."
        ),
        action_multipliers={
            "상사와 점심을 먹는다": {"boss_favor": 1.6, "peer_relation": 1.3},
            "동료를 도와준다":     {"peer_relation": 1.5, "reputation": 1.4},
            "정치적으로 행동한다": {"political_skill": 1.2, "boss_favor": 1.2},
            "야근한다":           {"skill": 0.7, "performance": 0.8, "stress": 1.2},
            "프로젝트에 집중한다": {"skill": 0.8, "performance": 0.85},
            "자기계발을 한다":     {"skill": 0.8},
        },
        initial_bonus={"peer_relation": 10.0, "boss_favor": 5.0, "skill": -5.0, "performance": -3.0, "political_skill": 8.0},  # 시작 performance: 12 (-5→-3), political_skill: 18
        event_tier_multipliers={"personal": 1.5, "company": 0.8},
        weekend_weights={"사교": 5, "휴식": 3, "인맥관리": 2, "자기계발": 1, "여행": 2},
    ),
    "정치형": Personality(
        name="정치형",
        description=(
            "조직 정치 중심형. 상사 관리와 정치적 행동의 효과가 극대화된다. "
            "순수 업무 효율은 낮지만 승진 조건을 빠르게 충족시키는 데 유리하다."
        ),
        action_multipliers={
            "정치적으로 행동한다": {"political_skill": 1.6, "boss_favor": 1.5},
            "상사와 점심을 먹는다": {"boss_favor": 1.4, "political_skill": 1.3},
            "동료를 도와준다":     {"reputation": 1.3, "peer_relation": 1.2},
            "프로젝트에 집중한다": {"skill": 0.7, "performance": 0.8},
            "야근한다":           {"skill": 0.6, "performance": 0.75},
            "자기계발을 한다":     {"skill": 0.7},
        },
        initial_bonus={"political_skill": 25.0, "skill": -3.0, "performance": -2.0},  # 시작 skill: 7, performance: 13, political_skill: 35
        event_tier_multipliers={"company": 1.5, "personal": 1.2},
        weekend_weights={"인맥관리": 5, "사교": 3, "휴식": 2, "자기계발": 1, "여행": 1},
    ),
    "워라밸형": Personality(
        name="워라밸형",
        description=(
            "건강과 지속가능성 중심형. 휴식과 자기계발의 효과가 크고 스트레스를 잘 회복한다. "
            "고강도 업무(야근, 프로젝트 집중)는 상대적으로 비효율적이고 더 많이 소진된다."
        ),
        action_multipliers={
            "휴가를 쓴다":         {"energy": 1.5, "stress": 1.4},
            "이직 준비를 한다":    {"energy": 1.3, "stress": 1.3},
            "자기계발을 한다":     {"performance": 1.2, "stress": 0.7},
            "야근한다":           {"performance": 0.8, "stress": 1.5},
            "프로젝트에 집중한다": {"performance": 1.0, "stress": 1.3},  # 0.9→1.0: 집중은 평균 수준 성과
        },
        initial_bonus={"energy": 10.0, "stress": -10.0, "political_skill": -3.0, "performance": 8.0},  # 시작 performance: 23, political_skill: 7
        event_tier_multipliers={"team": 1.4, "personal": 0.8},
        weekend_weights={"휴식": 6, "사교": 2, "여행": 3, "자기계발": 1, "인맥관리": 1},
    ),
}
