# 코드 리뷰 발표 대본 (10분)

---

## 1. 에이전트 구조 (3분)

이 프로젝트의 핵심은 ReAct 에이전트입니다.
ReAct는 "Reasoning + Acting"의 약자로, LLM이 먼저 생각하고(Thought) 그 다음 행동(Action)을 선택하는 패턴입니다.

### 배치 결정 구조

에이전트는 매일 하나씩 행동을 결정하는 게 아니라, **30일치 행동 계획을 한번에** LLM에게 요청합니다.

```python
# agents/react_agent.py — decide_batch()
def decide_batch(self, state, observation, n):
    memory_section = self._build_memory_section()
    system = self._batch_system_template.format(
        n=n, actions=self._actions_list(), memory_section=memory_section,
    )
    messages = [{"role": "user", "content": observation}]
    response = self.llm.call(system=system, messages=messages)
    actions = self._parse_batch(response, n)
    return actions
```

LLM에게 보내는 시스템 프롬프트에는 세 가지가 합쳐져 들어갑니다:
1. **성향 설명** — "당신은 정치형입니다. 상사 관계와 조직 내 영향력을 중시합니다"
2. **메모리** — 과거 주요 경험, 최근 행동 패턴 요약, 전략 지침
3. **현재 상태** — 스탯 8종(업무능력, 성과, 상사신뢰, 평판 등)과 가능한 행동 목록

LLM은 이걸 보고 "Day 1: 프로젝트에 집중한다 / Day 2: 상사와 점심을 먹는다 / ..." 형식으로 30일치 계획을 출력합니다.

이 30일 배치 주기가 나중에 Reflection과 관련해서 문제가 됩니다. 이건 Reflection 파트에서 다시 설명하겠습니다.

---

## 2. 메모리 시스템 (3분)

에이전트의 메모리는 3단계로 구성됩니다. 이 구조가 이 프로젝트에서 "딥 에이전트"를 구현하는 핵심입니다.

### 1단계: 에피소딕 메모리

모든 사건을 다 기억하는 게 아니라, **중요한 사건만 선별**해서 저장합니다.

```python
# agents/base_agent.py — _store_episode_if_important()
def _classify_outcome(self, observation):
    keywords = {
        "critical": ["해고", "승진", "이직"],
        "important": ["프로젝트 성공", "프로젝트 실패", "상사 교체"],
        "notable": ["상사 칭찬", "상사 질책", "헤드헌터"],
    }
```

승진, 해고 위기, 이직 같은 커리어에 큰 영향을 주는 사건만 에피소딕 메모리에 저장하고, 최대 50개까지 유지합니다. 오래된 건 자동으로 밀려납니다.

### 2단계: 히스토리 압축

최근 30일간의 행동 기록을 LLM에게 보내서 **3문장으로 요약**시킵니다.

```python
# memory/compressor.py
def compress_history(history, llm, window=30):
    recent = history[-window:]
    prompt = "아래 행동 기록을 3문장으로 요약하세요..."
    return llm.call(system=prompt, messages=[...])
```

"최근 30일간 프로젝트 집중 15일, 상사 점심 8일, 휴가 7일. 성과와 상사신뢰가 안정적으로 상승 중."
이런 식으로 압축된 요약이 다음 배치 결정의 컨텍스트로 들어갑니다.

### 3단계: Reflection (자기성찰)

90일마다 고급 모델(gpt-4.1)이 에이전트의 행동을 분석하고 전략을 처방합니다.

```python
# agents/react_agent.py — reflect()
def reflect(self, state, window=90, promotion_requirements=None):
    # 최근 90일 행동 기록 + 현재 스탯 + 승진 갭 분석을 종합해서
    # "평가 → 문제점 → 처방" 형식으로 전략 조언을 생성
    response = self.llm_reflect.call(system=prompt, messages=[...])
    self._reflection = response.strip()
```

