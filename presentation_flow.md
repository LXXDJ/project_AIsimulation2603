# 코드 실행 흐름 대본 (main.py부터 따라가기)

---

## 1. 진입점: main.py

```python
# main.py
EXPERIMENT_SEED    = 42      # 랜덤 시드 — 모든 에이전트가 동일한 이벤트를 경험
MAX_DAYS           = 7300    # 20년
DECISION_INTERVAL  = 30      # 30일치 행동을 한 번에 결정

USE_REFLECTION     = False
MODEL_DECISION     = "gpt-4.1-mini"    # 배치 결정용 (저렴)
MODEL_REFLECTION   = "gpt-4.1"         # Reflection용 (고품질)

ACTIVE_PERSONALITIES = ["균형형", "성과형", "사교형", "정치형", "워라밸형"]
```

실행하면 먼저 실험 설정을 읽습니다. 핵심은 **EXPERIMENT_SEED**입니다.
같은 시드를 쓰면 5개 성향의 에이전트가 모두 동일한 랜덤 이벤트 시퀀스를 경험하게 됩니다.
성향만 다르고 환경은 같으니, 순수하게 "어떤 성향이 회사에서 유리한가"를 비교할 수 있습니다.

---

## 2. 에이전트 & 환경 생성: _run_one()

```python
def _run_one(personality_name, ...):
    llm = LLMClient(model=MODEL_DECISION)             # GPT-4.1-mini
    llm_reflect = LLMClient(model=MODEL_REFLECTION)    # GPT-4.1 (Reflection용)
    agent = ReActAgent(llm=llm, personality=PERSONALITIES[personality_name],
                       llm_reflect=llm_reflect)
    env = CompanyEnvironment(seed=EXPERIMENT_SEED, personality=agent.personality)
    return run_simulation(agent=agent, env=env, ...)
```

각 성향마다 `_run_one()`이 호출됩니다. 여기서 세 가지 객체가 만들어집니다:
- **LLMClient**: OpenAI API를 호출하는 래퍼. 배치 결정용과 Reflection용 두 개.
- **ReActAgent**: 성향이 주입된 에이전트. 프롬프트에 "당신은 정치형입니다" 같은 설명이 들어갑니다.
- **CompanyEnvironment**: 회사 환경. 승진 요건, 해고 조건, 이벤트 확률 등이 여기에 있습니다.

5개 성향이 **ThreadPoolExecutor**로 병렬 실행됩니다.


ThreadPoolExecutor 컨텍스트 매니저

with ThreadPoolExecutor(max_workers=len(jobs)) as executor:
ThreadPoolExecutor(max_workers=len(jobs))
스레드 풀을 생성합니다. max_workers는 동시에 실행할 스레드 수입니다.

len(jobs)가 5면 → 스레드 5개를 미리 만들어두고, 작업 5개를 동시에 실행합니다. 이걸 3으로 바꾸면 5개 중 3개만 먼저 돌고, 하나가 끝나면 다음 걸 시작합니다.

with ... as executor:
with 문(컨텍스트 매니저)을 쓰는 이유는 자동 정리 때문입니다:


# with를 쓰면 이렇게 동작합니다:
executor = ThreadPoolExecutor(max_workers=5)
try:
    # ... submit, as_completed 등 작업 수행 ...
finally:
    executor.shutdown(wait=True)  # 모든 스레드가 끝날 때까지 대기 후 정리
with 블록을 빠져나오는 순간 shutdown(wait=True)가 자동 호출되어:

아직 실행 중인 스레드가 있으면 전부 끝날 때까지 대기
스레드 풀 자원 해제
전체 흐름 요약

with ThreadPoolExecutor(max_workers=5) as executor:  # 스레드 5개 준비
    # submit()으로 작업 5개 제출 → 5개 동시 실행 시작
    # as_completed()로 끝나는 순서대로 결과 수거
# ← 여기서 자동으로 모든 스레드 종료 대기 + 정리
with를 안 쓰고 executor.shutdown()을 직접 안 불러주면, 스레드가 프로그램 종료 후에도 남아서 좀비처럼 돌 수 있습니다.

---

## 3. 시뮬레이션 루프: run_simulation()

```python
# runner/simulation.py
for day in range(1, max_days + 1):     # Day 1 ~ 7300
    is_weekend = (day - 1) % 7 >= 5    # 토/일 판별
```

7300일(20년)을 하루씩 돌립니다. 여기가 전체 시뮬레이션의 심장입니다.

### 주말이면?

```python
if is_weekend:
    state, observation, action = env.step_weekend()
```

주말에는 LLM을 호출하지 않습니다. 성향별 가중치로 활동을 랜덤 선택합니다.
휴식, 자기계발, 사교, 인맥관리, 여행 중 하나. 예를 들어 워라밸형은 여행과 휴식 가중치가 높습니다.

### 평일이면? — 배치 결정

