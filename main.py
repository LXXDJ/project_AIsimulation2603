"""
회사원 시뮬레이션 - 딥 에이전트 아키텍처 비교 실험
실행: python main.py
"""
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from dotenv import load_dotenv
from environment.company import CompanyEnvironment
from environment.personality import PERSONALITIES
from agents.react_agent import ReActAgent
from llm.client import LLMClient
from runner.simulation import run_simulation
from evaluation.metrics import compare_agents


# ── 실험 설정 ──────────────────────────────────────────
AUTO_VISUALIZE     = True # 시뮬레이션 종료 후 비교 차트 HTML 자동 생성 여부
EXPERIMENT_SEED    = 42   # 모든 에이전트가 동일한 이벤트 시퀀스를 경험 (랜덤 이벤트 순서를 고정하는 값) : 값 자체는 아무 숫자나 상관없고, 바꾸면 이벤트 순서가 달라짐
MAX_DAYS           = 3650 # 시뮬레이션 최대 기간 (일) — 10년
LOG_INTERVAL       = 30  # 콘솔 출력 주기 (일) — 분기마다
DECISION_INTERVAL  = 30   # 배치 결정 주기 (일) — 한달치 한 번에 결정

# ── 비교할 성향 목록 ────────────────────────────────────
# 사용 가능한 성향: "균형형", "성과형", "사교형", "정치형", "워라밸형"
ACTIVE_PERSONALITIES = ["균형형", "성과형", "사교형", "정치형", "워라밸형"]
# ────────────────────────────────────────────────────────


def _run_one(personality_name: str, tqdm_position: int = 0) -> dict:
    """단일 에이전트 시뮬레이션 실행 (스레드별 독립 실행)."""
    llm = LLMClient()
    agent = ReActAgent(llm=llm, personality=PERSONALITIES[personality_name])
    env = CompanyEnvironment(seed=EXPERIMENT_SEED, personality=agent.personality, max_days=MAX_DAYS)

    return run_simulation(
        agent=agent, env=env,
        max_days=MAX_DAYS, log_interval=LOG_INTERVAL,
        decision_interval=DECISION_INTERVAL, verbose=True,
        tqdm_position=tqdm_position,
    )


def main():
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY 환경변수를 설정하세요.")

    # tqdm 멀티스레드 커서 충돌 방지
    tqdm.set_lock(threading.RLock())

    # 성향별 병렬 실행 (각 에이전트에 tqdm 줄 번호 고정)
    results_map: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=len(ACTIVE_PERSONALITIES)) as executor:
        future_to_name = {
            executor.submit(_run_one, p, i): p
            for i, p in enumerate(ACTIVE_PERSONALITIES)
        }
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                results_map[name] = future.result()
            except Exception as e:
                print(f"[오류] {name} 실행 실패: {e}")

    # 원래 순서 복원
    results = [results_map[p] for p in ACTIVE_PERSONALITIES if p in results_map]

    # tqdm 멀티스레드 잔여 커서 정리
    print("\n" * len(ACTIVE_PERSONALITIES))
    print(f"{'='*60}")
    print("최종 비교 결과")
    print(f"{'='*60}")
    ranking = compare_agents(results)
    for m in ranking:
        print(
            f"[{m['rank']}위] {m['agent']} | 총점: {m['total_score']:.1f} | "
            f"{m['final_position']} | {m['final_salary']:,}원 | "
            f"생존: {m['survived_days']}일 | 해고: {m['fired']}"
        )

    # 비교 차트 HTML 생성 (브라우저 자동 열기 없음)
    if AUTO_VISUALIZE:
        from pathlib import Path
        from visualize_plotly import draw_comparison_html
        log_paths = [Path(r["log_path"]) for r in results if "log_path" in r]
        if log_paths:
            draw_comparison_html(log_paths, show=False)


if __name__ == "__main__":
    main()
