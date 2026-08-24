"""
Eval 报告生成器。

输出两种格式：
1. JSON：完整数据，供程序化分析
2. Markdown：人类可读，直接贴 README / 面试材料
"""
import json
from datetime import datetime
from pathlib import Path


def to_json(report: dict) -> str:
    """序列化 eval 报告为 JSON 字符串。"""
    return json.dumps(report, ensure_ascii=False, indent=2, default=str)


def to_markdown(report: dict) -> str:
    """生成 Markdown 格式的 eval 报告。"""
    agg = report.get("aggregate", {})
    config_name = report.get("config_name", "unknown")
    timestamp = report.get("timestamp", "")

    lines = [
        f"# Eval 报告: {config_name}",
        "",
        f"> 生成时间: {timestamp}",
        f"> 测试用例数: {report.get('test_case_count', 0)}",
        f"> 总耗时: {report.get('total_duration_sec', 0)}s",
        "",
        "## 聚合指标",
        "",
        "| 指标 | 值 |",
        "|------|-----|",
        f"| 有效用例 | {agg.get('valid_cases', 0)} / {agg.get('total_cases', 0)} |",
        f"| 成功数 | {agg.get('success_count', 0)} |",
        f"| **成功率** | **{agg.get('success_rate', 0):.1%}** |",
        f"| 平均步数 | {agg.get('avg_step_count', '-')} |",
        f"| 平均 Critic 触发 | {agg.get('avg_critic_count', '-')} |",
        f"| Critic 建议重规划率 | {_fmt_pct(agg.get('avg_critic_replan_rate'))} |",
        f"| 平均错误数 | {agg.get('avg_error_count', '-')} |",
        f"| LLM-judge 平均分 | {agg.get('avg_llm_judge_score', '-')} / 5 |",
        f"| 平均耗时 | {agg.get('avg_duration_sec', '-')}s |",
        "",
        "### 状态分布",
        "",
        "| 状态 | 数量 |",
        "|------|------|",
    ]

    for status, count in agg.get("status_distribution", {}).items():
        lines.append(f"| {status} | {count} |")

    lines.extend([
        "",
        "### 工具调用分布（全部 run 合并）",
        "",
        "| 工具 | 调用次数 |",
        "|------|----------|",
    ])
    for tool, count in sorted(agg.get("tool_call_distribution", {}).items(), key=lambda x: -x[1]):
        lines.append(f"| {tool} | {count} |")

    lines.extend([
        "",
        "## 单 run 明细",
        "",
        "| 用例 | 场景 | 状态 | 步数 | Critic | 成功 | judge | 耗时 | 摘要预览 |",
        "|------|------|------|------|--------|------|-------|------|----------|",
    ])

    for r in report.get("results", []):
        m = r.get("metrics") or {}
        status = m.get("status", "error")
        steps = m.get("step_count", "-")
        critic = m.get("critic_count", "-")
        success = "✓" if m.get("success") else "✗"
        judge = (m.get("llm_judge") or {}).get("overall_score", "-")
        duration = r.get("duration_sec", "-")
        preview = (m.get("summary_preview", "") or "").replace("|", "\\|").replace("\n", " ")[:50]
        error = r.get("error")
        if error:
            status = f"ERROR: {error[:30]}"
        lines.append(
            f"| {r['case_id']} | {r['scenario']} | {status} | {steps} | "
            f"{critic} | {success} | {judge} | {duration}s | {preview} |"
        )

    return "\n".join(lines)


def to_ablation_markdown(reports: list[dict]) -> str:
    """生成 ablation 对比 Markdown 报告。"""
    lines = [
        "# Ablation 消融实验对比",
        "",
        f"> 生成时间: {datetime.now().isoformat()}",
        "",
        "## 聚合对比",
        "",
        "| 配置 | 成功率 | 平均步数 | Critic 触发 | 建议重规划率 | LLM-judge | 平均耗时 |",
        "|------|--------|----------|-------------|---------------|-----------|----------|",
    ]

    for report in reports:
        agg = report.get("aggregate", {})
        name = report.get("config_name", "?")
        sr = f"{agg.get('success_rate', 0):.1%}"
        steps = agg.get("avg_step_count", "-")
        critic = agg.get("avg_critic_count", "-")
        replan = _fmt_pct(agg.get('avg_critic_replan_rate'))
        judge = agg.get("avg_llm_judge_score", "-")
        dur = f"{agg.get('avg_duration_sec', '-')}s"
        lines.append(f"| {name} | {sr} | {steps} | {critic} | {replan} | {judge} | {dur} |")

    lines.extend(["", "## 逐用例对比", ""])

    # 收集所有 case_id
    all_cases = []
    seen = set()
    for report in reports:
        for r in report.get("results", []):
            if r["case_id"] not in seen:
                all_cases.append(r["case_id"])
                seen.add(r["case_id"])

    # 表头：case_id | scenario | 每个配置的 (status, steps, judge)
    header = "| 用例 | 场景 |"
    separator = "|------|------|"
    for report in reports:
        name = report.get("config_name", "?")
        header += f" {name} |"
        separator += "------|"
    lines.append(header)
    lines.append(separator)

    for case_id in all_cases:
        scenario = ""
        cells = []
        for report in reports:
            found = None
            for r in report.get("results", []):
                if r["case_id"] == case_id:
                    found = r
                    if not scenario:
                        scenario = r["scenario"]
                    break
            if found and found.get("metrics"):
                m = found["metrics"]
                judge = (m.get("llm_judge") or {}).get("overall_score", "-")
                success = "✓" if m.get("success") else "✗"
                cells.append(f"{success}/{m['step_count']}步/judge{judge}")
            elif found and found.get("error"):
                cells.append("ERROR")
            else:
                cells.append("-")
        row = f"| {case_id} | {scenario} | " + " | ".join(cells) + " |"
        lines.append(row)

    return "\n".join(lines)


def _fmt_pct(val) -> str:
    """格式化百分比，None → '-'。"""
    if val is None:
        return "-"
    return f"{val:.1%}"


def save_report(report: dict, output_dir: str = "eval_reports") -> dict:
    """保存报告到文件，返回文件路径。"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    config_name = report.get("config_name", "report")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = out / f"{config_name}_{timestamp}.json"
    md_path = out / f"{config_name}_{timestamp}.md"

    json_path.write_text(to_json(report), encoding="utf-8")
    md_path.write_text(to_markdown(report), encoding="utf-8")

    return {"json": str(json_path), "markdown": str(md_path)}


def save_ablation_report(reports: list[dict], output_dir: str = "eval_reports") -> dict:
    """保存 ablation 对比报告。"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out / f"ablation_{timestamp}.json"
    md_path = out / f"ablation_{timestamp}.md"

    json_path.write_text(
        json.dumps(reports, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    md_path.write_text(to_ablation_markdown(reports), encoding="utf-8")

    return {"json": str(json_path), "markdown": str(md_path)}
