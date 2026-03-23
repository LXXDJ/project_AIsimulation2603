from pathlib import Path
from visualize_plotly import draw_comparison_html

logs = [
    Path("logs/260323_101153_ReAct_균형형.jsonl"),
    Path("logs/260323_101153_ReAct_성과형.jsonl"),
    Path("logs/260323_101153_ReAct_사교형.jsonl"),
    Path("logs/260323_101153_ReAct_정치형.jsonl"),
    Path("logs/260323_101153_ReAct_워라밸형.jsonl"),
]

path = draw_comparison_html(logs, show=False)
print(f"생성 완료: {path}")
