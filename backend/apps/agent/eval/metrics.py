"""
Eval 指标计算。

两类指标：
1. 确定性指标（从 DB trace 统计）：成功率、步数、工具分布、Critic 触发率
2. LLM-as-judge（无参考打分）：让 DeepSeek 对摘要质量评 1-5 分

LLM-as-judge 不依赖手写 ground truth，而是基于绝对质量标准打分：
- 格式合规：圆点开头、≤5条、无 markdown、每条 20-35 字
- 内容覆盖：是否涵盖主要政策要点
- 语言质量：正式、简洁、中文
"""
import json
import logging
from collections import Counter
from typing import Optional

from django.conf import settings
from openai import OpenAI

from agent.models import AgentTrace
from agent.core import get_state, get_docx
from agent.utils import has_docx_trace

logger = logging.getLogger(__name__)

# 懒加载 LLM-judge 客户端（避免模块级初始化在 settings 未就绪时报错）
_judge_client = None


def _get_judge_client():
    """懒加载 OpenAI/DeepSeek 客户端。第一次调用时初始化。"""
    global _judge_client
    if _judge_client is None:
        _judge_client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
        )
    return _judge_client

JUDGE_SYSTEM = """你是一个严格的财税日报摘要评审专家。请对摘要进行 1-5 分评分。

评分维度：
1. format_score（格式合规）：圆点（• ）开头、≤5 条、无 markdown 符号、每条 20-35 字
   - 5: 完全合规
   - 3: 基本合规，有小瑕疵
   - 1: 严重违规（用了序号、星号、超条数等）
2. coverage_score（内容覆盖）：是否涵盖输入政策的主要要点
   - 5: 覆盖所有重要政策
   - 3: 覆盖部分
   - 1: 完全偏离或空泛
3. language_score（语言质量）：正式、简洁、中文
   - 5: 专业正式、简洁有力
   - 3: 基本合格
   - 1: 口语化或语病多

overall_score = round((format + coverage + language) / 3)

必须以 JSON 返回：{"format_score": int, "coverage_score": int, "language_score": int, "overall_score": int, "reasoning": "一句话评价"}"""

JUDGE_USER_TEMPLATE = """请评分以下摘要：

---
{summary}
---

请以 JSON 返回评分。如果摘要为空或无意义，所有分给 1。"""


def _get_traces(run_id) -> list[AgentTrace]:
    """获取某次 run 的所有 trace，按 step 排序。"""
    return list(AgentTrace.objects.filter(run_id=run_id).order_by('step'))


def success(run_id) -> bool:
    """任务是否成功：status == done 且生成了 docx。"""
    state = get_state(run_id)
    if state:
        return state.status == "done" and state.docx_bytes is not None
    # cache 丢失时从 DB 推断
    last = AgentTrace.objects.filter(run_id=run_id).order_by('-step').first()
    if not last or last.action != 'terminate':
        return False
    status = (last.output or {}).get('status', 'failed')
    if status != 'done':
        return False
    return has_docx_trace(run_id)


def status(run_id) -> str:
    """获取 run 的最终状态。"""
    state = get_state(run_id)
    if state:
        return state.status
    last = AgentTrace.objects.filter(run_id=run_id).order_by('-step').first()
    if not last:
        return 'unknown'
    if last.action != 'terminate':
        return 'incomplete'
    return (last.output or {}).get('status', 'failed')


def step_count(run_id) -> int:
    """总步数（DB trace 中最大的 step 值）。"""
    last = AgentTrace.objects.filter(run_id=run_id).order_by('-step').first()
    return last.step if last else 0


def tool_call_distribution(run_id) -> dict[str, int]:
    """工具调用分布：{tool_name: count}。只统计成功执行的工具调用。"""
    traces = AgentTrace.objects.filter(
        run_id=run_id, action='actuate', tool__isnull=False
    ).exclude(output__has_key='error')
    counter = Counter(t.tool for t in traces if t.tool)
    return dict(counter)


def critic_count(run_id) -> int:
    """Critic 触发次数。"""
    return AgentTrace.objects.filter(run_id=run_id, action='critique').count()


