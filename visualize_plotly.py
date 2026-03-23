"""
Plotly 기반 인터랙티브 HTML 시각화
사용법: python visualize_plotly.py logs/ReAct_성과형_240101_120000.jsonl
        python visualize_plotly.py          (← logs/ 폴더의 가장 최신 파일 자동 선택)
"""
import json
import sys
from datetime import datetime as _dt
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── 상수 ──────────────────────────────────────────────────────────────────────
_POSITIVE_EVENTS = {"우수사원 선정", "연봉 협상 성공", "프로젝트 성공", "헤드헌터 연락", "상사 칭찬", "회식"}

STAT_LINES = [
    ("performance",     "성과",        "#1565C0", True),
    ("boss_favor",      "상사 호감도", "#F57F17", True),
    ("skill",           "업무능력",    "#5c4033", True),
    ("peer_relation",   "동료 관계",   "#2E7D32", False),
    ("reputation",      "평판",        "#6A1B9A", False),
    ("stress",          "스트레스",    "#E53935", True),
    ("energy",          "체력",        "#00ACC1", True),
]

AGENT_PALETTE = [
    "#1565C0", "#E53935", "#2E7D32", "#F57F17",
    "#6A1B9A", "#00838F", "#AD1457", "#4E342E",
]

ACTION_COLORS = {
    # 평일 행동
    "야근한다":            "#E53935",  # 빨강
    "프로젝트에 집중한다":  "#FF7043",  # 주황-빨강
    "상사와 점심을 먹는다": "#FDD835",  # 노랑
    "자기계발을 한다":      "#00897B",  # 청록
    "동료를 도와준다":      "#43A047",  # 초록
    "정치적으로 행동한다":  "#8E24AA",  # 보라
    "이직 준비를 한다":     "#546E7A",  # 회색-파랑
    "휴가를 쓴다":          "#29B6F6",  # 하늘
    # 주말 활동
    "휴식":                "#BDBDBD",  # 연회색
    "자기계발":             "#26A69A",  # 민트
    "사교":                "#66BB6A",  # 연초록
    "인맥관리":             "#AB47BC",  # 연보라
    "여행":                "#FFCA28",  # 금색
}

# 주말 행동 식별자 (평일 행동과 구분)
_WEEKEND_ACTIONS = {"휴식", "자기계발", "사교", "인맥관리", "여행"}


