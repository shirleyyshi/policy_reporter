"""Agent rag.py 单元测试。

覆盖：
- _get_collection / _get_episodic_collection 单例
- rebuild_index：清空+插入 / 空列表
- search：空查询 / 空索引 / 正常检索 / 异常返回空
- index_count
- episodic memory 异常分支（store/retrieve/clear/count 的 except 路径）
"""
from unittest.mock import patch, MagicMock

from django.test import SimpleTestCase


class GetCollectionTest(SimpleTestCase):
    """测试 collection 单例获取。"""

    def test_get_collection_returns_singleton(self):
        """_get_collection 应返回同一实例。"""
        from agent.rag import _get_collection, _collection
        with patch('agent.rag.chromadb') as mock_chroma:
            mock_col = MagicMock()
            mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_col
            # 重置全局缓存
            import agent.rag as rag_mod
            rag_mod._collection = None
            rag_mod._client = None

            c1 = _get_collection()
            c2 = _get_collection()
            self.assertIs(c1, c2)

            # 清理
            rag_mod._collection = None
            rag_mod._client = None

    def test_get_episodic_collection_returns_singleton(self):
        import agent.rag as rag_mod
        rag_mod._episodic_collection = None
        rag_mod._client = None

        with patch('agent.rag.chromadb') as mock_chroma:
            mock_col = MagicMock()
            mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = mock_col
            c1 = rag_mod._get_episodic_collection()
            c2 = rag_mod._get_episodic_collection()
            self.assertIs(c1, c2)

        rag_mod._episodic_collection = None
        rag_mod._client = None


class RebuildIndexTest(SimpleTestCase):
    """测试 rebuild_index。"""

    def test_empty_policies_returns_zero(self):
        """空列表应返回 0，不调 col.add。"""
        from agent.rag import rebuild_index
        with patch('agent.rag._get_collection') as mock_get:
            mock_col = MagicMock()
            mock_col.get.return_value = {'ids': []}
            mock_get.return_value = mock_col
            result = rebuild_index([])
        self.assertEqual(result, 0)
        mock_col.add.assert_not_called()

    def test_rebuild_clears_then_inserts(self):
        """重建应先清空已有数据再插入。"""
        from agent.rag import rebuild_index
        with patch('agent.rag._get_collection') as mock_get:
            mock_col = MagicMock()
            mock_col.get.return_value = {'ids': ['old_1', 'old_2']}
            mock_get.return_value = mock_col

            policies = [
                {'id': 1, 'doc_text': '文档1', 'source': 'central',
                 'title': '标题1', 'source_url': 'http://x', 'publish_time': '2026-07-13'},
                {'id': 2, 'doc_text': '文档2', 'source': 'local',
                 'title': '标题2', 'source_url': 'http://y', 'publish_time': '2026-07-14'},
            ]
            result = rebuild_index(policies)

        self.assertEqual(result, 2)
        mock_col.delete.assert_called_once_with(ids=['old_1', 'old_2'])
        mock_col.add.assert_called_once()
        # 验证 ids 格式
        call_kwargs = mock_col.add.call_args.kwargs
        self.assertEqual(call_kwargs['ids'], ['central_1', 'local_2'])


