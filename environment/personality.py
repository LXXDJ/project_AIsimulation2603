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
    # 개별 이벤트 발생 확률 배수 {이벤트명: 배수} — 미정의=1.0
    event_weights: dict[str, float] = field(default_factory=dict)

    def get_multiplier(self, action: str, stat: str) -> float:
        return self.action_multipliers.get(action, {}).get(stat, 1.0)

    def get_event_multiplier(self, tier: str) -> float:
        return self.event_tier_multipliers.get(tier, 1.0)

    def get_event_weight(self, event_name: str) -> float:
        return self.event_weights.get(event_name, 1.0)


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
        initial_bonus={"skill": 15.0, "performance": 10.0, "political_skill": -8.0},
        event_tier_multipliers={"team": 1.5, "personal": 0.7},
        weekend_weights={"자기계발": 5, "휴식": 3, "사교": 1, "인맥관리": 1, "여행": 1},
        event_weights={
            "우수사원 선정": 1.3,     # 성과 좋으니 선정 확률↑
            "연봉 협상 성공": 1.3,    # 실적이 뒷받침하는 협상력
            "프로젝트 성공": 1.5,     # 업무 집중 → 성공 확률↑
            "헤드헌터 연락": 1.5,     # 실력자라 스카우트 잦음
            "업무 과부하": 1.4,       # 일을 많이 하니까
            "동료 갈등": 1.3,         # 사교 서툴러서 마찰
            "상사 질책": 0.8,         # 실력 좋아서 질책할 거리 적음
            "회식": 0.7,             # 회식보다 야근 선호
            "업무 실수": 0.5,         # 실력 좋아서 실수 적음
        },
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
        initial_bonus={"peer_relation": 10.0, "boss_favor": 5.0, "skill": -5.0, "performance": -3.0, "political_skill": 8.0},
        event_tier_multipliers={"personal": 1.5, "company": 0.8},
        weekend_weights={"사교": 5, "휴식": 3, "인맥관리": 2, "자기계발": 1, "여행": 2},
        event_weights={
            "회식": 1.5,             # 사교적이라 회식 자주
            "상사 칭찬": 1.3,        # 관계 좋아서 칭찬 많이 받음
            "업무 실수": 1.3,        # 업무 집중 덜 해서 실수 많음
            "헤드헌터 연락": 1.2,    # 넓은 인맥 네트워크
            "프로젝트 실패": 1.2,    # 실력보다 관계에 투자
            "업무 과부하": 0.8,      # 업무보다 관계 우선, 무리하게 안 맡음
            "팀원 퇴사": 0.8,        # 팀 분위기 좋게 만들어 이탈 방지
            "갑질 피해": 0.7,        # 관계 좋아서 갑질 타겟 안 됨
            "소문 발생": 0.6,        # 인망 있어서 악소문 적음
            "동료 갈등": 0.4,        # 대인관계 좋아서 갈등 적음
        },
    ),
    "정치형": Personality(
        name="정치형",
        description=(
            "조직 정치 중심형. 상사 관리와 정치적 행동의 효과가 극대화된다. "
            "순수 업무 효율은 낮지만 승진 조건을 빠르게 충족시키는 데 유리하다."
        ),
        action_multipliers={
            "정치적으로 행동한다": {"political_skill": 1.6, "boss_favor": 1.5, "reputation": 0.0},
            "상사와 점심을 먹는다": {"boss_favor": 1.4, "political_skill": 1.3},
            "동료를 도와준다":     {"reputation": 1.4, "peer_relation": 1.2},
            "프로젝트에 집중한다": {"skill": 0.85, "performance": 0.9},
            "야근한다":           {"skill": 0.8, "performance": 0.85},
            "자기계발을 한다":     {"skill": 0.85},
        },
        initial_bonus={"political_skill": 25.0, "skill": -2.0},
        event_tier_multipliers={"company": 1.5, "personal": 1.2},
        weekend_weights={"인맥관리": 5, "사교": 3, "휴식": 2, "자기계발": 1, "여행": 1},
        event_weights={
            "소문 발생": 1.6,        # 정치적 행동은 소문 대상이 되기 쉬움
            "동료 갈등": 1.5,        # 정치적이라 동료 반감
            "연봉 협상 성공": 1.4,   # 정치적 수완으로 협상력↑
            "상사 칭찬": 1.3,        # 상사 관리 잘해서
            "프로젝트 실패": 1.3,    # 업무보다 정치에 시간 투자
            "상사 교체": 1.3,        # 정치적 변동에 민감
            "팀원 퇴사": 1.3,        # 정치적 분위기 → 동료 이탈
            "부서 이동": 1.2,        # 정치적 움직임에 노출
            "업무 실수": 1.2,        # 업무 소홀
            "헤드헌터 연락": 0.8,    # 실력보다 정치 → 외부 시장 평가 낮음
            "회식": 0.8,             # 전략적 만남 선호, 일반 회식 관심 적음
        },
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
            "프로젝트에 집중한다": {"performance": 1.0, "stress": 1.3},
        },
        initial_bonus={"energy": 10.0, "stress": -10.0, "political_skill": -3.0, "performance": 8.0},
        event_tier_multipliers={"team": 1.4, "personal": 0.8},
        weekend_weights={"휴식": 6, "사교": 2, "여행": 3, "자기계발": 1, "인맥관리": 1},
        event_weights={
            "우수사원 선정": 0.7,    # 눈에 안 띄는 스타일
            "연봉 협상 성공": 0.7,   # 적극적으로 협상하지 않음
            "헤드헌터 연락": 0.7,    # 적극적이지 않아서 눈에 안 띔
            "갑질 피해": 0.7,        # 스트레스 적고 조용해서 타겟 안 됨
            "회식": 0.7,             # 워라밸 선호, 회식보다 퇴근
            "업무 실수": 0.7,        # 컨디션 관리 잘 해서 실수 적음
            "소문 발생": 0.8,        # 존재감 낮아서 소문 대상 안 됨
            "상사 질책": 0.8,        # 무난하게 하니까 질책 적음
            "동료 갈등": 0.8,        # 갈등 자체를 피하는 성향
            "업무 과부하": 0.5,      # 무리하지 않아서
        },
    ),
}