```python
if not pending_actions:                              # 30일 계획이 소진됐으면
    # 1) Reflection 체크 (90일마다)
    if agent.llm_reflect and day - last_reflection_day >= 90:
        agent.reflect(state, window=90, ...)          # GPT-4.1로 자기성찰

    # 2) 30일치 행동 계획 생성
    observation = state.to_observation()              # 현재 스탯을 텍스트로
    pending_actions = agent.decide_batch(state, observation, 30)  # GPT-4.1-mini 호출

action = pending_actions.pop(0)                       # 오늘 행동 꺼내기
state, observation = env.step(action)                 # 환경 1일 전진
```

이 구조가 핵심입니다:
1. 30일치 계획이 소진되면, 먼저 **Reflection**(자기성찰)을 할지 체크합니다.
2. 그 다음 에이전트의 메모리(에피소딕 + 히스토리 압축 + Reflection 결과)를 조합해서 **시스템 프롬프트**를 만들고, LLM에게 30일치 행동을 요청합니다.
3. 매일 하나씩 꺼내서 환경에 적용합니다.

---

## 4. 환경 처리: env.step(action)

```python
# environment/company.py — step()
def step(self, action):
    # 1) 행동 효과 적용
    effects = ACTION_EFFECTS[action]
    self._apply_effects(effects, action)       # 스탯 변화 (성향 배율 적용)

    # 2) 자연 회복/저하
    self._apply_daily_drift()                   # 체력+5, 스트레스-2, ...

    # 3) 랜덤 이벤트 발생
    events = roll_events(self.rng, ...)         # 확률 판정
    for event in events:
        self._apply_effects(event.effects)      # 이벤트 효과 적용

    # 4) 수치 범위 클램프 (0~100)
    state.clamp_all()

    # 5) 번아웃 / 만성스트레스 / 희망퇴직 판정
    # 6) 해고 판정
    # 7) 이직 판정 (새 회사에서 계속)
    # 8) 승진 판정 (연 2회 인사시즌)
```

하루 동안 일어나는 일이 순서대로 처리됩니다.
행동 효과 → 자연 변화 → 랜덤 이벤트 → 생존 판정 → 커리어 변동.

이벤트는 3티어로 나뉩니다:
- **회사 이벤트** (0.2%/일): 구조조정, 상사 교체, 우수사원 선정
- **팀 이벤트** (1.2%/일): 프로젝트 성공/실패, 헤드헌터 연락
- **개인 이벤트** (4%/일): 상사 칭찬/질책, 회식, 업무 실수

---

## 5. 기록 & 메모리 저장

```python
# runner/simulation.py
agent.record(day, action, observation)           # 히스토리에 추가
_store_episode_if_important(agent, day, ...)     # 중요 사건만 에피소딕 메모리에 저장
```

매일 행동과 결과가 기록되고, 승진/해고위기/이직 같은 중요한 사건은 에피소딕 메모리에 별도 저장됩니다.
이 메모리가 다음 번 배치 결정 때 프롬프트에 포함되어 에이전트의 판단에 영향을 줍니다.

---

## 6. 종료 판정

에이전트가 살아남는 방법과 죽는 방법:

**생존 종료:**
- 부장/이사로 20년 완주 → **정년퇴직**
- 임원으로 20년 완주 → **현직유지**

**비자발적 종료:**
- 성과 < 10 AND 상사신뢰 < 10 → **성과 부진 해고**
- 5년차 대리 미만 / 8년차 과장 미만 / 15년차 차장 미만 / 18년차 부장 미만 → **승진 미달 권고사직**

**자발적 종료:**
- 스트레스 90+ AND 체력 10 이하 30일 지속 → **번아웃 퇴사**
- 스트레스 70+ 누적 180일 → **만성 스트레스 퇴사**
- 경력 12년+ 차장 이상 → **희망퇴직** (직급/스탯/성향에 따라 확률 변동)

---

## 7. 결과 비교 & 시각화

```python
# main.py
ranking = compare_agents(results)        # 총점 기준 순위 매기기
draw_comparison_html(log_paths)          # Plotly 인터랙티브 차트 생성
```

모든 에이전트가 끝나면 총점(직급 점수 + 연봉 점수 + 생존일 점수)으로 순위를 매기고,
스탯 변화 그래프를 HTML로 생성합니다. 각 성향이 20년 동안 어떻게 다른 궤적을 그리는지 비교할 수 있습니다.

---

## 정리: 전체 흐름 한눈에

```
main.py                  _run_one()              run_simulation()           env.step()
───────                  ──────────              ────────────────           ──────────
설정 로드           →    에이전트 생성       →    Day 1~7300 루프      →    행동 효과 적용
5개 성향 병렬 실행  →    환경 생성           →    주말: 자동 활동            자연 변화
                        LLM 클라이언트       →    평일: 30일 배치 결정       랜덤 이벤트
                                                  90일마다 Reflection       생존/해고/승진 판정
                                             →    메모리 저장
결과 비교 & HTML                             ←    결과 반환
```

*이 구조도는 architecture_code.png와 대응됩니다.*