class SearchTest(SimpleTestCase):
    """测试 search。"""

    def test_empty_query_returns_empty(self):
        from agent.rag import search
        self.assertEqual(search(''), [])
        self.assertEqual(search('   '), [])
        self.assertEqual(search(None), [])

    def test_empty_index_returns_empty(self):
        """索引为空时返回 []。"""
        from agent.rag import search
        with patch('agent.rag._get_collection') as mock_get:
            mock_col = MagicMock()
            mock_col.count.return_value = 0
            mock_get.return_value = mock_col
            result = search('查询')
        self.assertEqual(result, [])

    def test_normal_search_returns_hits(self):
        from agent.rag import search
        with patch('agent.rag._get_collection') as mock_get:
            mock_col = MagicMock()
            mock_col.count.return_value = 2
            mock_col.query.return_value = {
                'documents': [['文档1', '文档2']],
                'metadatas': [[
                    {'title': '标题1', 'source': 'central', 'source_url': 'http://x', 'publish_time': '2026-07-13'},
                    {'title': '标题2', 'source': 'local', 'source_url': 'http://y', 'publish_time': '2026-07-14'},
                ]],
                'distances': [[0.2, 0.5]],
            }
            mock_get.return_value = mock_col
            hits = search('查询', n_results=2)

        self.assertEqual(len(hits), 2)
        self.assertEqual(hits[0]['title'], '标题1')
        self.assertEqual(hits[0]['score'], 0.8)  # 1.0 - 0.2
        self.assertEqual(hits[1]['score'], 0.5)  # 1.0 - 0.5

    def test_search_exception_returns_empty(self):
        """col.query 抛异常时应返回 []，不向上传播。"""
        from agent.rag import search
        with patch('agent.rag._get_collection') as mock_get:
            mock_col = MagicMock()
            mock_col.count.return_value = 1
            mock_col.query.side_effect = Exception("index corrupted")
            mock_get.return_value = mock_col
            result = search('查询')
        self.assertEqual(result, [])

    def test_search_empty_results(self):
        """col.query 返回空文档时返回 []。"""
        from agent.rag import search
        with patch('agent.rag._get_collection') as mock_get:
            mock_col = MagicMock()
            mock_col.count.return_value = 1
            mock_col.query.return_value = {'documents': [[]], 'metadatas': [[]], 'distances': [[]]}
            mock_get.return_value = mock_col
            result = search('查询')
        self.assertEqual(result, [])


class IndexCountTest(SimpleTestCase):
    """测试 index_count。"""

    def test_returns_collection_count(self):
        from agent.rag import index_count
        with patch('agent.rag._get_collection') as mock_get:
            mock_col = MagicMock()
            mock_col.count.return_value = 42
            mock_get.return_value = mock_col
            self.assertEqual(index_count(), 42)


class EpisodicMemoryExceptionTest(SimpleTestCase):
    """测试 episodic memory 异常分支。"""

    def test_store_exception_returns_false(self):
        """store_episodic_memory 异常时应返回 False。"""
        from agent.rag import store_episodic_memory
        with patch('agent.rag._get_episodic_collection') as mock_get:
            mock_col = MagicMock()
            mock_col.upsert.side_effect = Exception("disk full")
            mock_get.return_value = mock_col
            result = store_episodic_memory('run-1', '2026-07-13', '摘要', ['tool1'])
        self.assertFalse(result)

    def test_retrieve_exception_returns_empty(self):
        from agent.rag import retrieve_episodic_memory
        with patch('agent.rag._get_episodic_collection') as mock_get:
            mock_col = MagicMock()
            mock_col.count.return_value = 1
            mock_col.query.side_effect = Exception("index error")
            mock_get.return_value = mock_col
            result = retrieve_episodic_memory('query')
        self.assertEqual(result, [])

    def test_retrieve_empty_results(self):
        """col.query 返回空文档时返回 []。"""
        from agent.rag import retrieve_episodic_memory
        with patch('agent.rag._get_episodic_collection') as mock_get:
            mock_col = MagicMock()
            mock_col.count.return_value = 1
            mock_col.query.return_value = {'documents': [[]]}
            mock_get.return_value = mock_col
            result = retrieve_episodic_memory('query')
        self.assertEqual(result, [])

    def test_clear_exception_returns_zero(self):
        from agent.rag import clear_episodic_memory
        with patch('agent.rag._get_episodic_collection') as mock_get:
            mock_col = MagicMock()
            mock_col.get.side_effect = Exception("error")
            mock_get.return_value = mock_col
            result = clear_episodic_memory()
        self.assertEqual(result, 0)

    def test_clear_when_empty(self):
        """collection 为空时返回 0，不调 delete。"""
        from agent.rag import clear_episodic_memory
        with patch('agent.rag._get_episodic_collection') as mock_get:
            mock_col = MagicMock()
            mock_col.get.return_value = {'ids': []}
            mock_get.return_value = mock_col
            result = clear_episodic_memory()
        self.assertEqual(result, 0)
        mock_col.delete.assert_not_called()

    def test_episodic_memory_count_exception(self):
        from agent.rag import episodic_memory_count
        with patch('agent.rag._get_episodic_collection') as mock_get:
            mock_col = MagicMock()
            mock_col.count.side_effect = Exception("error")
            mock_get.return_value = mock_col
            self.assertEqual(episodic_memory_count(), 0)
