"""
Agent 工具集（Phase 2）。

设计要点（面试 tradeoff）：
1. 批量式工具：工具操作 AgentState，LLM 只看 state 摘要（计数），不看原始数据。
   避免把大段政策文本塞进 LLM 参数。Observer（core.py 里）负责据 tool 类型更新 state。
2. classify_policy 用确定性元数据（category_hint）而非 LLM：DB 里 CentralPolicy.type
   和 LocalPolicy.province 已是结构化字段，再调 LLM 纯属浪费。这是"并非每一步都需要 LLM"
   的工程判断。
3. fetch 不落库：数据在工具间以 Python 对象流动，trace 能展示"爬 12→清洗 12→去重 9"
   的数据变化——反玩具指标"不同 run 不同路径"的素材。
4. save_to_db 是 stub：fetch 已从 DB 读，政策已持久化，故仅返回"already in DB"。
   保留在 registry 里是为 trace 完整性，不在 happy path 上。
"""
import difflib
import re
from dataclasses import dataclass, field
from typing import Optional
from io import BytesIO

from django.conf import settings
from openai import OpenAI

from report.models import CentralPolicy, LocalPolicy
from report.views import generate_docx


# DeepSeek 客户端（复用 report.views 的配置模式）
_openai_client = OpenAI(
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
)


@dataclass
class AgentState:
    """Agent 运行时状态。工具批量操作此对象，LLM 只看摘要。"""
    task_input: dict                          # {date, legal_text}
    raw_policies: list = field(default_factory=list)      # fetch 累积
    clean_policies: list = field(default_factory=list)    # clean/dedup/classify 累积
    summary: Optional[str] = None
    related_analysis: Optional[str] = None               # 关联政策分析（基于 RAG 历史政策，独立章节，不进摘要）
    docx_bytes: Optional[bytes] = None
    trace: list = field(default_factory=list)             # 内存中的 trace（同时入 DB）
    step: int = 0
    status: str = "running"                  # running / waiting_human / done / failed
    fail_count: int = 0
    ask_human_count: int = 0
    last_actions: list = field(default_factory=list)      # [(tool, params_json, observation_preview), ...] 用于重复检测 + ReAct Observation 反馈
    human_input_callback: Optional[callable] = None       # Phase 5: 人在回路回调
    pending_question: Optional[dict] = None               # Phase 5: {question, options} 等待回答
    context_hints: list = field(default_factory=list)     # A3: RAG episodic memory 检索到的历史经验（list of str）

    def summary_view(self) -> str:
        """给 LLM 看的状态摘要（计数而非原始数据）。"""
        return (
            f"raw={len(self.raw_policies)} "
            f"clean={len(self.clean_policies)} "
            f"summary={'有' if self.summary else '无'} "
            f"docx={'有' if self.docx_bytes else '无'}"
        )


# ==================== 工具实现 ====================

def _extend_without_duplicates(state: AgentState, items: list, source: str):
    """按 (source, id) 幂等追加，已在 raw_policies 里的不再入列。

    fetch 用 extend 累积是设计（fetch_central + fetch_local 组合），但 LLM 若
    重复调用同一 fetch（Actuator 决策不可控），同一政策会进 raw 两次；后续一旦
    跳过 deduplicate（prompt 允许"不必全用"），docx 里就会出现重复政策。
    在 fetch 入口做幂等，重复调用返回 duplicates_skipped。
    """
    existing = {(p.get('source'), p.get('id')) for p in state.raw_policies}
    fresh = []
    for it in items:
        it['source'] = source
        if (source, it['id']) not in existing:
            fresh.append(it)
    state.raw_policies.extend(fresh)
    return len(fresh), len(items) - len(fresh)


def fetch_central(state: AgentState, params: dict) -> dict:
    """按日期取中央政策（读 DB）。params: {date}"""
    date = params.get("date") or state.task_input.get("date")
    qs = CentralPolicy.objects.filter(publish_time__date=date) if date else CentralPolicy.objects.all()
    items = list(qs.values('id', 'title', 'content', 'type', 'publish_time', 'source_url'))
    fetched, skipped = _extend_without_duplicates(state, items, 'central')
    return {"fetched": fetched, "duplicates_skipped": skipped, "source": "central", "date": date}