def critic_replan_rate(run_id) -> Optional[float]:
    """
    Critic 建议重规划率：触发 replan 的比例（建议≠修复，命名避免夸大）。
    返回 None 表示没有 Critic 触发（无法计算）。
    """
    critiques = AgentTrace.objects.filter(run_id=run_id, action='critique')
    total = critiques.count()
    if total == 0:
        return None
    replan_count = 0
    for c in critiques:
        if c.output and isinstance(c.output, dict) and c.output.get('needs_replan'):
            replan_count += 1
    return replan_count / total


def error_count(run_id) -> int:
    """错误 trace 数量（含工具异常、未知工具等）。"""
    return AgentTrace.objects.filter(
        run_id=run_id
    ).filter(output__has_key='error').count()


def ask_human_count(run_id) -> int:
    """ask_human 调用次数。"""
    return AgentTrace.objects.filter(
        run_id=run_id, tool='ask_human'
    ).count()


def has_docx(run_id) -> bool:
    """是否生成了 docx。"""
    state = get_state(run_id)
    if state and state.docx_bytes:
        return True
    return has_docx_trace(run_id)


def get_summary(run_id) -> str:
    """
    获取 run 的摘要文本。
    优先级：
    1. 内存 state.summary（最完整）
    2. DB trace 中 summarize 工具的 output.summary_preview（前 80 字，截断）
    3. 从 docx 文件提取（兜底，最完整但解析慢）
    """
    # 1. 内存 state
    state = get_state(run_id)
    if state and state.summary:
        return state.summary

    # 2. DB trace 的 summarize 工具输出（只有前 80 字预览，聊胜于无）
    summarize_trace = AgentTrace.objects.filter(
        run_id=run_id, tool='summarize'
    ).exclude(output__has_key='error').first()
    if summarize_trace and summarize_trace.output:
        preview = summarize_trace.output.get('summary_preview')
        if preview:
            # 标记为截断版本，让 LLM-judge 知道是不完整的
            return preview + "...（截断）"

    # 3. 从 docx 文件提取完整摘要
    docx_bytes = get_docx(run_id)
    if docx_bytes:
        return _extract_summary_from_docx(docx_bytes)
    return ""


def _extract_summary_from_docx(docx_bytes: bytes) -> str:
    """从 docx 文件提取摘要段落（以圆点开头的段落）。"""
    try:
        from docx import Document
        from io import BytesIO
        doc = Document(BytesIO(docx_bytes))
        # 摘要通常在文档开头的"今日热点"段落，以圆点（•）开头
        paragraphs = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text and text.startswith('•'):
                paragraphs.append(text)
        return '\n'.join(paragraphs)
    except ImportError:
        logger.error("python-docx 未安装，无法从 docx 提取摘要")
        return ""
    except Exception as e:
        logger.warning(f"docx 摘要提取失败: {e}")
        return ""


def llm_judge_score(summary: str) -> Optional[dict]:
    """
    LLM-as-judge 无参考打分。
    返回 {"format_score", "coverage_score", "language_score", "overall_score", "reasoning"}。
    失败返回 None。
    """
    if not summary or not summary.strip():
        return {
            "format_score": 1, "coverage_score": 1, "language_score": 1,
            "overall_score": 1, "reasoning": "摘要为空",
        }

    try:
        response = _get_judge_client().chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": JUDGE_USER_TEMPLATE.format(summary=summary)},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            stream=False,
        )
        content = response.choices[0].message.content
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            import re
            m = re.search(r'\{[\s\S]*\}', content)
            if m:
                return json.loads(m.group(0))
            return None
    except Exception as e:
        logger.warning(f"LLM-as-judge 调用失败: {e}")
        return None


def collect_run_metrics(run_id) -> dict:
    """
    收集单次 run 的全部指标。
    返回 dict，包含所有确定性指标 + LLM-as-judge 评分。
    """
    summary = get_summary(run_id)
    judge = llm_judge_score(summary)

    return {
        "run_id": str(run_id),
        "status": status(run_id),
        "success": success(run_id),
        "step_count": step_count(run_id),
        "tool_calls": tool_call_distribution(run_id),
        "critic_count": critic_count(run_id),
        "critic_replan_rate": critic_replan_rate(run_id),
        "error_count": error_count(run_id),
        "ask_human_count": ask_human_count(run_id),
        "has_docx": has_docx(run_id),
        "summary_length": len(summary),
        "summary_preview": summary[:120] if summary else "",
        "llm_judge": judge,
    }
