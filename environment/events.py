import random
from dataclasses import dataclass, field


@dataclass
class Event:
    name: str
    description: str
    effects: dict           # {"performance": +10, "stress": +20, ...} — 현재값에 더함
    probability: float      # 티어 내 상대 가중치 (클수록 선택 확률 높음)
    resets: dict = field(default_factory=dict)  # {"boss_favor": 25} — 해당 값으로 직접 설정


# ── 회사 차원 이벤트 ───────────────────────────────────────────────────────
# 연간 기대 0~1건, 가끔 2건. 하루 발생 확률: 0.2%
# (구조적 변화 — 개인 행동과 무관하게 회사가 결정)
COMPANY_EVENTS: list[Event] = [
    Event(
        name="구조조정 공지",
        description="회사에서 구조조정을 예고했다. 분위기가 어수선하다.",
        effects={"stress": 20, "peer_relation": -6, "political_skill": 3},  # 위기 속에서 정치 감각 자극
        probability=0.6,
    ),
    Event(
        name="상사 교체",
        description="직속 상사가 갑자기 교체됐다. 새 상사와의 관계를 다시 쌓아야 한다.",
        effects={"boss_favor": -10, "stress": 12, "political_skill": -4},
        probability=0.8,
    ),
    Event(
        name="우수사원 선정",
        description="이달의 우수사원으로 선정됐다. 사내 인지도가 크게 올랐다.",
        effects={"reputation": 15, "boss_favor": 10, "performance": 5, "stress": -5, "political_skill": 3},  # 공식 인정 → 정치 입지 강화
        probability=0.4,
    ),
    Event(
        name="연봉 협상 성공",
        description="연봉 협상에서 원하는 결과를 얻어냈다. 의욕이 생겼다.",
        effects={"salary": 2_000_000, "stress": -10, "reputation": 5, "political_skill": 2},  # 협상 성공 = 정치력 발현
        probability=0.4,
    ),
    Event(
        name="부서 이동",
        description="갑작스럽게 부서 이동 명령이 내려졌다. 새 상사와 팀에 처음부터 다시 시작해야 한다.",
        effects={"stress": 15, "performance": -5, "political_skill": -5},  # 기존 네트워크 전면 무효화
        resets={"boss_favor": 25, "peer_relation": 20},
        probability=0.3,
    ),
    Event(
        name="회사 적자 발표",
        description="회사가 적자를 발표했다. 분위기가 급격히 냉각됐다.",
        effects={"stress": 15, "peer_relation": -5, "boss_favor": -5, "energy": -5},  # stress 20→15, peer_relation -8→-5
        probability=0.5,
    ),
]

# ── 팀/프로젝트 차원 이벤트 ───────────────────────────────────────────────
# 연간 기대 4~5건 (분기당 1건). 하루 발생 확률: 1.2%
# (팀 단위, 프로젝트 단위에서 발생 — 개인보다 빈도 낮음)
TEAM_EVENTS: list[Event] = [
    Event(
        name="프로젝트 성공",
        description="담당 프로젝트가 좋은 평가를 받았다.",
        effects={"performance": 15, "reputation": 10, "boss_favor": 8, "political_skill": 1},  # 성공 경험 → 조직 입지 소폭 강화
        probability=0.8,
    ),
    Event(
        name="프로젝트 실패",
        description="담당 프로젝트가 실패했다. 책임 소재가 논의되고 있다.",
        effects={"performance": -6, "reputation": -4, "stress": 20, "boss_favor": -6, "political_skill": -1},
        probability=0.6,
    ),
    Event(
        name="팀원 퇴사",
        description="가까운 팀원이 갑자기 퇴사했다. 업무 부담이 늘었다.",
        effects={"stress": 12, "peer_relation": -4, "performance": -3},  # stress 15→12, peer_relation -5→-4, performance -5→-3
        probability=0.7,
    ),
    Event(
        name="헤드헌터 연락",
        description="헤드헌터로부터 이직 제안이 왔다.",
        effects={"reputation": 5, "political_skill": 2},  # 외부 가치 인정 → 정치적 자신감
        probability=0.5,
    ),
    Event(
        name="갑질 피해",
        description="상사 또는 클라이언트의 갑질로 심한 스트레스를 받았다.",
        effects={"stress": 20, "energy": -10, "boss_favor": -5, "peer_relation": -4, "political_skill": -3},  # 위계 폭력 → 정치적 무력감
        probability=0.6,
    ),
    Event(
        name="업무 과부하",
        description="무리한 야근 지시와 업무 몰림으로 한계에 다다랐다.",
        effects={"stress": 18, "energy": -15, "performance": -3, "boss_favor": 3},  # stress 20→18, energy -20→-15, performance -5→-3
        probability=0.8,
    ),
]

# ── 개인 차원 이벤트 ──────────────────────────────────────────────────────
# 연간 기대 14~15건 (월 1~2건). 하루 발생 확률: 4%
# (일상적 대인관계 — 가장 자주 발생)
PERSONAL_EVENTS: list[Event] = [
    Event(
        name="상사 칭찬",
        description="상사가 최근 업무를 칭찬했다.",
        effects={"boss_favor": 10, "reputation": 5, "stress": -5},
        probability=0.8,
    ),
    Event(
        name="상사 질책",
        description="상사가 실수를 크게 질책했다.",
        effects={"boss_favor": -8, "stress": 18, "energy": -8},
        probability=0.8,
    ),
    Event(
        name="소문 발생",
        description="나에 대한 좋지 않은 소문이 돌고 있다.",
        effects={"reputation": -5, "peer_relation": -4, "stress": 8},
        probability=0.5,
    ),
    Event(
        name="회식",
        description="팀 회식이 있었다. 동료들과 관계가 가까워졌다.",
        effects={"peer_relation": 10, "boss_favor": 5, "energy": -10},
        probability=0.9,
    ),
    Event(
        name="업무 실수",
        description="중요한 업무에서 실수를 저질렀다. 수습이 필요하다.",
        effects={"performance": -4, "boss_favor": -4, "reputation": -3, "stress": 12},
        probability=0.4,
    ),
    Event(
        name="동료 갈등",
        description="동료와 심각한 갈등이 생겼다. 팀 분위기가 어색해졌다.",
        effects={"peer_relation": -8, "stress": 10, "reputation": -3, "performance": -1},
        probability=0.6,
    ),
]