이 세 단계가 합쳐져서 `_build_memory_section()`에서 하나의 텍스트로 조합되고, 배치 결정 프롬프트에 주입됩니다.

```python
# agents/react_agent.py — _build_memory_section()
def _build_memory_section(self):
    parts = []
    if self._reflection:           # 전략 지침 (최우선)
        parts.append(...)
    memory_text = self.memory.to_text(n=10)  # 에피소딕 메모리
    if memory_text != "기억 없음":
        parts.append(...)
    if len(self.history) >= 30:    # 히스토리 압축
        summary = compress_history(...)
        parts.append(...)
    return "\n\n".join(parts)
```

---

## 3. Reflection 개선 과정 (4분)

Reflection은 이 프로젝트에서 가장 많은 시행착오를 거친 부분입니다.

### 1단계: 단순 자기성찰 (실패)

처음에는 "지난 90일을 돌아보고 개선점을 말해줘" 정도의 프롬프트였습니다.
결과: Reflection ON/OFF 간 **차이가 전혀 없었습니다.** 배치 결정 모델(gpt-4.1-mini)이 조언을 그냥 무시했습니다.

### 2단계: 처방 형식 강화 (부분 성공)

프롬프트를 "전략 컨설턴트" 역할로 바꾸고, 승진 요건 대비 부족한 스탯을 수치로 보여주고, "30일 기준 행동 배분"을 구체적으로 처방하게 했습니다.

```
처방: 다음 90일 행동 배분 (30일 기준):
- 프로젝트에 집중한다 12일 (성과 부족)
- 상사와 점심을 먹는다 8일 (상사신뢰 유지)
- 휴가를 쓴다 5일 (스트레스 관리)
```

그리고 배치 프롬프트에서 이걸 "최우선 전략 지침"으로 강조했습니다.

결과: **Reflection이 "성과 올려라"고 처방하면 에이전트가 야근/프로젝트에 몰빵** → 스트레스 100, 체력 0 → **만성 스트레스로 오히려 더 빨리 퇴사.** NoReflect보다 결과가 나빠졌습니다.

### 3단계: 안전장치 + 배치 주기 단축 (현재)

두 가지를 수정했습니다.

**첫째, Reflection 프롬프트에 체력/스트레스 안전장치 추가:**
```
[!] 체력 30 이하 또는 스트레스 70 이상이면 반드시 휴가를 처방에 포함하세요.
[!] 야근은 스트레스 50 이상일 때 절대 처방하지 마세요.
[!] 장기 생존이 승진보다 중요합니다. 죽으면 승진도 없습니다.
```

**둘째, 배치 주기 단축 실험 (30일 → 7일):**

30일 배치의 문제는, 10일차에 스트레스가 급등해도 나머지 20일 계획이 이미 짜여있어서 대응이 안 된다는 것이었습니다. 7일로 줄이면 스트레스/체력 변화에 훨씬 빠르게 반응할 수 있습니다. 단, LLM 호출이 4배 늘어나서 비용이 증가합니다.

결과: **Reflect 에이전트가 드디어 스트레스/체력 관리에 성공**하고, 번아웃 없이 생존. 업무능력·성과도 NoReflect보다 높아졌습니다.

### 교훈

LLM 기반 에이전트를 만들 때 배운 점 세 가지:

1. **LLM의 조언은 "참고"일 뿐이다** — 아무리 프롬프트를 강조해도 모델이 100% 따르지 않는다. 구조적으로 따를 수밖에 없게 설계해야 한다.
2. **배치 주기가 에이전트의 반응성을 결정한다** — 비용 절약을 위해 긴 배치를 쓰면 환경 변화에 대응 못한다.
3. **자연스러운 균형을 깨뜨리면 오히려 역효과** — 성향대로 놔두는 게 균형을 유지하는데, 외부 조언이 이 균형을 무너뜨릴 수 있다.

---

*총 소요: 약 10분*
*필요한 화면: IDE(코드), architecture_code.png, A/B 비교 HTML*
