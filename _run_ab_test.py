"""정치형 Reflect vs NoReflect A/B 테스트 (main.py 동일 조건: gpt-4.1-mini, 배치 30일)"""
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from dotenv import load_dotenv
load_dotenv()

from environment.company import CompanyEnvironment
from environment.personality import PERSONALITIES
from agents.react_agent import ReActAgent
from llm.client import LLMClient
from runner.simulation import run_simulation
from pathlib import Path
from visualize_plotly import draw_comparison_html

MAX_DAYS = 7300  # 20년
DECISION_INTERVAL = 30  # 배치 주기 30일 (main.py 동일)
personality = PERSONALITIES["정치형"]
tqdm.set_lock(threading.RLock())


def run_reflect(pos=0):
    llm = LLMClient(model="gpt-4.1-mini")
    llm_reflect = LLMClient(model="gpt-4.1")
    agent = ReActAgent(llm=llm, personality=personality, llm_reflect=llm_reflect)
    agent.name = f"{agent.name}_Reflect"
    env = CompanyEnvironment(seed=42, personality=agent.personality, max_days=MAX_DAYS)
    return run_simulation(agent=agent, env=env, max_days=MAX_DAYS, log_interval=30,
                          decision_interval=DECISION_INTERVAL, verbose=True, tqdm_position=pos)


def run_noreflect(pos=1):
    llm = LLMClient(model="gpt-4.1-mini")
    agent = ReActAgent(llm=llm, personality=personality, llm_reflect=None)
    agent.name = f"{agent.name}_NoReflect"
    env = CompanyEnvironment(seed=42, personality=agent.personality, max_days=MAX_DAYS)
    return run_simulation(agent=agent, env=env, max_days=MAX_DAYS, log_interval=30,
                          decision_interval=DECISION_INTERVAL, verbose=True, tqdm_position=pos)


with ThreadPoolExecutor(max_workers=2) as executor:
    f_reflect = executor.submit(run_reflect, 0)
    f_noreflect = executor.submit(run_noreflect, 1)
    results = {}
    for f in as_completed([f_reflect, f_noreflect]):
        try:
            r = f.result()
            results[r["agent"]] = r
        except Exception as e:
            print(f"[오류] {e}")

print("\n\n" + "=" * 60)
print("A/B 비교 결과")
print("=" * 60)
for name, r in results.items():
    print(f"{name}: {r['final_position']} | 연봉 {r['final_salary']:,} | 생존 {r['survived_days']}일 | 해고:{r.get('is_fired')} 퇴사:{r.get('is_resigned')}")

# HTML 생성
log_paths = [Path(r["log_path"]) for r in results.values() if "log_path" in r]
if log_paths:
    draw_comparison_html(log_paths, show=False)
