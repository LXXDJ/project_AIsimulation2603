from environment.state import POSITIONS

_BASE_SALARY   = 36_000_000   # 입사 초봉
_SALARY_RANGE  = 60_000_000   # 5년(1825일) 기준 최대 상승 폭 (임원 포함 상향)


def compute_metrics(result: dict) -> dict:
    """단일 시뮬레이션 결과에서 지표를 계산한다."""
    max_days = result.get("max_days", 1825)

    # 1) 생존율 (30점)
    survival_rate = result["survived_days"] / max_days

    # 2) 직급 점수 (20점)
    position_score = POSITIONS.index(result["final_position"]) / (len(POSITIONS) - 1)

    # 3) 연봉 상승 점수 (25점): 초봉 대비 얼마나 올렸는가, 시뮬 기간에 비례해 상한 조정
    salary_ceiling = _BASE_SALARY + _SALARY_RANGE * (max_days / 1825)
    salary_score = min(
        max(result["final_salary"] - _BASE_SALARY, 0) / (salary_ceiling - _BASE_SALARY),
        1.0,
    )

    # 4) 최종 스탯 퀄리티 (25점): 업무능력 + 성과 + 상사 호감도의 균형
    perf  = result.get("final_performance", 50) / 100
    skill = result.get("final_skill",       50) / 100
    favor = result.get("final_boss_favor",  50) / 100
    stress_penalty = result.get("final_stress", 30) / 100  # 스트레스 높을수록 감점
    state_score = (perf * 0.4 + skill * 0.3 + favor * 0.2 + (1 - stress_penalty) * 0.1)

    # 종합 점수 (0-100 스케일)
    score = (
        survival_rate * 30
        + position_score * 20
        + salary_score   * 25
        + state_score    * 25
    ) * 100

    return {
        "agent":          result["agent"],
        "survival_rate":  round(survival_rate,  3),
        "position_score": round(position_score, 3),
        "salary_score":   round(salary_score,   3),
        "state_score":    round(state_score,    3),
        "total_score":    round(score,           2),
        "survived_days":  result["survived_days"],
        "final_position": result["final_position"],
        "final_salary":   result["final_salary"],
        "fired":          result["is_fired"],
    }


def compare_agents(results: list[dict]) -> list[dict]:
    """여러 에이전트 결과를 지표화하고 순위를 매긴다."""
    metrics = [compute_metrics(r) for r in results]
    metrics.sort(key=lambda x: x["total_score"], reverse=True)
    for rank, m in enumerate(metrics, 1):
        m["rank"] = rank
    return metrics
