"""정치형 Reflect 5년 테스트 (gpt-4.1)"""
import os
from dotenv import load_dotenv
load_dotenv()

from environment.company import CompanyEnvironment
from environment.personality import PERSONALITIES
from agents.react_agent import ReActAgent
from llm.client import LLMClient
from runner.simulation import run_simulation

MAX_DAYS = 1825  # 5년
personality = PERSONALITIES["정치형"]

# Reflect: 둘 다 gpt-4.1
llm = LLMClient(model="gpt-4.1")
llm_reflect = LLMClient(model="gpt-4.1")
agent = ReActAgent(llm=llm, personality=personality, llm_reflect=llm_reflect)
agent.name = f"{agent.name}_Reflect"
env = CompanyEnvironment(seed=42, personality=agent.personality, max_days=MAX_DAYS)

result = run_simulation(
    agent=agent, env=env,
    max_days=MAX_DAYS, log_interval=30,
    decision_interval=30, verbose=True,
    tqdm_position=0,
)
print()
print("=== Reflect 결과 ===")
print(f"직급: {result['final_position']}, 연봉: {result['final_salary']:,}, 생존: {result['survived_days']}일")
print(f"해고: {result.get('is_fired')}, 퇴사: {result.get('is_resigned')}")
