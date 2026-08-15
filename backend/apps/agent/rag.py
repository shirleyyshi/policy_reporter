"""
RAG 检索封装：ChromaDB + 默认多语言 embedding（all-MiniLM-L6-v2）。

设计要点：
1. 索引存到 media/chroma_db/，服务器重启不丢
2. build_index 命令构建索引，rag_search 工具只读
3. 索引内容：title + content[:500]（避免单文档过长）
4. id 格式：central_<id> / local_<id>（避免两类政策 id 冲突）
5. 默认 embedding 模型多语言，中英文政策都能检索
"""
import json
import logging
from pathlib import Path

from django.conf import settings
import chromadb

logger = logging.getLogger(__name__)

# 索引持久化目录
_CHROMA_PATH = Path(settings.BASE_DIR) / 'media' / 'chroma_db'
_CHROMA_PATH.mkdir(parents=True, exist_ok=True)

_COLLECTION_NAME = "policies"
_EPISODIC_COLLECTION_NAME = "agent_episodic_memory"

# 模块级单例（避免每次 rag_search 都重建 client）
_client = None
_collection = None
_episodic_collection = None


def _get_collection():
    """获取 ChromaDB collection 单例。"""
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=str(_CHROMA_PATH))
        _collection = _client.get_or_create_collection(name=_COLLECTION_NAME)
    return _collection


def _get_episodic_collection():
    """获取 episodic memory collection 单例（与 policies 独立）。"""
    global _client, _episodic_collection
    if _episodic_collection is None:
        if _client is None:
            _client = chromadb.PersistentClient(path=str(_CHROMA_PATH))
        _episodic_collection = _client.get_or_create_collection(name=_EPISODIC_COLLECTION_NAME)
    return _episodic_collection


def rebuild_index(policies):
    """
    重建索引（幂等：先清空再插入）。

    Args:
        policies: list of dict，每条至少含
            id (int)、doc_text (str)、source (str)、title (str)、
            source_url (str)、publish_time (str)

    Returns:
        int: 索引中的文档数
    """
    col = _get_collection()

    # 清空已有数据
    existing = col.get()
    if existing and existing.get('ids'):
        col.delete(ids=existing['ids'])

    if not policies:
        return 0

    # 批量插入（ChromaDB 内部分批）
    col.add(
        documents=[p['doc_text'] for p in policies],
        metadatas=[
            {
                'source': p.get('source', ''),
                'title': p.get('title', ''),
                'source_url': p.get('source_url', ''),
                'publish_time': str(p.get('publish_time', '')),
            }
            for p in policies
        ],
        ids=[f"{p.get('source', 'unknown')}_{p['id']}" for p in policies],
    )
    return len(policies)


def search(query, n_results=3):
    """
    检索相似政策。

    Args:
        query: 查询文本（通常是当前政策的标题或摘要关键词）
        n_results: 返回条数

    Returns:
        list of dict，每条含 title/source/source_url/publish_time/score
        索引为空或查询为空时返回 []
    """
    if not query or not query.strip():
        return []

    col = _get_collection()
    if col.count() == 0:
        return []

    try:
        results = col.query(query_texts=[query], n_results=n_results)
    except Exception as e:
        logger.warning(f"RAG 检索异常（不影响 Agent）: {e}")
        return []

    hits = []
    docs = results.get('documents', [[]])
    metas = results.get('metadatas', [[]])
    dists = results.get('distances', [[]])

    if not docs or not docs[0]:
        return []

    for i, doc in enumerate(docs[0]):
        meta = metas[0][i] if i < len(metas[0]) else {}
        dist = dists[0][i] if i < len(dists[0]) else 1.0
        hits.append({
            'title': meta.get('title', ''),
            'source': meta.get('source', ''),
            'source_url': meta.get('source_url', ''),
            'publish_time': meta.get('publish_time', ''),
            'score': round(1.0 - dist, 3),  # 距离越小越相似，转成相似度
        })
    return hits


def index_count():
    """返回当前索引文档数。"""
    col = _get_collection()
    return col.count()


# ==================== Episodic Memory（A3：跨会话经验复用） ====================

def store_episodic_memory(run_id, date, summary, key_decisions):
    """
    存一次 run 的经验到 episodic memory collection。

    在 _run_loop 结束时调用，让后续 run 能检索复用历史经验。

    Args:
        run_id: run 标识（作为文档 id，幂等避免重复存储）
        date: 任务日期
        summary: 本次 run 生成的摘要
        key_decisions: list of dict，工具调用序列（如 [{'tool':'fetch_central','params':{...}}, ...]）

    Returns:
        bool: 是否存储成功
    """
    if not summary:
        return False
    try:
        col = _get_episodic_collection()
        # key_decisions 是 dict 列表，序列化为可读字符串
        if key_decisions:
            decisions_str = ', '.join(
                d.get('tool', '?') if isinstance(d, dict) else str(d)
                for d in key_decisions
            )
        else:
            decisions_str = '无'
        doc = (
            f"日期: {date}\n"
            f"摘要: {summary}\n"
            f"工具调用序列: {decisions_str}"
        )
        # metadatas 也存完整 key_decisions，便于精确复用
        col.upsert(
            documents=[doc],
            metadatas=[{
                'run_id': str(run_id),
                'date': str(date),
                'key_decisions': json.dumps(key_decisions, default=str) if key_decisions else '[]',
            }],
            ids=[f"ep_{run_id}"],
        )
        return True
    except Exception as e:
        logger.warning(f"episodic memory 存储失败（不影响 run）: {e}")
        return False


def retrieve_episodic_memory(query, n_results=3):
    """
    检索相似历史 run 经验。

    在 run_agent 开头调用，把命中经验注入 state.context_hints 供 LLM 参考。

    Args:
        query: 查询文本（通常是 "财税政策日报 {date}"）
        n_results: 返回条数

    Returns:
        list of str：命中历史经验的文档内容（已含日期/摘要/工具序列）。
        索引为空或查询为空时返回 []。
    """
    if not query or not query.strip():
        return []
    try:
        col = _get_episodic_collection()
        if col.count() == 0:
            return []
        results = col.query(query_texts=[query], n_results=n_results)
        docs = results.get('documents', [[]])
        if not docs or not docs[0]:
            return []
        return docs[0]
    except Exception as e:
        logger.warning(f"episodic memory 检索失败（不影响 Agent）: {e}")
        return []


def clear_episodic_memory():
    """
    清空 episodic memory collection（供 build_index 命令或手动重置调用）。

    Returns:
        int: 清除前的文档数
    """
    try:
        col = _get_episodic_collection()
        existing = col.get()
        count = len(existing.get('ids', [])) if existing else 0
        if count > 0:
            col.delete(ids=existing['ids'])
        return count
    except Exception as e:
        logger.warning(f"episodic memory 清空失败: {e}")
        return 0


def episodic_memory_count():
    """返回 episodic memory 当前文档数。"""
    try:
        return _get_episodic_collection().count()
    except Exception:
        return 0