# 하위 호환을 위한 전체 풀 (이벤트 로그 등에서 참조)
EVENT_POOL: list[Event] = COMPANY_EVENTS + TEAM_EVENTS + PERSONAL_EVENTS

# 티어별 하루 발생 확률
_COMPANY_CHANCE = 0.002   # 연간 기대 ~0.7건 (0-1, 가끔 2)
_TEAM_CHANCE    = 0.012   # 연간 기대 ~4.4건 (분기당 ~1건)
_PERSONAL_CHANCE = 0.04   # 연간 기대 ~14.6건 (월 ~1.2건)


def _state_weights(state) -> dict[str, float]:
    """현재 상태값 기반으로 이벤트별 선택 가중치 배수를 반환 (기본값 1.0)."""
    if state is None:
        return {}
    w = {}

    # ── 개인 이벤트 ─────────────────────────────────────────────
    # 상사 칭찬: 호감도 높을수록 자주 / 성과 낮으면 칭찬도 드묾
    if state.boss_favor >= 70:   w["상사 칭찬"] = 1.8
    elif state.boss_favor >= 50: w["상사 칭찬"] = 1.2
    if state.performance < 40:   w["상사 칭찬"] = w.get("상사 칭찬", 1.0) * 0.4

    # 상사 질책: 호감도 낮을수록 조금 더 자주 (악순환 완화)
    if state.boss_favor <= 25:   w["상사 질책"] = 1.5
    elif state.boss_favor <= 40: w["상사 질책"] = 1.2

    # 업무 실수: 스트레스 높거나 체력 낮을수록 자주 / 컨디션 좋을 땐 드묾
    if state.stress >= 75 or state.energy <= 20:   w["업무 실수"] = 2.0
    elif state.stress >= 55 or state.energy <= 35: w["업무 실수"] = 1.4
    elif state.stress < 40 and state.energy > 50:  w["업무 실수"] = 0.5

    # 동료 갈등: 동료 관계 낮을수록 자주
    if state.peer_relation <= 25:   w["동료 갈등"] = 1.8
    elif state.peer_relation <= 40: w["동료 갈등"] = 1.3

    # 소문: 평판 낮을수록 자주
    if state.reputation <= 20: w["소문 발생"] = 1.6

    # 회식: 동료 관계 높을수록 자주
    if state.peer_relation >= 60: w["회식"] = 1.3

    # ── 팀 이벤트 ───────────────────────────────────────────────
    # 프로젝트 성공: 성과 높을수록 자주
    if state.performance >= 70:   w["프로젝트 성공"] = 1.8
    elif state.performance >= 50: w["프로젝트 성공"] = 1.2

    # 프로젝트 실패: 성과 낮을수록 조금 더 자주 (악순환 완화)
    if state.performance <= 30:   w["프로젝트 실패"] = 1.4
    elif state.performance <= 45: w["프로젝트 실패"] = 1.2

    # 헤드헌터: 평판 높을수록 자주
    if state.reputation >= 65:   w["헤드헌터 연락"] = 1.8
    elif state.reputation >= 45: w["헤드헌터 연락"] = 1.3

    # 갑질: 호감도 낮을수록 자주
    if state.boss_favor <= 25: w["갑질 피해"] = 1.6

    # 업무 과부하: 스트레스 높고 체력 낮을 때 자주
    if state.stress >= 70 and state.energy <= 30: w["업무 과부하"] = 1.6

    # ── 회사 이벤트 ─────────────────────────────────────────────
    # 우수사원: 성과·평판 모두 높을 때
    if state.performance >= 75 and state.reputation >= 60: w["우수사원 선정"] = 1.8

    # 연봉 협상 성공: 성과·호감도 높을 때
    if state.performance >= 70 and state.boss_favor >= 65: w["연봉 협상 성공"] = 1.5

    return w


def roll_events(rng: random.Random | None = None, personality=None, state=None) -> list[Event]:
    """
    티어별로 독립적으로 발생 여부를 결정하고, 발생 시 가중치로 1개 선택.
    성향 배수 + 상태값 기반 가중치를 함께 반영한다.
    하루 최대 3건 (티어당 1건)이지만 실제론 거의 0~1건.
    """
    r = rng or random
    sw = _state_weights(state)
    result = []
    for tier_name, tier_pool, base_chance in (
        ("company",  COMPANY_EVENTS,  _COMPANY_CHANCE),
        ("team",     TEAM_EVENTS,     _TEAM_CHANCE),
        ("personal", PERSONAL_EVENTS, _PERSONAL_CHANCE),
    ):
        multiplier = personality.get_event_multiplier(tier_name) if personality else 1.0
        if r.random() < base_chance * multiplier:
            weights = [
                e.probability
                * sw.get(e.name, 1.0)                                    # 상태 기반
                * (personality.get_event_weight(e.name) if personality else 1.0)  # 성향 기반
                for e in tier_pool
            ]
            result.append(r.choices(tier_pool, weights=weights, k=1)[0])
    return result