def fetch_local(state: AgentState, params: dict) -> dict:
    """按日期取地方政策（读 DB）。params: {date}"""
    date = params.get("date") or state.task_input.get("date")
    qs = LocalPolicy.objects.filter(publish_time__date=date) if date else LocalPolicy.objects.all()
    items = list(qs.values('id', 'title', 'content', 'province', 'type', 'publish_time', 'source_url'))
    fetched, skipped = _extend_without_duplicates(state, items, 'local')
    return {"fetched": fetched, "duplicates_skipped": skipped, "source": "local", "date": date}


def _clean_text(text: str) -> str:
    """确定性清洗：去 HTML 标签、归一化空白。"""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def clean_policy(state: AgentState, params: dict) -> dict:
    """清洗所有 raw_policies → clean_policies。确定性，不调 LLM。"""
    cleaned = []
    for raw in state.raw_policies:
        cleaned.append({
            'source': raw.get('source'),
            'id': raw.get('id'),
            'title': _clean_text(raw.get('title', '')),
            'content': _clean_text(raw.get('content', '')),
            'type': raw.get('type'),
            'province': raw.get('province'),
            'source_url': raw.get('source_url', ''),
            'publish_time': str(raw.get('publish_time', '')),
        })
    state.clean_policies = cleaned
    return {"cleaned": len(cleaned)}


def deduplicate(state: AgentState, params: dict) -> dict:
    """标题相似度（difflib）+ URL 去重。"""
    seen_urls = set()
    kept = []
    for item in state.clean_policies:
        url = item.get('source_url', '')
        if url and url in seen_urls:
            continue
        # 标题相似度：与已保留的比，>0.85 视为重复
        is_dup = False
        for k in kept:
            ratio = difflib.SequenceMatcher(None, item.get('title', ''), k.get('title', '')).ratio()
            if ratio > 0.85:
                is_dup = True
                break
        if not is_dup:
            kept.append(item)
            if url:
                seen_urls.add(url)
    removed = len(state.clean_policies) - len(kept)
    state.clean_policies = kept
    return {"kept": len(kept), "removed": removed}


def classify_policy(state: AgentState, params: dict) -> dict:
    """
    分类政策。用 DB 的 type 字段（业务分类：财政/税务/金融/商贸）确定性分类，
    不调 LLM。中央和地方统一用 type 做业务分类维度，province 仅作为地方属性保留。
    这是"并非每一步都需要 LLM"的工程判断。
    """
    for item in state.clean_policies:
        item['category'] = item.get('type') or '未分类'
    return {"classified": len(state.clean_policies)}


def summarize(state: AgentState, params: dict) -> dict:
    """LLM 摘要。仅基于当日政策，每条政策对应 1 条摘要，不足 5 条不凑数。"""
    texts = [item.get('content', '') for item in state.clean_policies if item.get('content')]
    if not texts:
        return {"summary": "", "note": "无政策内容，未生成摘要"}
    # 摘要条数 = 政策条数，最多 5 条；1 条政策就只生成 1 条摘要（与手动导出口径一致）
    target_count = min(len(texts), 5)
    selected_texts = texts[:target_count]
    prompt = (
        "假设你是一位财税专家，为公司管理层梳理每日日报热点。"
        f"请仅基于以下{len(selected_texts)}条当日财税类政策内容，为每条政策生成1条摘要要点，共{target_count}条。"
        "语言正式、简洁，适合放在财税简报的开头部分，每条20-35字。"
        "严禁引入所提供内容之外的信息（包括历史政策、背景知识），严禁为凑数而拆分或编造要点。"
        "不需要标题或者【今日财税热点摘要】之类的开头。"
        "每条摘要前请加一个圆点（• ），并换行显示，禁止使用星号(*)、序号（如1. 2. 3.）"
        "或其他Markdown格式符号。"
        f"必须且只能生成{target_count}条摘要，不要多生成也不要少生成。仅返回纯文本，不要多余解释。\n\n"
        + "\n\n".join(selected_texts)
    )
    response = _openai_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        stream=False,
        temperature=0.7,
    )
    state.summary = response.choices[0].message.content.strip()
    return {"summary_len": len(state.summary), "summary_preview": state.summary[:80]}