def _display_name(name: str) -> str:
    """에이전트 이름에서 타임스탬프·접두사(ReAct_ 등) 제거 → 성향명만 반환."""
    import re
    # 타임스탬프 패턴 제거 (예: 260320_162456_)
    name = re.sub(r"^\d{6}_\d{6}_", "", name)
    for prefix in ("ReAct_", "Batch_", "Chain_", "React_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return name


def _day_to_label(day: int) -> str:
    """일수를 '1년', '6개월' 등 사람이 읽기 쉬운 레이블로 변환."""
    total_months = round(day / 30)
    years  = total_months // 12
    months = total_months % 12
    if years == 0:
        return f"{total_months}개월"
    if months == 0:
        return f"{years}년"
    return f"{years}년 {months}개월"


def _make_time_ticks(max_day: int) -> tuple[list[int], list[str]]:
    """x축 tick 위치와 레이블 생성 (분기/반기/연 단위)."""
    tickvals, ticktext = [], []
    # 연 단위
    for y in range(1, max_day // 365 + 2):
        d = y * 365
        if d <= max_day + 60:
            tickvals.append(d)
            ticktext.append(f"{y}년")
    # 반기 단위 (연 경계와 겹치지 않는 것만)
    for h in range(1, max_day // 182 + 2):
        d = h * 182
        if d <= max_day + 60 and not any(abs(d - v) < 60 for v in tickvals):
            tickvals.append(d)
            ticktext.append(_day_to_label(d))
    # 분기 단위 (필요 시 — max_day 짧을 때)
    if max_day <= 400:
        for q in range(1, max_day // 90 + 2):
            d = q * 90
            if d <= max_day + 30 and not any(abs(d - v) < 45 for v in tickvals):
                tickvals.append(d)
                ticktext.append(_day_to_label(d))
    # 정렬
    pairs = sorted(zip(tickvals, ticktext))
    return [p[0] for p in pairs], [p[1] for p in pairs]


# ── 로그 로딩 ─────────────────────────────────────────────────────────────────

def load_log(path: Path) -> tuple[dict, list[dict]]:
    result, steps = {}, []
    extra: dict[str, list] = {"_reflections": [], "_promotions_log": []}
    exit_log = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            t = obj.get("type")
            if t == "result":
                result = {k: v for k, v in obj.items() if k != "type"}
            elif t == "step":
                steps.append({k: v for k, v in obj.items() if k != "type"})
            elif t == "exit":
                exit_log = obj
            elif t == "promotion":
                extra["_promotions_log"].append(obj)
            elif t == "reflection":
                extra["_reflections"].append(obj)
    # result 덮어쓰기 이후에 부가 데이터 병합
    if exit_log:
        result["_exit_log"] = exit_log
    if extra["_promotions_log"]:
        result["_promotions_log"] = extra["_promotions_log"]
    if extra["_reflections"]:
        result["_reflections"] = extra["_reflections"]
    # result 레코드가 없거나 불완전한 경우 steps에서 보완
    if steps:
        last = steps[-1]
        if not result.get("final_position"):
            result["final_position"] = last.get("position", "?")
        if not result.get("final_salary"):
            result["final_salary"] = last.get("salary", 0)
        if result.get("survived_days") is None:
            result["survived_days"] = last.get("day", len(steps))
        if not result.get("agent"):
            # meta 행에서 가져올 수도 있지만, 파일명에서 추출
            result["agent"] = path.stem
        # is_fired/is_resigned/is_retired 미설정 시 exit_log에서 추론
        if result.get("is_fired") is None and result.get("is_resigned") is None:
            if exit_log:
                reason = (exit_log.get("analysis") or {}).get("reason", "")
                if reason in ("성과_부진", "승진_미달", "번아웃", "만성_스트레스"):
                    result["is_fired"] = True
                    result["is_resigned"] = False
                    result["is_retired"] = False
                    if not result.get("exit_analysis"):
                        result["exit_analysis"] = exit_log.get("analysis", {})
                elif reason == "희망퇴직":
                    result["is_fired"] = False
                    result["is_resigned"] = True
                    result["is_retired"] = False
                    if not result.get("exit_analysis"):
                        result["exit_analysis"] = exit_log.get("analysis", {})
    return result, steps


_STAT_LABELS = {
    "skill": "업무능력", "performance": "성과",
    "boss_favor": "상사신뢰", "reputation": "평판",
}


def _extract_reflection_label(text: str) -> str:
    """성찰 텍스트의 '문제점:' 줄에서 핵심 키워드를 추출한다."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("문제점:") or stripped.startswith("문제점 :"):
            content = stripped.split(":", 1)[1].strip()
            # 괄호 안 수치 제거하고 핵심만 추출
            # 너무 길면 15자로 자름
            if len(content) > 18:
                content = content[:18] + "…"
            return content
    # 문제점이 없으면 개선 줄 시도
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("개선:") or stripped.startswith("개선 :"):
            content = stripped.split(":", 1)[1].strip()
            if len(content) > 18:
                content = content[:18] + "…"
            return content
    return ""


def _exit_reason_text(result: dict) -> str:
    """result 딕셔너리에서 해고/퇴사 원인 텍스트를 생성한다."""
    # exit_analysis (result에 직접 포함) 또는 _exit_log (JSONL exit 레코드) 참조
    analysis = result.get("exit_analysis") or {}
    if not analysis:
        log = result.get("_exit_log", {})
        analysis = log.get("analysis", {})
    if not analysis:
        return ""

    reason = analysis.get("reason", "")
    if reason == "성과_부진":
        lines = ["원인: 성과 + 상사신뢰 동시 저조"]
        for k, v in analysis.get("stats", {}).items():
            label = _STAT_LABELS.get(k, k)
            lines.append(f"  {label}: {v['value']} (기준: {v['threshold']} 미만)")
        return "<br>".join(lines)
    elif reason == "승진_미달":
        target = analysis.get("target_position", "?")
        lines = [f"원인: 경력 대비 직급 미달 (요구: {target})"]
        for k, v in analysis.get("stats", {}).items():
            label = _STAT_LABELS.get(k, k)
            bottlenecks = analysis.get("bottlenecks", [])
            mark = " ← 미달" if k in bottlenecks else " ✓"
            lines.append(f"  {label}: {v['value']}/{v['required']}{mark}")
        return "<br>".join(lines)
    elif reason == "번아웃":
        return f"원인: 번아웃 ({analysis.get('duration', '?')}일 연속)<br>  스트레스: {analysis.get('stress', '?')} / 체력: {analysis.get('energy', '?')}"
    elif reason == "만성_스트레스":
        return f"원인: 만성 스트레스 (누적 {analysis.get('duration', '?')}일)<br>  스트레스: {analysis.get('stress', '?')} / 체력: {analysis.get('energy', '?')}"
    elif reason == "희망퇴직":
        factor = analysis.get("voluntary_factor", "")
        factor_str = f" — {factor}" if factor else ""
        return f"원인: 희망퇴직 (경력 {analysis.get('career_years', '?')}년차 {analysis.get('position', '?')}){factor_str}"
    elif reason == "정년퇴직":
        return f"경력 {analysis.get('career_years', '?')}년 — {analysis.get('position', '?')}으로 정년퇴직"
    return ""


# ── 한 줄 요약 (rule-based) ───────────────────────────────────────────────────

def _one_line_summary(s: dict) -> str:
    perf      = s.get("performance", 0)
    boss      = s.get("boss_favor", 0)
    stress    = s.get("stress", 0)
    energy    = s.get("energy", 0)
    peer      = s.get("peer_relation", 0)
    rep       = s.get("reputation", 0)

    if perf < 25 and boss < 20:
        return "성과도 없고 상사 눈 밖에도 났다 — 짤릴 위기"
    if perf < 25:
        return "성과 부족 — 조만간 면담 각"
    if boss < 20:
        return "상사가 못 마땅히 여기는 게 느껴진다"
    if stress >= 85 and energy <= 25:
        return "스트레스 폭발 직전 + 체력도 바닥"
    if stress >= 85:
        return "스트레스 폭발 직전 — 휴가가 절실하다"
    if stress >= 70:
        return "스트레스가 슬슬 쌓이고 있다"
    if energy <= 10:
        return "몸이 한계 신호를 보내고 있다"
    if energy <= 25:
        return "체력이 위험하다 — 좀 쉬어야 할 것 같다"
    if stress < 35 and energy >= 75 and perf >= 75:
        return "승승장구 중 — 회사원이 천직인듯"
    if perf >= 80:
        return "이 기세면 진급도 문제없다"
    if boss >= 80:
        return "상사한테 완전 낙점됐다"
    if peer >= 80:
        return "사내 인싸 등극 — 동료들 사이 인기 최고"
    if stress < 40 and energy >= 60:
        return "회사생활 이상무!"
    return "그럭저럭 버티는 중"


def _hover_text(s: dict, personality: str = "") -> str:
    """단일 차트용 호버 텍스트."""
    events_str = ", ".join(s.get("events", [])) or "없음"
    summary = _one_line_summary(s)
    score = _composite_score(s)
    job_changes = s.get("job_changes", 0)
    job_str = f" / 이직 {job_changes}회" if job_changes > 0 else ""
    sep = "─" * 27
    return (
        f"<b>{personality}</b> ({s['position']}{job_str})<br>"
        f"행동: {s['action']}<br>"
        f"<i>{summary}</i><br>"
        f"{sep}<br>"
        f"• 연봉: {s['salary']:,}원<br>"
        f"• 이벤트: {events_str}<br>"
        f"{sep}<br>"
        f"성과: {s.get('performance', 0):.0f}  │  "
        f"상사호감: {s.get('boss_favor', 0):.0f}  │  "
        f"업무능력: {s.get('skill', 0):.0f}<br>"
        f"동료관계: {s.get('peer_relation', 0):.0f}  │  "
        f"평판: {s.get('reputation', 0):.0f}  │  "
        f"정치력: {s.get('political_skill', 0):.0f}<br>"
        f"스트레스: {s.get('stress', 0):.0f}  │  "
        f"체력: {s.get('energy', 0):.0f}  │  "
        f"<b>총점: {score:.0f}</b>"
    )


def _build_milestones(steps: list[dict], result: dict | None = None,
                      duration: int = 30) -> list[str]:
    """승진/이직/퇴사 발생 후 duration일간 마일스톤 텍스트를 표시한다."""
    milestones = [""] * len(steps)
    if not steps:
        return milestones

    # 이벤트 발생 지점 탐지
    events: list[tuple[int, str]] = []  # (day_idx, text)
    prev_pos = steps[0]["position"]
    prev_jc = steps[0].get("job_changes", 0)
    for idx, s in enumerate(steps):
        if s["position"] != prev_pos:
            events.append((idx, f"★ 승진 발생 : {prev_pos} → {s['position']}"))
            prev_pos = s["position"]
        cur_jc = s.get("job_changes", 0)
        if cur_jc > prev_jc:
            events.append((idx, "◆ 이직 발생"))
            prev_jc = cur_jc

    # 퇴사/해고/종료 마일스톤 (마지막 스텝 — 역방향 duration)
    end_text = None
    if result:
        analysis = result.get("exit_analysis") or {}
        if not analysis:
            log = result.get("_exit_log", {})
            analysis = log.get("analysis", {})
        reason = analysis.get("reason", "")
        reason_map = {
            "성과_부진": "성과 부진", "승진_미달": "승진 미달",
            "번아웃": "번아웃", "만성_스트레스": "만성 스트레스",
            "희망퇴직": "희망퇴직",
        }
        if reason == "현직유지":
            end_text = "👔 현직 유지 (임원)"
        elif reason == "희망퇴직":
            factor = analysis.get("voluntary_factor", "")
            factor_str = f" — {factor}" if factor else ""
            end_text = f"✕ 퇴사 발생 : 희망퇴직({factor_str.lstrip(' — ')})" if factor else "✕ 퇴사 발생 : 희망퇴직"
        elif reason in reason_map:
            end_text = f"✕ 퇴사 발생 : {reason_map[reason]}"
        elif result.get("is_retired"):
            end_text = "🎉 정년퇴직"
        elif not reason:
            final_pos = result.get("final_position", steps[-1].get("position", "?"))
            if final_pos == "임원":
                end_text = f"👔 현직 유지 ({final_pos})"
            else:
                end_text = f"🎉 정년퇴직 ({final_pos})"

    # 일반 이벤트: 발생일부터 duration일간 표시 (새 이벤트가 이전 것을 덮어씀)
    for evt_idx, text in events:
        for d in range(evt_idx, min(evt_idx + duration, len(steps))):
            milestones[d] = text

    # 종료 마일스톤: 마지막 duration일 동안 역방향으로 표시
    if end_text:
        start = max(0, len(steps) - duration)
        for d in range(start, len(steps)):
            milestones[d] = end_text

    return milestones


def _exit_stat_html(analysis: dict) -> str:
    """퇴사/해고 시 스탯 비교 테이블 HTML 생성 (3번째 열용)."""
    reason = analysis.get("reason", "")
    stats = analysis.get("stats", {})
    if not stats:
        # 번아웃/만성스트레스 — 스탯 테이블 대신 간단 표시
        if reason == "번아웃":
            return (f"<div style='font-size:11px;line-height:1.6;color:#C62828;'>"
                    f"<b>번아웃</b> ({analysis.get('duration','?')}일)<br>"
                    f"스트레스: {analysis.get('stress','?')}<br>"
                    f"체력: {analysis.get('energy','?')}</div>")
        elif reason == "만성_스트레스":
            return (f"<div style='font-size:11px;line-height:1.6;color:#C62828;'>"
                    f"<b>만성 스트레스</b> ({analysis.get('duration','?')}일)<br>"
                    f"스트레스: {analysis.get('stress','?')}<br>"
                    f"체력: {analysis.get('energy','?')}</div>")
        return ""
    bottlenecks = analysis.get("bottlenecks", [])
    rows = ""
    for k, v in stats.items():
        label = _STAT_LABELS.get(k, k)
        val = v.get("value", "?")
        req = v.get("required", v.get("threshold", "?"))
        if k in bottlenecks:
            mark = "<span style='color:#C62828;'> ✗</span>"
        else:
            mark = "<span style='color:#2E7D32;'> ✓</span>"
        rows += f"<tr><td style='padding:1px 4px;font-size:11px;'>{label}</td><td style='padding:1px 4px;font-size:11px;'>{val}/{req}{mark}</td></tr>"
    return f"<table style='border-collapse:collapse;'>{rows}</table>"


def _hover_text_comparison(s: dict, display_name: str, milestone: str = "",
                           exit_analysis: dict | None = None,
                           agent_color: str = "#999",
                           survived_days: int = 0,
                           pos_rank: int = 0,
                           salary: int = 0) -> str:
    """비교 차트용 호버 텍스트 — 스탯테이블 | 행동/연봉/이벤트 | 퇴사스탯(해당 시)."""
    events_str = ", ".join(s.get("events", [])) or "없음"
    summary = _one_line_summary(s)
    score = _composite_score(s)
    job_changes = s.get("job_changes", 0)
    job_str = f" / 이직 {job_changes}회" if job_changes > 0 else ""
    day = s["day"]
    day_label = _day_to_label(day)
    milestone_tag = f" <b style='color:#C62828;'>{milestone}</b>" if milestone else ""

    # 스탯 3열 테이블 데이터
    stats = [
        ("성과", s.get("performance", 0)),
        ("상사", s.get("boss_favor", 0)),
        ("능력", s.get("skill", 0)),
        ("동료", s.get("peer_relation", 0)),
        ("평판", s.get("reputation", 0)),
        ("정치", s.get("political_skill", 0)),
        ("스트레스", s.get("stress", 0)),
        ("체력", s.get("energy", 0)),
    ]
    stat_rows = ""
    for row_start in range(0, len(stats), 3):
        cells = ""
        for label, val in stats[row_start:row_start + 3]:
            cells += f"<td style='padding:2px 6px;border:1px solid #e0e0e0;font-size:12px;'><b>{label}</b> {val:.0f}</td>"
        remaining = 3 - len(stats[row_start:row_start + 3])
        cells += "<td style='border:1px solid #e0e0e0;'></td>" * remaining
        stat_rows += f"<tr>{cells}</tr>"
    stat_rows += f"<tr><td colspan='3' style='padding:3px 6px;border:1px solid #e0e0e0;text-align:center;font-size:12px;background:#f0f0f0;'><b>총점: {score:.0f}</b></td></tr>"

    # 퇴사 스탯 (3번째 열, 해당 시에만)
    exit_col = ""
    if exit_analysis:
        exit_html = _exit_stat_html(exit_analysis)
        if exit_html:
            exit_col = f"<div style='border-left:1px solid #e0e0e0;padding-left:10px;'>{exit_html}</div>"

    return (
        f"<div style='margin-bottom:8px;' data-color='{agent_color}' data-survived='{survived_days}' data-posrank='{pos_rank}' data-salary='{salary}'>"
        f"<b>DAY {day}</b> ({day_label}){milestone_tag}<br>"
        f"<b>{display_name}</b> ({s['position']}{job_str})"
        f"</div>"
        f"<div style='display:flex;gap:12px;'>"
        f"<div><table style='border-collapse:collapse;'>{stat_rows}</table></div>"
        f"<div style='font-size:12px;line-height:1.8;'>"
        f"행동: <b>{s['action']}</b><br>"
        f"연봉: <b>{s['salary']:,}원</b><br>"
        f"이벤트: {events_str}<br>"
        f"<i style='color:#555;'>\" {summary} \"</i>"
        f"</div>"
        f"{exit_col}"
        f"</div>"
    )


# ── 단일 실행 인터랙티브 차트 ─────────────────────────────────────────────────

def draw_interactive_html(log_path: Path, show: bool = False) -> Path:
    """
    단일 시뮬레이션 로그 → 인터랙티브 HTML 차트
    - 상단: 핵심 스탯 라인 (마우스 올리면 상태값 + 한 줄 요약)
    - 중단: 연봉 추이
    - 하단: 이벤트 마커 (긍정=초록, 부정=빨강)
    """
    result, steps = load_log(log_path)
    if not steps:
        print(f"[경고] 스텝 데이터가 없습니다: {log_path}")
        return log_path

    days     = [s["day"] for s in steps]
    hovers   = [_hover_text(s) for s in steps]

    # 승진 감지
    promotions = []
    prev_pos = steps[0]["position"]
    for s in steps[1:]:
        if s["position"] != prev_pos:
            promotions.append({"day": s["day"], "from": prev_pos, "to": s["position"]})
            prev_pos = s["position"]

    # 이직 감지
    job_changes_list = []
    prev_jc = steps[0].get("job_changes", 0)
    for s in steps[1:]:
        cur_jc = s.get("job_changes", 0)
        if cur_jc > prev_jc:
            job_changes_list.append({"day": s["day"], "count": cur_jc})
            prev_jc = cur_jc

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.55, 0.25, 0.20],
        subplot_titles=["핵심 스탯 추이", "연봉 추이 (원)", "이벤트"],
        vertical_spacing=0.07,
    )

    # ── Row 1: 스탯 라인 ─────────────────────────────────────────────
    for key, label, color, visible in STAT_LINES:
        values = [s.get(key, 0) for s in steps]
        fig.add_trace(go.Scatter(
            x=days, y=values,
            mode="lines",
            name=label,
            line=dict(color=color, width=1.8),
            visible=True if visible else "legendonly",
            hovertext=hovers,
            hovertemplate="%{hovertext}<extra></extra>",
        ), row=1, col=1)

    # 해고 위험선
    fig.add_hline(y=20, line_dash="dot", line_color="#E53935", line_width=1,
                  opacity=0.5, row=1, col=1,
                  annotation_text="성과 해고 기준", annotation_font_size=9)

    # ── Row 2: 연봉 ──────────────────────────────────────────────────
    salaries = [s["salary"] for s in steps]
    sal_hovers = [
        f"<b>Day {s['day']}</b><br>연봉: {s['salary']:,}원<br>직급: {s['position']}<extra></extra>"
        for s in steps
    ]
    fig.add_trace(go.Scatter(
        x=days, y=salaries,
        mode="lines",
        name="연봉",
        line=dict(color="#1565C0", width=2),
        fill="tozeroy",
        fillcolor="rgba(21,101,192,0.12)",
        hovertemplate="%{text}<extra></extra>",
        text=[f"Day {s['day']}<br>{s['salary']:,}원<br>{s['position']}" for s in steps],
        showlegend=True,
    ), row=2, col=1)

    # ── Row 3: 이벤트 마커 ───────────────────────────────────────────
    evt_days_pos, evt_days_neg = [], []
    evt_text_pos, evt_text_neg = [], []
    for s in steps:
        for evt in s.get("events", []):
            if evt in _POSITIVE_EVENTS:
                evt_days_pos.append(s["day"])
                evt_text_pos.append(f"Day {s['day']}: {evt}")
            else:
                evt_days_neg.append(s["day"])
                evt_text_neg.append(f"Day {s['day']}: {evt}")

    if evt_days_pos:
        fig.add_trace(go.Scatter(
            x=evt_days_pos, y=[1] * len(evt_days_pos),
            mode="markers",
            marker=dict(color="#43A047", size=9, symbol="circle"),
            name="긍정 이벤트",
            text=evt_text_pos,
            hovertemplate="%{text}<extra></extra>",
        ), row=3, col=1)

    if evt_days_neg:
        fig.add_trace(go.Scatter(
            x=evt_days_neg, y=[0.4] * len(evt_days_neg),
            mode="markers",
            marker=dict(color="#E53935", size=9, symbol="circle"),
            name="부정 이벤트",
            text=evt_text_neg,
            hovertemplate="%{text}<extra></extra>",
        ), row=3, col=1)

    # ── 승진 수직선 ──────────────────────────────────────────────────
    for p in promotions:
        fig.add_vline(
            x=p["day"], line_dash="dash", line_color="#7B1FA2", line_width=1.2,
            opacity=0.7,
            annotation_text=f"★ {p['to']}",
            annotation_font_size=10,
            annotation_font_color="#7B1FA2",
        )

    # ── 이직 수직선 ──────────────────────────────────────────────────
    for jc in job_changes_list:
        fig.add_vline(
            x=jc["day"], line_dash="dot", line_color="#546E7A", line_width=1.5,
            opacity=0.7,
            annotation_text=f"🔄 이직{jc['count']}회",
            annotation_font_size=10,
            annotation_font_color="#546E7A",
        )

    # ── 성찰 마커 (row=1 스탯 차트에 표시) ────────────────────────────
    reflections = result.get("_reflections", [])
    if reflections:
        day_to_score = {}
        for s in steps:
            # row1에는 개별 스탯이 표시되므로, performance를 y값으로 사용
            day_to_score[s["day"]] = s.get("performance", 0)
        ref_days, ref_ys, ref_texts = [], [], []
        for ref in reflections:
            ref_day = ref.get("day", 0)
            if ref_day in day_to_score:
                ref_days.append(ref_day)
                ref_ys.append(day_to_score[ref_day])
                ref_body = ref.get("text", "").replace("\n", "<br>")
                ref_texts.append(
                    f"<b>🔍 자기성찰</b> Day {ref_day}<br>"
                    f"─────────<br>"
                    f"{ref_body}"
                )
        if ref_days:
            fig.add_trace(go.Scatter(
                x=ref_days, y=ref_ys,
                mode="markers",
                marker=dict(color="#FF6F00", size=10, symbol="triangle-up",
                            line=dict(color="white", width=1)),
                name="자기성찰",
                hovertemplate="%{text}<extra></extra>",
                text=ref_texts,
            ), row=1, col=1)

    # ── 레이아웃 ─────────────────────────────────────────────────────
    agent_name   = result.get("agent", log_path.stem)
    survived     = result.get("survived_days", "?")
    final_pos    = result.get("final_position", "?")
    final_sal    = result.get("final_salary", 0)
    if result.get("is_fired"):
        ea = result.get("exit_analysis") or {}
        fire_detail = ea.get("detail", "")
        fire_reason = ea.get("reason", "")
        end_status = "권고사직" if ("권고사직" in fire_detail or fire_reason == "승진_미달") else "해고"
    elif result.get("is_resigned"):
        resign_reason = (result.get("exit_analysis") or {}).get("reason", "")
        end_status = "희망퇴직" if resign_reason == "희망퇴직" else "자진퇴사"
    elif result.get("is_retired"):
        end_status = "정년퇴직"
    else:
        end_status = "정상 종료"
    # 원인 요약 (타이틀에 간략히 표시)
    reason_brief = ""
    exit_analysis = result.get("exit_analysis", {})
    if exit_analysis.get("reason"):
        r = exit_analysis["reason"]
        if r == "승진_미달":
            bottlenecks = exit_analysis.get("bottlenecks", [])
            bn_text = ", ".join(_STAT_LABELS.get(b, b) for b in bottlenecks)
            reason_brief = f" (원인: 승진 미달 — {bn_text} 부족)" if bn_text else " (원인: 승진 미달)"
        elif r == "성과_부진":
            reason_brief = " (원인: 성과 부진)"
        elif r == "번아웃":
            reason_brief = f" (원인: 번아웃 {exit_analysis.get('duration', '?')}일)"
        elif r == "만성_스트레스":
            reason_brief = f" (원인: 만성 스트레스 {exit_analysis.get('duration', '?')}일)"

    fig.update_layout(
        title=dict(
            text=f"[{agent_name}]  {survived}일 생존  |  최종: {final_pos}  |  {final_sal:,}원  |  {end_status}{reason_brief}",
            font=dict(size=14),
        ),
        hovermode="x unified",
        height=750,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white",
        margin=dict(t=100, b=40, l=60, r=40),
    )
    max_day = days[-1] if days else 1
    tickvals, ticktext = _make_time_ticks(max_day)
    fig.update_yaxes(range=[0, 105], row=1, col=1)
    fig.update_yaxes(row=3, col=1, showticklabels=False, range=[0, 1.5])
    for row in (1, 2, 3):
        fig.update_xaxes(tickvals=tickvals, ticktext=ticktext, row=row, col=1)
    fig.update_xaxes(title_text="기간", row=3, col=1)

    out_path = log_path.with_suffix(".html")
    fig.write_html(str(out_path))
    print(f"인터랙티브 차트 저장됨: {out_path}")
    if show:
        fig.show()
    return out_path


# ── 여러 성향 비교 차트 ───────────────────────────────────────────────────────

def _composite_score(s: dict) -> float:
    return (
        s.get("skill", 0)           * 0.20 +
        s.get("performance", 0)     * 0.30 +
        s.get("boss_favor", 0)      * 0.25 +
        s.get("reputation", 0)      * 0.15 +
        s.get("political_skill", 0) * 0.10
    )


def _moving_average(values: list[float], window: int = 30) -> list[float]:
    result = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        result.append(sum(values[start:i+1]) / (i - start + 1))
    return result


def draw_comparison_html(log_paths: list, show: bool = False) -> Path:
    """
    여러 성향 JSONL 로그 → 비교 HTML 차트
    - Row 1: 종합 점수 비교 선 그래프 (30일 이동평균)
    - Row 2: 성향별 회사(평일) 행동 비율 원그래프
    - Row 3: 성향별 주말 행동 비율 원그래프
    """
    from collections import Counter

    datasets = []
    for p in log_paths:
        result, steps = load_log(Path(p))
        if steps:
            raw_name    = result.get("agent", Path(p).stem)
            display     = _display_name(raw_name)
            datasets.append({"name": raw_name, "display": display,
                             "result": result, "steps": steps})

    if not datasets:
        print("[경고] 유효한 데이터셋이 없습니다.")
        return Path(log_paths[0])

    # 생존일수 → 직급 → 연봉 내림차순 정렬 (범례·카드 순서 일치)
    _POS_RANK = {"사원": 0, "대리": 1, "과장": 2, "차장": 3, "부장": 4, "이사": 5, "임원": 6}
    datasets.sort(key=lambda d: (
        d["result"].get("survived_days", len(d["steps"])),
        _POS_RANK.get(d["result"].get("final_position", ""), 0),
        d["result"].get("final_salary", 0),
    ), reverse=True)

    n = len(datasets)

    # 레이아웃: row1=라인 차트(전체 폭), row2=평일 파이 n개, row3=주말 파이 n개
    specs = [
        [{"colspan": n, "type": "xy"}] + [None] * (n - 1),
        [{"type": "pie"}] * n,
        [{"type": "pie"}] * n,
    ]
    weekday_titles = [f"회사 행동, {d['display']}" for d in datasets]
    weekend_titles = [f"주말 행동, {d['display']}" for d in datasets]

    # 시뮬 기간(일) → 연수 표현
    max_day_all = max((d["steps"][-1]["day"] if d["steps"] else 0) for d in datasets)
    years_str = f"{max_day_all // 365}년" if max_day_all >= 365 else f"{max_day_all}일"
    line_title = f"성향별 회사에서 살아남기 — {years_str}의 직장 일대기"

    fig = make_subplots(
        rows=3, cols=n,
        specs=specs,
        subplot_titles=[""] + weekday_titles + weekend_titles,
        row_heights=[0.42, 0.28, 0.26],
        vertical_spacing=0.15,
    )

    max_day = 1
    for d in datasets:
        last = d["steps"][-1]["day"] if d["steps"] else 1
        max_day = max(max_day, last)
    tickvals, ticktext = _make_time_ticks(max_day)

    # ── Row 1: 종합 점수 라인 ─────────────────────────────────────────
    for i, d in enumerate(datasets):
        color  = AGENT_PALETTE[i % len(AGENT_PALETTE)]
        steps  = d["steps"]
        days   = [s["day"] for s in steps]
        scores = [_composite_score(s) for s in steps]
        ma     = _moving_average(scores, window=30)
        milestones = _build_milestones(steps, result=d["result"])
        # 마지막 스텝에만 exit_analysis 전달
        r_data = d["result"]
        ea = r_data.get("exit_analysis") or {}
        if not ea:
            log = r_data.get("_exit_log", {})
            ea = log.get("analysis", {})
        agent_survived = d["result"].get("survived_days", len(steps))
        agent_pos_rank = _POS_RANK.get(d["result"].get("final_position", ""), 0)
        agent_salary = d["result"].get("final_salary", 0)
        hovers = []
        for idx, (s, m) in enumerate(zip(steps, milestones)):
            ex = ea if (ea and idx == len(steps) - 1) else None
            hovers.append(_hover_text_comparison(s, display_name=d["display"],
                                                  milestone=m, exit_analysis=ex,
                                                  agent_color=color,
                                                  survived_days=agent_survived,
                                                  pos_rank=agent_pos_rank,
                                                  salary=agent_salary))
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)

        # 원시 점수 (흐릿)
        fig.add_trace(go.Scatter(
            x=days, y=scores,
            mode="lines",
            legendgroup=d["display"],
            showlegend=False,
            line=dict(color=color, width=0.7),
            opacity=0.22,
            hoverinfo="skip",
        ), row=1, col=1)

        # 범례에 최종 결과 표시 (모든 에이전트에 종료 사유 + 직급)
        r_data = d["result"]
        final_pos = r_data.get("final_position", "")
        exit_reason = (r_data.get("exit_analysis") or {}).get("reason", "")
        if r_data.get("is_fired"):
            ea = r_data.get("exit_analysis") or {}
            fire_detail = ea.get("detail", "")
            fire_reason = ea.get("reason", "")
            if "권고사직" in fire_detail or fire_reason == "승진_미달":
                reason_text = "권고사직"
            else:
                reason_map = {"성과_부진": "성과부진", "승진_미달": "승진미달",
                              "번아웃": "번아웃", "만성_스트레스": "만성스트레스"}
                reason_text = reason_map.get(exit_reason, "해고")
            legend_suffix = f" ({final_pos}/{reason_text})" if final_pos else f" ({reason_text})"
        elif exit_reason == "희망퇴직":
            legend_suffix = f" ({final_pos}/희망퇴직)" if final_pos else " (희망퇴직)"
        elif r_data.get("is_resigned"):
            legend_suffix = f" ({final_pos}/퇴사)" if final_pos else " (퇴사)"
        elif r_data.get("is_retired"):
            legend_suffix = f" ({final_pos}/정년퇴직)"
        elif exit_reason == "현직유지":
            legend_suffix = f" ({final_pos}/현직유지)"
        else:
            legend_suffix = f" ({final_pos})" if final_pos else ""
        legend_name = d["display"] + legend_suffix

        # 이동평균 (진하게)
        fig.add_trace(go.Scatter(
            x=days, y=ma,
            mode="lines",
            name=legend_name,
            legendgroup=d["display"],
            line=dict(color=color, width=2.5),
            fill="tozeroy",
            fillcolor=f"rgba({r},{g},{b},0.07)",
            hovertext=hovers,
            hovertemplate="%{hovertext}<extra></extra>",
            hoverlabel=dict(
                bgcolor=f"rgba({r},{g},{b},0.08)",
                bordercolor=color,
                font=dict(size=12, color="#222", family="monospace"),
            ),
        ), row=1, col=1)

        # 승진 마커 (그래프 위 ★ 점으로 표시, 호버로 상세 확인)
        promo_days, promo_scores, promo_texts = [], [], []
        prev_pos = steps[0]["position"]
        for s in steps[1:]:
            if s["position"] != prev_pos:
                promo_days.append(s["day"])
                promo_scores.append(_composite_score(s))
                promo_texts.append(
                    f"<b>★ 승진!</b><br>{d['display']}: {prev_pos} → {s['position']}<br>"
                    f"Day {s['day']} ({_day_to_label(s['day'])})<br>"
                    f"연봉: {s['salary']:,}원"
                )
                prev_pos = s["position"]
        if promo_days:
            fig.add_trace(go.Scatter(
                x=promo_days, y=promo_scores,
                mode="markers",
                marker=dict(color=color, size=12, symbol="star", line=dict(color="white", width=1)),
                legendgroup=d["display"],
                showlegend=False,
                hoverinfo="skip",
            ), row=1, col=1)

        # 이직 마커 (그래프 위 🔄 점으로 표시)
        jc_days, jc_scores, jc_texts = [], [], []
        prev_jc = steps[0].get("job_changes", 0)
        for s in steps[1:]:
            cur_jc = s.get("job_changes", 0)
            if cur_jc > prev_jc:
                jc_days.append(s["day"])
                jc_scores.append(_composite_score(s))
                jc_texts.append(
                    f"<b>🔄 이직 {cur_jc}회</b><br>{d['display']}<br>"
                    f"Day {s['day']} ({_day_to_label(s['day'])})<br>"
                    f"연봉: {s['salary']:,}원  |  {s['position']}"
                )
                prev_jc = cur_jc
        if jc_days:
            fig.add_trace(go.Scatter(
                x=jc_days, y=jc_scores,
                mode="markers",
                marker=dict(color=color, size=10, symbol="diamond", line=dict(color="white", width=1)),
                legendgroup=d["display"],
                showlegend=False,
                hoverinfo="skip",
            ), row=1, col=1)

        # 종료 마커 (해고/퇴사 시 그래프 끝에 X 표시)
        r_data = d["result"]
        if r_data.get("is_fired") or r_data.get("is_resigned"):
            last_step = steps[-1]
            last_day = last_step["day"]
            last_score = _composite_score(last_step)
            if r_data.get("is_fired"):
                ea = r_data.get("exit_analysis") or {}
                fire_detail = ea.get("detail", "")
                fire_reason = ea.get("reason", "")
                end_label = "권고사직" if ("권고사직" in fire_detail or fire_reason == "승진_미달") else "해고"
                end_symbol = "x"
            else:
                end_label = "자진퇴사"
                end_symbol = "cross"
            reason_text = _exit_reason_text(r_data)
            reason_line = f"<br>─────────<br>{reason_text}" if reason_text else ""
            end_text = (
                f"<b>{end_label}</b><br>{d['display']}<br>"
                f"Day {last_day} ({last_day // 365}년 {(last_day % 365) // 30}개월)<br>"
                f"최종: {last_step['position']}  |  연봉: {last_step['salary']:,}원"
                f"{reason_line}"
            )
            fig.add_trace(go.Scatter(
                x=[last_day], y=[last_score],
                mode="markers",
                marker=dict(color=color, size=14, symbol=end_symbol,
                            line=dict(color="white", width=2)),
                legendgroup=d["display"],
                showlegend=False,
                hoverinfo="skip",
            ), row=1, col=1)

        # 성찰 마커 + annotation (triangle-up, 호버로 성찰 내용 + 그래프에 핵심 키워드)
        reflections = d["result"].get("_reflections", [])
        if reflections:
            day_to_score = {s["day"]: _composite_score(s) for s in steps}
            ref_days, ref_scores, ref_texts = [], [], []
            ref_annotations = []  # (day, score, short_text)
            for ref in reflections:
                ref_day = ref.get("day", 0)
                if ref_day not in day_to_score:
                    continue
                score = day_to_score[ref_day]
                ref_days.append(ref_day)
                ref_scores.append(score)
                ref_body = ref.get("text", "").replace("\n", "<br>")
                ref_texts.append(
                    f"<b>🔍 자기성찰</b> Day {ref_day} ({_day_to_label(ref_day)})<br>"
                    f"─────────<br>"
                    f"{ref_body}"
                )
                # 문제점 줄에서 핵심 키워드 추출 → annotation용
                short = _extract_reflection_label(ref.get("text", ""))
                if short:
                    ref_annotations.append((ref_day, score, short))

            if ref_days:
                r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
                fig.add_trace(go.Scatter(
                    x=ref_days, y=ref_scores,
                    mode="markers",
                    marker=dict(color=f"rgba({r},{g},{b},0.7)", size=10,
                                symbol="triangle-up",
                                line=dict(color="white", width=1)),
                    legendgroup=d["display"],
                    showlegend=False,
                    hovertemplate="%{text}<extra></extra>",
                    text=ref_texts,
                    hoverlabel=dict(
                        bgcolor="rgba(255,255,255,0.95)",
                        bordercolor=color,
                        font=dict(size=11, color="#222", family="monospace"),
                    ),
                ), row=1, col=1)

            # 핵심 성찰 annotation (최대 4개, 균등 간격으로 선택)
            max_annotations = 4
            if ref_annotations:
                step_size = max(1, len(ref_annotations) // max_annotations)
                selected = [ref_annotations[j] for j in range(0, len(ref_annotations), step_size)][:max_annotations]
                for idx, (aday, ascore, alabel) in enumerate(selected):
                    # 위/아래 교대 배치로 겹침 방지
                    ay_offset = -35 if idx % 2 == 0 else 35
                    fig.add_annotation(
                        x=aday, y=ascore,
                        text=alabel,
                        showarrow=True,
                        arrowhead=0,
                        arrowwidth=1,
                        arrowcolor=color,
                        ax=0, ay=ay_offset,
                        font=dict(size=9, color=color),
                        bgcolor="rgba(255,255,255,0.85)",
                        bordercolor=color,
                        borderwidth=1,
                        borderpad=2,
                        xref="x", yref="y",
                    )

    fig.update_xaxes(tickvals=tickvals, ticktext=ticktext,
                     title_text="기간", row=1, col=1)
    fig.update_yaxes(range=[0, 100], title_text="종합 점수", row=1, col=1)

    # ── Row 2 & 3: 평일 / 주말 행동 비율 파이 차트 ────────────────────
    all_weekday_actions: list[str] = []
    all_weekend_actions: list[str] = []
    seen_wd: set[str] = set()
    seen_we: set[str] = set()

    for d in datasets:
        for s in d["steps"]:
            a = s["action"]
            if a in _WEEKEND_ACTIONS:
                if a not in seen_we:
                    all_weekend_actions.append(a)
                    seen_we.add(a)
            else:
                if a not in seen_wd:
                    all_weekday_actions.append(a)
                    seen_wd.add(a)

    for i, d in enumerate(datasets):
        weekday_steps = [s for s in d["steps"] if s["action"] not in _WEEKEND_ACTIONS]
        weekend_steps = [s for s in d["steps"] if s["action"] in _WEEKEND_ACTIONS]

        for row_idx, step_subset in [(2, weekday_steps), (3, weekend_steps)]:
            if not step_subset:
                continue
            counts = Counter(s["action"] for s in step_subset)
            labels = list(counts.keys())
            values = list(counts.values())
            colors = [ACTION_COLORS.get(lbl, "#BDBDBD") for lbl in labels]
            total  = sum(values)
            custom = [f"{lbl}<br>{cnt}회 ({cnt/total*100:.1f}%)"
                      for lbl, cnt in zip(labels, values)]

            fig.add_trace(go.Pie(
                labels=labels,
                values=values,
                marker=dict(colors=colors, line=dict(color="#fff", width=1.5)),
                textinfo="percent",
                textposition="inside",
                textfont=dict(size=10),
                hovertemplate="%{customdata}<extra></extra>",
                customdata=custom,
                legendgroup="weekday_actions" if row_idx == 2 else "weekend_actions",
                showlegend=False,
                hole=0.25,
            ), row=row_idx, col=i + 1)

    # 평일 행동 범례 (legend2)
    for action in all_weekday_actions:
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode="markers",
            marker=dict(color=ACTION_COLORS.get(action, "#BDBDBD"), size=10, symbol="square"),
            name=action,
            legend="legend2",
            showlegend=True,
        ), row=1, col=1)

    # 주말 행동 범례 (legend3)
    for action in all_weekend_actions:
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode="markers",
            marker=dict(color=ACTION_COLORS.get(action, "#BDBDBD"), size=10, symbol="square"),
            name=action,
            legend="legend3",
            showlegend=True,
        ), row=1, col=1)

    # ── 마커 범례 (승진/이직/해고 아이콘 설명) ─────────────────────
    for symbol, label, color in [
        ("star", "승진", "#7B1FA2"),
        ("diamond", "이직", "#546E7A"),
        ("x", "해고/퇴사", "#E53935"),
    ]:
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode="markers",
            marker=dict(color=color, size=10, symbol=symbol),
            name=label,
            showlegend=True,
        ), row=1, col=1)

    fig.update_layout(
        title=dict(
            text=line_title,
            font=dict(size=15),
            x=0.01, xanchor="left",
        ),
        hovermode="x",
        hoverlabel=dict(font=dict(size=1, family="monospace"), bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)"),
        height=1150,
        # 에이전트명 + 마커 범례 (선 그래프 우측 상단, 세로 배치)
        legend=dict(
            orientation="v", yanchor="top", y=1.0, xanchor="left", x=1.01,
            font=dict(size=12),
        ),
        # 평일 행동 범례 (회사 행동 파이차트 바로 아래, row2-row3 사이 간격)
        legend2=dict(
            orientation="h", yanchor="top", y=0.345, xanchor="center", x=0.5,
            font=dict(size=11), title=dict(text="회사 행동  ", side="left"),
        ),
        # 주말 행동 범례 (주말 행동 파이차트 바로 아래)
        legend3=dict(
            orientation="h", yanchor="top", y=-0.02, xanchor="center", x=0.5,
            font=dict(size=11), title=dict(text="주말 행동  ", side="left"),
        ),
        template="plotly_white",
        margin=dict(t=80, b=150, l=60, r=180),
    )

    names_tag = "_".join(d["display"] for d in datasets)
    out_path  = Path(log_paths[0]).parent / f"{_dt.now().strftime('%y%m%d_%H%M%S')}_comparison_{names_tag}.html"

    # 각 에이전트의 종료 카드 미리 생성 (color → final card HTML)
    import html as _html
    end_cards_js = {}
    for i, d in enumerate(datasets):
        color = AGENT_PALETTE[i % len(AGENT_PALETTE)]
        last_step = d["steps"][-1]
        r_data = d["result"]
        # 종료 마일스톤 텍스트
        analysis = r_data.get("exit_analysis") or {}
        if not analysis:
            log = r_data.get("_exit_log", {})
            analysis = log.get("analysis", {})
        reason = analysis.get("reason", "")
        final_pos = r_data.get("final_position", last_step.get("position", "?"))
        if reason == "현직유지" or (not reason and final_pos == "임원"):
            end_milestone = "👔 현직 유지 (임원)"
        elif reason in ("성과_부진", "승진_미달", "번아웃", "만성_스트레스"):
            detail = analysis.get("detail", "")
            if "권고사직" in detail or reason == "승진_미달":
                # 상세 사유: 승진심사탈락 vs 스탯부족
                bottlenecks = analysis.get("bottlenecks", [])
                if not bottlenecks:
                    fail_cnt = analysis.get("promotion_fail_count")
                    if fail_cnt is not None:
                        sub_reason = f"승진심사 {fail_cnt}회 탈락"
                    else:
                        sub_reason = "승진심사 탈락"
                else:
                    stat_kr = {"skill": "업무능력", "performance": "성과", "boss_favor": "상사신뢰", "reputation": "평판"}
                    lacking = ", ".join(stat_kr.get(b, b) for b in bottlenecks)
                    sub_reason = f"{lacking} 부족"
                target = analysis.get("target_position", "")
                pos_info = f" [{final_pos}→{target}]" if target else ""
                end_milestone = f"✕ 권고사직 ({sub_reason}){pos_info}"
            else:
                reason_kr = {"성과_부진": "성과 부진", "승진_미달": "승진 미달",
                             "번아웃": "번아웃", "만성_스트레스": "만성 스트레스"}[reason]
                end_milestone = f"✕ 퇴사 발생 : {reason_kr}"
        elif reason == "희망퇴직":
            factor = analysis.get("voluntary_factor", "")
            end_milestone = f"✕ 퇴사 발생 : 희망퇴직({factor})" if factor else "✕ 퇴사 발생 : 희망퇴직"
        elif r_data.get("is_retired"):
            end_milestone = "🎉 정년퇴직"
        else:
            end_milestone = f"🎉 정년퇴직 ({final_pos})"

        survived = r_data.get("survived_days", last_step.get("day", 0))
        end_pos_rank = _POS_RANK.get(r_data.get("final_position", ""), 0)
        end_salary = r_data.get("final_salary", 0)
        ea = analysis if analysis else None
        end_hover = _hover_text_comparison(
            last_step, display_name=d["display"],
            milestone=end_milestone, exit_analysis=ea,
            agent_color=color, survived_days=survived,
            pos_rank=end_pos_rank, salary=end_salary)
        end_card_html = (f'<div class="info-card" style="border-left:4px solid {color};">'
                         f'{end_hover}</div>')
        end_cards_js[color] = end_card_html.replace("'", "\\'").replace("\n", "")

    # 커스텀 HTML: 차트 70% + 호버 정보 패널 30% 고정 레이아웃
    chart_html = fig.to_html(full_html=False, include_plotlyjs="cdn", div_id="chart")
    custom_html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>{line_title}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ display: flex; height: 100vh; font-family: 'Malgun Gothic', monospace; background: #fafafa; }}
  #chart-container {{ width: 70%; height: 100%; overflow-y: auto; }}
  #info-panel {{
    width: 30%; height: 100%; overflow-y: auto;
    border-left: 2px solid #ddd; background: #fff;
    padding: 16px; font-size: 13px; line-height: 1.6;
  }}
  .hoverlayer .hovertext {{ display: none !important; }}
  #info-panel h3 {{
    font-size: 15px; margin-bottom: 12px; padding-bottom: 8px;
    border-bottom: 2px solid #1565C0; color: #1565C0;
  }}
  #info-content {{ }}
  .info-card {{
    background: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 6px;
    padding: 12px; margin-bottom: 10px;
  }}
  .info-card table {{ border-collapse: collapse; }}
  .info-card td {{ white-space: nowrap; }}
  .info-card.reflect {{
    background: #fff8e1; border-color: #ffb300;
  }}
  .info-placeholder {{
    color: #999; font-style: italic; margin-top: 40px; text-align: center;
  }}
</style>
</head><body>
<div id="chart-container">{chart_html}</div>
<div id="info-panel">
  <h3>상세 정보</h3>
  <div id="info-content">
    <p class="info-placeholder">그래프 위에 마우스를 올리면<br>상세 정보가 여기에 표시됩니다</p>
  </div>
</div>
<script>
  var chartDiv = document.getElementById('chart');
  var infoContent = document.getElementById('info-content');

  // 에이전트별 종료 카드 (미리 생성)
  var endCards = {{{', '.join(f"'{k}': '{v}'" for k, v in end_cards_js.items())}}};
  // 에이전트가 한번이라도 호버에 등장했는지 추적
  var seenAgents = {{}};

  function buildCard(txt) {{
    var isReflect = txt.includes('자기성찰');
    var cls = isReflect ? 'info-card reflect' : 'info-card';
    var colorMatch = txt.match(/data-color='([^']+)'/);
    var borderStyle = colorMatch ? 'border-left:4px solid ' + colorMatch[1] + ';' : '';
    return '<div class="' + cls + '" style="' + borderStyle + '">' + txt + '</div>';
  }}

  function getAgentKey(txt) {{
    // data-survived + data-color 조합으로 에이전트 식별
    var cm = txt.match(/data-color='([^']+)'/);
    return cm ? cm[1] : '';
  }}

  chartDiv.on('plotly_hover', function(data) {{
    var currentCards = {{}};
    data.points.forEach(function(pt) {{
      var txt = pt.hovertext || pt.text || '';
      if (!txt || txt === 'undefined') return;
      if (txt.includes('자기성찰')) return;
      var key = getAgentKey(txt);
      if (key) {{
        currentCards[key] = buildCard(txt);
        seenAgents[key] = true;
      }}
    }});
    // 현재 호버에 없지만 이전에 등장한 에이전트 → 종료 카드 표시
    Object.keys(seenAgents).forEach(function(key) {{
      if (!currentCards[key] && endCards[key]) {{
        currentCards[key] = endCards[key];
      }}
    }});
    var allCards = Object.values(currentCards);
    if (allCards.length > 0) {{
      allCards.sort(function(a, b) {{
        var sa = Number((a.match(/data-survived='(\d+)'/) || [0,0])[1]);
        var sb = Number((b.match(/data-survived='(\d+)'/) || [0,0])[1]);
        if (sa !== sb) return sb - sa;
        var pa = Number((a.match(/data-posrank='(\d+)'/) || [0,0])[1]);
        var pb = Number((b.match(/data-posrank='(\d+)'/) || [0,0])[1]);
        if (pa !== pb) return pb - pa;
        var ya = Number((a.match(/data-salary='(\d+)'/) || [0,0])[1]);
        var yb = Number((b.match(/data-salary='(\d+)'/) || [0,0])[1]);
        return yb - ya;
      }});
      infoContent.innerHTML = allCards.join('');
    }}
  }});

  chartDiv.on('plotly_unhover', function() {{
    // 호버 해제 시 마지막 내용 유지
  }});
</script>
</body></html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(custom_html)
    print(f"비교 차트 저장됨: {out_path}")
    if show:
        import webbrowser
        webbrowser.open(str(out_path))
    return out_path


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) >= 2:
        path = Path(sys.argv[1])
    else:
        logs = sorted(Path("logs").glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
        if not logs:
            print("logs/ 폴더에 .jsonl 파일이 없습니다.")
            sys.exit(1)
        path = logs[-1]
        print(f"최신 로그 파일 사용: {path}")

    if not path.exists():
        print(f"파일을 찾을 수 없습니다: {path}")
        sys.exit(1)

    draw_interactive_html(path, show=True)


if __name__ == "__main__":
    main()
