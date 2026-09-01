"""
Agent prompt 模板。

温度策略（面试 tradeoff）：
- Actuator temperature=0.3：基本确定性，留轻微随机以演"不同 run 不同路径"反玩具指标
- Critic temperature=0：判断要稳定，同一状态不应给出不同结论
- summarize temperature=0.7：摘要需一定创造性
"""
import json

from .tools import TOOLS_DESCRIPTION


ACTUATOR_SYSTEM = f"""你是财税日报生成 Agent。任务：根据给定日期，自主抓取政策、清洗、去重、分类、生成摘要，最终产出一份 .docx 日报。

可用工具（按需调用，不必全用）：
{TOOLS_DESCRIPTION}

决策规则：
- 每次只调一个工具，基于上一步 observation 决策
- 政策数据为空时，考虑换数据源（如已 fetch_central 为空则试 fetch_local）或求助
- 摘要必须只反映当日政策：summarize 基于当日已清洗政策生成，每条政策对应1条摘要（最多5条），不足5条绝不凑数
- 严禁把历史政策、RAG 检索结果或背景知识混入当日摘要
- related_analysis 用于生成"关联政策分析"（历史政策的延续/修订/配套关系），其结果只进入报告独立章节
- rag_search 仅用于了解历史背景，命中结果不得写入当日摘要
- 数据为空时不要强行 summarize，会产出无意义摘要
- 工具返回 error 时，不要重复调用同一工具，应切换策略或求助
- 所有政策处理完且摘要就绪后，调 format_docx 收尾
- format_docx 成功后输出 done=true

输出格式（严格 JSON，不要 markdown 代码块包裹）：
{{
  "reasoning": "为什么选这个工具（一句话）",
  "tool": "工具名 或 finish",
  "params": {{}},
  "done": false
}}
"""


def build_step_prompt(state, max_steps=15, replan_hint=None):
    """每步拼装 Actuator 的 user prompt。

    ReAct 完整化：显式标注 Action(params) → Observation，让 LLM 基于上一步工具返回结果决策。
    A3：注入 episodic memory 历史经验段落（若有），让 Agent 跨会话复用经验。
    """
    recent = state.trace[-5:] if state.trace else []
    trace_lines = []
    for t in recent:
        tool = t.get('tool') or '-'
        params = t.get('input') or {}
        out = t.get('output') or {}
        # params 非空才显示，避免空 () 噪音
        params_preview = json.dumps(params, ensure_ascii=False)[:80] if params else ""
        # 输出压缩成一行预览（即 Observation）
        out_preview = str(out)[:120]
        action_str = f"{tool}({params_preview})" if params_preview else tool
        trace_lines.append(
            f"  step {t.get('step')}: Action={action_str} → Observation: {out_preview}"
        )
    trace_str = "\n".join(trace_lines) if trace_lines else "  （无历史）"

    hint_str = f"\n[Critic 反馈]：{replan_hint}\n" if replan_hint else ""

    # A3: episodic memory 历史经验段落（仅当 context_hints 非空时显示）
    episodic_str = ""
    if getattr(state, 'context_hints', None):
        episodic_preview = "\n".join(
            f"  - {h[:200]}" for h in state.context_hints[:3]
        )
        episodic_str = f"""
历史 run 经验参考（RAG 检索，可借鉴工具调用顺序但勿照搬摘要）:
{episodic_preview}
"""

    return f"""任务: {state.task_input}
当前步数: {state.step}/{max_steps}
当前状态: {state.summary_view()}
{hint_str}{episodic_str}
历史 trace（最近 5 步，Action → Observation）:
{trace_str}

基于上一步 Observation 决策你的下一步 Action。（输出 JSON）"""


CRITIC_SYSTEM = f"""你是 Critic。评估当前 Agent 进度是否合理。

可用工具（replan_hint 只能建议以下工具，不得编造不存在的工具名）：
{TOOLS_DESCRIPTION}

检查:
1. 是否在原地打转（重复工具+参数）？
2. 是否数据为空却硬走摘要？
3. 是否该求助却没求助？
4. 步数是否过多未收敛？
5. 工具是否连续返回 error？若是，建议切换策略而非重复尝试

约束:
- replan_hint 中只能提及上述可用工具，绝不能编造新工具名
- 如果当前没有合适的工具能解决问题，建议 terminate 而非编造工具

输出格式（严格 JSON）：
{{
  "needs_replan": false,
  "replan_hint": "具体建议；若 needs_replan 为 false 则填空字符串"
}}
"""


def build_critic_prompt(state):
    """Critic 的 user prompt。"""
    recent = state.trace[-6:] if state.trace else []
    trace_lines = []
    for t in recent:
        tool = t.get('tool') or '-'
        out = t.get('output') or {}
        out_preview = str(out)[:120]
        trace_lines.append(f"  step {t.get('step')}: tool={tool} → {out_preview}")
    trace_str = "\n".join(trace_lines) if trace_lines else "  （无历史）"

    return f"""状态: {state.summary_view()}
步数: {state.step}
最近 trace:
{trace_str}

评估当前进度是否合理。"""