def rag_search(state: AgentState, params: dict) -> dict:
    """
    检索历史相似政策（ChromaDB 向量检索）。只读，不污染 state。

    定位（与 related_analysis 分工）：供 Actuator 了解历史背景 / 决策参考用，
    命中结果不得写入当日摘要。要产出报告里的"关联政策分析"章节应调
    related_analysis（它会自行检索并调 LLM 生成分析）。

    查询策略：
    - params 有 query 就用 query
    - 否则用 state.clean_policies 第一条的标题（典型场景：找相似历史政策）
    - 都没有就返回空
    """
    from .rag import search
    query = params.get("query", "")
    if not query and state.clean_policies:
        # 默认用第一条政策的标题当查询
        query = state.clean_policies[0].get('title', '')

    hits = search(query, n_results=3) if query else []

    # 把命中政策的 source_url 摘要进 observation，供 Actuator 决策
    return {
        "hits": hits,
        "query": query,
        "count": len(hits),
    }


def related_analysis(state: AgentState, params: dict) -> dict:
    """
    生成"关联政策分析"（LLM）：对当日政策检索历史相似政策，分析关联与变化
    （延续/修订/替代/配套关系）。结果存 state.related_analysis，只进入报告的
    独立章节，绝不混入当日摘要——历史政策的正确位置是分析，不是当日新闻。
    """
    if not state.clean_policies:
        return {"error": "无当日政策，无法生成关联分析"}

    from .rag import search
    today_urls = {it.get('source_url') for it in state.clean_policies}
    today_titles = {it.get('title') for it in state.clean_policies}

    # 每条当日政策检索 top2 历史相似，按 URL 去重合并
    history = {}
    for item in state.clean_policies[:5]:
        for hit in search(item.get('title', ''), n_results=2):
            # 排除当日政策自身（索引含当日数据，最相似的就是自己）
            if hit.get('source_url') in today_urls or hit.get('title') in today_titles:
                continue
            key = hit.get('source_url') or hit.get('title')
            history[key] = hit

    if not history:
        state.related_analysis = None
        return {"related": 0, "note": "未检索到相关历史政策，跳过关联分析"}

    today_lines = "\n".join(
        f"- 《{it.get('title', '')}》（{it.get('category') or it.get('type') or '未分类'}）"
        for it in state.clean_policies
    )
    history_lines = "\n".join(
        f"- 《{h.get('title', '')}》（发布于 {str(h.get('publish_time', ''))[:10]}，"
        f"{'中央政策' if h.get('source') == 'central' else '地方法规'}）"
        for h in history.values()
    )
    prompt = (
        "你是财税政策分析师。以下是【今日政策】和检索到的【历史相关政策】清单。"
        "请分析今日政策与历史政策之间的关联与变化（如延续、修订、替代、配套、呼应关系），"
        "生成不超过4条分析要点，每条30-60字，语言正式、克制。"
        "只能依据清单中给出的政策标题与日期分析，不得编造政策内容。"
        "今日政策之间若无历史政策对应，可分析其内在关联。"
        "每条要点前加一个圆点（• ），并换行显示，禁止使用星号、序号或其他Markdown格式符号。"
        "仅返回纯文本，不要多余解释。\n\n"
        f"【今日政策】\n{today_lines}\n\n【历史相关政策】\n{history_lines}"
    )
    response = _openai_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        stream=False,
        temperature=0.3,
    )
    state.related_analysis = response.choices[0].message.content.strip()
    return {
        "analysis_len": len(state.related_analysis),
        "history_count": len(history),
        "preview": state.related_analysis[:80],
    }


def save_to_db(state: AgentState, params: dict) -> dict:
    """持久化到数据库。Phase 2 stub：fetch 已从 DB 读，政策已落库。"""
    return {"saved": 0, "note": "政策已在 DB（fetch 直接读 DB），无需重复写入"}


def _dedup_for_docx(items: list, extra_titles: set = None) -> list:
    """docx 生成前的最后防线去重：按 URL 和完整标题精确去重。

    fetch 已幂等、deduplicate 工具可选，但 LLM 决策不可控（可能跳过 dedup），
    这里兜底保证同一政策绝不在 docx 里出现两次。
    extra_titles：跨表去重用（如地方转发中央文件标题相同时，地方侧剔除）。
    """
    seen_urls, seen_titles, kept = set(), set(extra_titles or ()), []
    for it in items:
        url = it.get('source_url') or ''
        title = it.get('title') or ''
        if url and url in seen_urls:
            continue
        if title and title in seen_titles:
            continue
        if url:
            seen_urls.add(url)
        if title:
            seen_titles.add(title)
        kept.append(it)
    return kept


def format_docx(state: AgentState, params: dict) -> dict:
    """生成最终 docx。复用 report.views.generate_docx，传入预计算 summary。"""
    if not state.summary:
        return {"error": "摘要未生成，无法产出 docx"}
    # 中央和地方统一用 type（业务分类）作为分组维度；去重兜底（见 _dedup_for_docx）
    central = _dedup_for_docx(
        [it for it in state.clean_policies if it.get('source') == 'central']
    )
    local = _dedup_for_docx(
        [it for it in state.clean_policies if it.get('source') == 'local'],
        extra_titles={it.get('title') for it in central},
    )
    central_rows = [
        (it.get('title', ''), it.get('content', ''), it.get('type', ''), it.get('source_url', ''))
        for it in central
    ]
    local_rows = [
        (it.get('title', ''), it.get('content', ''), it.get('type', ''), it.get('source_url', ''))
        for it in local
    ]
    out = BytesIO()
    # report_date 必须传：否则 generate_docx 标题回退为"当天"日期，与所选政策日期不符
    generate_docx(central_rows, local_rows, state.task_input.get('legal_text', ''), out,
                  summary=state.summary, report_date=state.task_input.get('date'),
                  related_analysis=state.related_analysis)
    state.docx_bytes = out.getvalue()
    return {
        "docx_size": len(state.docx_bytes),
        "central": len(central_rows),
        "local": len(local_rows),
        "dedup_removed": (len(state.clean_policies) - len(central_rows) - len(local_rows)),
        "related_analysis": bool(state.related_analysis),
    }


def ask_human(state: AgentState, params: dict) -> dict:
    """
    求助人工。
    - human_input_callback 为 None 时（eval/同步模式）：mock 返回第一个选项
    - human_input_callback 为 callable 时（Phase 5 异步模式）：通过回调暂停等待人工回答
    """
    state.ask_human_count += 1
    question = params.get("question", "")
    options = params.get("options", [])
    if state.human_input_callback:
        answer = state.human_input_callback(question, options)
        note = "人工回答"
    else:
        answer = options[0] if options else "继续"
        note = "Phase 2 mock 同步返回"
    return {"question": question, "answer": answer, "note": note}


# ==================== 工具注册表 ====================

TOOLS = {
    "fetch_central": fetch_central,
    "fetch_local": fetch_local,
    "clean_policy": clean_policy,
    "deduplicate": deduplicate,
    "classify_policy": classify_policy,
    "summarize": summarize,
    "rag_search": rag_search,
    "related_analysis": related_analysis,
    "save_to_db": save_to_db,
    "format_docx": format_docx,
    "ask_human": ask_human,
}


# 给 Actuator prompt 用的工具说明
TOOLS_DESCRIPTION = """
1. fetch_central(date) - 取某日中央政策（幂等：重复调用自动去重），返回条数
2. fetch_local(date) - 取某日地方政策（幂等：重复调用自动去重），返回条数
3. clean_policy() - 清洗所有已抓取政策（去 HTML、归一化），无需参数
4. deduplicate() - 标题相似度+URL 去重，无需参数
5. classify_policy() - 用 DB 元数据分类（type/province），无需参数
6. summarize() - 仅基于当日政策生成摘要（每条政策1条摘要，最多5条，不凑数）
7. rag_search(query) - 检索历史相似政策（只读，供了解历史背景；不得写入当日摘要）
8. related_analysis() - 检索历史政策并生成"关联政策分析"（延续/修订/配套等），进入报告独立章节
9. save_to_db() - 持久化（当前 stub，fetch 已落库）
10. format_docx() - 生成最终 docx，需 summary 已就绪，无需参数
11. ask_human(question, options) - 遇到不确定时求助（当前 mock 同步返回）
"""
