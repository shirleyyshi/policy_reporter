"""
Agent 工具单元测试。

覆盖：
- _clean_text: HTML 清洗 + 空白归一化
- clean_policy: 批量清洗
- deduplicate: URL 去重 + 标题相似度去重
- classify_policy: 用 DB 元数据分类
- AgentState.summary_view: 状态摘要
- AgentRun state 持久化（A2）：save_state/get_state 跨重启恢复

运行：
    python manage.py test agent
"""
import uuid as uuid_mod

from django.test import SimpleTestCase, TestCase

from agent.tools import (
    _clean_text, clean_policy, deduplicate, classify_policy,
    AgentState,
)


class CleanTextTest(SimpleTestCase):
    """测试 _clean_text 确定性清洗。"""

    def test_strips_html_tags(self):
        self.assertEqual(_clean_text("<p>hello</p>"), "hello")

    def test_strips_nested_html(self):
        self.assertEqual(
            _clean_text("<div><p>foo</p><span>bar</span></div>"),
            "foobar",
        )

    def test_replaces_nbsp(self):
        self.assertEqual(_clean_text("a&nbsp;b"), "a b")

    def test_collapses_whitespace(self):
        self.assertEqual(_clean_text("a\n\n  b\t\tc"), "a b c")

    def test_empty_input(self):
        self.assertEqual(_clean_text(""), "")
        self.assertEqual(_clean_text(None), "")

    def test_strips_outer_whitespace(self):
        self.assertEqual(_clean_text("  hello  "), "hello")


class CleanPolicyTest(SimpleTestCase):
    """测试 clean_policy 工具。"""

    def test_cleans_all_fields(self):
        state = AgentState(task_input={})
        state.raw_policies = [
            {
                'source': 'central',
                'id': 1,
                'title': '<p>政策标题</p>',
                'content': '<div>正文&nbsp;内容</div>',
                'type': '税务',
                'source_url': 'http://example.com/1',
                'publish_time': '2026-07-13',
            }
        ]
        result = clean_policy(state, {})
        self.assertEqual(result['cleaned'], 1)
        self.assertEqual(state.clean_policies[0]['title'], '政策标题')
        self.assertEqual(state.clean_policies[0]['content'], '正文 内容')
        self.assertEqual(state.clean_policies[0]['source'], 'central')

    def test_handles_empty_raw(self):
        state = AgentState(task_input={})
        result = clean_policy(state, {})
        self.assertEqual(result['cleaned'], 0)
        self.assertEqual(state.clean_policies, [])

    def test_preserves_metadata_fields(self):
        state = AgentState(task_input={})
        state.raw_policies = [{
            'source': 'local', 'id': 5,
            'title': 'test', 'content': 'test',
            'province': '上海', 'source_url': 'http://x',
            'publish_time': '2026-07-08',
        }]
        clean_policy(state, {})
        item = state.clean_policies[0]
        self.assertEqual(item['province'], '上海')
        self.assertEqual(item['source_url'], 'http://x')


class DeduplicateTest(SimpleTestCase):
    """测试 deduplicate 工具。"""

    def _make_item(self, title, url=''):
        return {'title': title, 'source_url': url, 'source': 'central'}

    def test_dedup_by_url(self):
        state = AgentState(task_input={})
        state.clean_policies = [
            self._make_item('标题A', 'http://x/1'),
            self._make_item('标题A不同', 'http://x/1'),  # URL 重复
        ]
        result = deduplicate(state, {})
        self.assertEqual(result['kept'], 1)
        self.assertEqual(result['removed'], 1)

    def test_dedup_by_title_similarity(self):
        state = AgentState(task_input={})
        state.clean_policies = [
            self._make_item('财政部关于2025年增值税留抵退税政策有关问题的通知', 'http://x/1'),
            self._make_item('财政部关于2025年增值税留抵退税政策有关问题的公告', 'http://x/2'),
            # 仅末字不同，相似度 >0.85，应被去重
        ]
        result = deduplicate(state, {})
        self.assertEqual(result['kept'], 1)
        self.assertEqual(result['removed'], 1)

    def test_no_dedup_when_titles_different(self):
        state = AgentState(task_input={})
        state.clean_policies = [
            self._make_item('关于教育的通知', 'http://x/1'),
            self._make_item('关于交通的公告', 'http://x/2'),
        ]
        result = deduplicate(state, {})
        self.assertEqual(result['kept'], 2)
        self.assertEqual(result['removed'], 0)

    def test_empty_clean_policies(self):
        state = AgentState(task_input={})
        result = deduplicate(state, {})
        self.assertEqual(result['kept'], 0)
        self.assertEqual(result['removed'], 0)

    def test_keeps_first_occurrence(self):
        """重复时保留先出现的那条。"""
        state = AgentState(task_input={})
        first = self._make_item('第一条', 'http://x/1')
        second = self._make_item('第一条', 'http://x/2')
        state.clean_policies = [first, second]
        deduplicate(state, {})
        self.assertEqual(state.clean_policies[0]['source_url'], 'http://x/1')


class ClassifyPolicyTest(SimpleTestCase):
    """测试 classify_policy 工具。"""

    def test_central_uses_type(self):
        state = AgentState(task_input={})
        state.clean_policies = [
            {'source': 'central', 'type': '税务', 'title': 'A'},
            {'source': 'central', 'type': '财政', 'title': 'B'},
        ]
        classify_policy(state, {})
        self.assertEqual(state.clean_policies[0]['category'], '税务')
        self.assertEqual(state.clean_policies[1]['category'], '财政')

    def test_local_uses_type(self):
        """地方政策也用 type（业务分类）做分类，与中央维度一致。"""
        state = AgentState(task_input={})
        state.clean_policies = [
            {'source': 'local', 'province': '上海', 'type': '税务', 'title': 'A'},
            {'source': 'local', 'province': '上海', 'type': '财政', 'title': 'B'},
        ]
        classify_policy(state, {})
        self.assertEqual(state.clean_policies[0]['category'], '税务')
        self.assertEqual(state.clean_policies[1]['category'], '财政')

    def test_fallback_when_metadata_missing(self):
        """type 字段缺失时回退到"未分类"。"""
        state = AgentState(task_input={})
        state.clean_policies = [
            {'source': 'central', 'title': 'A'},  # 没 type
            {'source': 'local', 'title': 'B'},    # 没 type
        ]
        classify_policy(state, {})
        self.assertEqual(state.clean_policies[0]['category'], '未分类')
        self.assertEqual(state.clean_policies[1]['category'], '未分类')


class AgentStateTest(SimpleTestCase):
    """测试 AgentState 数据类。"""

    def test_summary_view_initial(self):
        state = AgentState(task_input={'date': '2026-07-13'})
        s = state.summary_view()
        self.assertIn('raw=0', s)
        self.assertIn('clean=0', s)
        self.assertIn('summary=无', s)
        self.assertIn('docx=无', s)

    def test_summary_view_with_data(self):
        state = AgentState(task_input={})
        state.raw_policies = [1, 2, 3]
        state.clean_policies = [1, 2]
        state.summary = "测试摘要"
        s = state.summary_view()
        self.assertIn('raw=3', s)
        self.assertIn('clean=2', s)
        self.assertIn('summary=有', s)

    def test_default_status_running(self):
        state = AgentState(task_input={})
        self.assertEqual(state.status, 'running')
        self.assertEqual(state.step, 0)
        self.assertEqual(state.fail_count, 0)

    def test_last_actions_tracking(self):
        """last_actions 应记录 (tool, params, observation) 三元组。"""
        state = AgentState(task_input={})
        import json
        state.last_actions.append((
            'fetch_central',
            json.dumps({'date': '2026-07-13'}),
            '{"fetched": 3, "source": "central"}',
        ))
        self.assertEqual(len(state.last_actions), 1)
        # 三元组：tool / params / observation_preview
        self.assertEqual(state.last_actions[0][0], 'fetch_central')
        self.assertEqual(state.last_actions[0][2], '{"fetched": 3, "source": "central"}')

    def test_last_actions_observation_for_react(self):
        """observation preview 应能被 ReAct 循环读取，用于 LLM 决策反馈。"""
        state = AgentState(task_input={})
        import json
        # 模拟 core.py 回填后的三元组
        state.last_actions.append((
            'fetch_central',
            json.dumps({'date': '2026-07-13'}),
            json.dumps({"fetched": 5, "source": "central"}, ensure_ascii=False)[:150],
        ))
        # 重复检测只比前两元，observation 不影响重复判定
        recent_keys = [(a[0], a[1]) for a in state.last_actions[-3:]]
        self.assertEqual(len(recent_keys), 1)
        self.assertEqual(recent_keys[0], ('fetch_central', json.dumps({'date': '2026-07-13'})))


class AgentRunPersistenceTest(TestCase):
    """测试 AgentRun state 持久化（A2）。

    用 TestCase（需 DB），验证 save_state/get_state 跨"重启"（清空 _RUN_CACHE）恢复。
    """

    def test_state_persists_across_cache_clear(self):
        """save_state 后清空内存缓存，get_state 应能从 DB 恢复。"""
        from agent.core import save_state, get_state, _RUN_CACHE
        run_id = uuid_mod.uuid4()
        state = AgentState(task_input={'date': '2026-07-13'})
        state.raw_policies = [{'id': 1, 'title': '政策A'}]
        state.clean_policies = [{'id': 1, 'title': '政策A', 'source': 'central'}]
        state.step = 5
        state.status = 'running'
        state.fail_count = 1
        state.last_actions = [('fetch_central', '{"date": "2026-07-13"}', '{"fetched": 1}')]
        save_state(run_id, state)

        # 清空内存缓存，模拟服务重启 / 多 worker 切换
        _RUN_CACHE.clear()

        recovered = get_state(run_id)
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered.step, 5)
        self.assertEqual(recovered.status, 'running')
        self.assertEqual(len(recovered.raw_policies), 1)
        self.assertEqual(recovered.raw_policies[0]['title'], '政策A')
        self.assertEqual(len(recovered.clean_policies), 1)
        self.assertEqual(recovered.fail_count, 1)
        self.assertEqual(len(recovered.last_actions), 1)
        # 三元组 observation 应保留
        self.assertEqual(recovered.last_actions[0][2], '{"fetched": 1}')

    def test_status_transitions_persist(self):
        """状态转换 running → done 应正确持久化。"""
        from agent.core import save_state, get_state, _RUN_CACHE
        run_id = uuid_mod.uuid4()
        state = AgentState(task_input={'date': '2026-07-13'})
        state.status = 'running'
        state.step = 0
        save_state(run_id, state)

        # 模拟 run 完成
        state.status = 'done'
        state.step = 8
        state.summary = '• 测试摘要'
        save_state(run_id, state)

        _RUN_CACHE.clear()
        recovered = get_state(run_id)
        self.assertEqual(recovered.status, 'done')
        self.assertEqual(recovered.step, 8)
        self.assertEqual(recovered.summary, '• 测试摘要')

    def test_failed_status_persists(self):
        """failed 状态应持久化，error 字段非空。"""
        from agent.core import save_state, get_state, _RUN_CACHE
        from agent.models import AgentRun
        run_id = uuid_mod.uuid4()
        state = AgentState(task_input={'date': '2026-07-13'})
        state.status = 'failed'
        state.step = 3
        save_state(run_id, state)

        _RUN_CACHE.clear()
        recovered = get_state(run_id)
        self.assertEqual(recovered.status, 'failed')
        # AgentRun 表 error 字段应有值
        run = AgentRun.objects.get(run_id=str(run_id))
        self.assertIsNotNone(run.error)

    def test_get_state_returns_none_for_nonexistent(self):
        """不存在的 run_id 应返回 None。"""
        from agent.core import get_state, _RUN_CACHE
        _RUN_CACHE.clear()
        result = get_state(uuid_mod.uuid4())
        self.assertIsNone(result)

    def test_get_state_uses_cache_when_available(self):
        """内存缓存有 state 时应直接返回，不查 DB。"""
        from agent.core import get_state, _RUN_CACHE
        run_id = uuid_mod.uuid4()
        cached_state = AgentState(task_input={'date': '2026-07-13'})
        cached_state.step = 99  # 内存中的值，DB 里没有
        _RUN_CACHE[str(run_id)] = cached_state

        result = get_state(run_id)
        self.assertIs(result, cached_state)  # 同一对象引用
        self.assertEqual(result.step, 99)

    def test_context_hints_persist(self):
        """A3: context_hints 应能持久化到 DB 并恢复。"""
        from agent.core import save_state, get_state, _RUN_CACHE
        run_id = uuid_mod.uuid4()
        state = AgentState(task_input={'date': '2026-07-13'})
        state.context_hints = ['历史经验1: 工具序列 fetch→clean→summarize', '历史经验2: ...']
        state.step = 2
        save_state(run_id, state)

        _RUN_CACHE.clear()
        recovered = get_state(run_id)
        self.assertEqual(len(recovered.context_hints), 2)
        self.assertIn('历史经验1', recovered.context_hints[0])


class EpisodicMemoryTest(SimpleTestCase):
    """测试 A3 episodic memory 函数（用 mock 避免污染 ChromaDB 索引）。"""

    def test_store_episodic_memory_calls_upsert(self):
        """store_episodic_memory 应调 collection.upsert 存经验。"""
        from unittest.mock import patch, MagicMock
        from agent.rag import store_episodic_memory
        with patch('agent.rag._get_episodic_collection') as mock_get:
            mock_col = MagicMock()
            mock_get.return_value = mock_col
            result = store_episodic_memory(
                run_id='test-run-1',
                date='2026-07-13',
                summary='• 测试摘要',
                key_decisions=['fetch_central', 'clean_policy', 'summarize'],
            )
            self.assertTrue(result)
            mock_col.upsert.assert_called_once()
            # 验证文档内容含日期和摘要
            call_args = mock_col.upsert.call_args
            doc = call_args.kwargs['documents'][0]
            self.assertIn('2026-07-13', doc)
            self.assertIn('测试摘要', doc)
            self.assertIn('fetch_central', doc)

    def test_store_episodic_memory_skips_empty_summary(self):
        """summary 为空时应跳过存储。"""
        from unittest.mock import patch, MagicMock
        from agent.rag import store_episodic_memory
        with patch('agent.rag._get_episodic_collection') as mock_get:
            mock_col = MagicMock()
            mock_get.return_value = mock_col
            result = store_episodic_memory('run-1', '2026-07-13', '', ['tool1'])
            self.assertFalse(result)
            mock_col.upsert.assert_not_called()

    def test_retrieve_episodic_memory_returns_docs(self):
        """retrieve_episodic_memory 应返回命中文档列表。"""
        from unittest.mock import patch, MagicMock
        from agent.rag import retrieve_episodic_memory
        with patch('agent.rag._get_episodic_collection') as mock_get:
            mock_col = MagicMock()
            mock_col.count.return_value = 2
            mock_col.query.return_value = {
                'documents': [['历史经验A', '历史经验B']],
            }
            mock_get.return_value = mock_col
            results = retrieve_episodic_memory('财税政策日报 2026-07-13')
            self.assertEqual(len(results), 2)
            self.assertIn('历史经验A', results[0])

    def test_retrieve_episodic_memory_empty_index(self):
        """索引为空时应返回空列表，不报错。"""
        from unittest.mock import patch, MagicMock
        from agent.rag import retrieve_episodic_memory
        with patch('agent.rag._get_episodic_collection') as mock_get:
            mock_col = MagicMock()
            mock_col.count.return_value = 0
            mock_get.return_value = mock_col
            results = retrieve_episodic_memory('query')
            self.assertEqual(results, [])
            mock_col.query.assert_not_called()

    def test_retrieve_episodic_memory_empty_query(self):
        """空 query 应返回空列表。"""
        from agent.rag import retrieve_episodic_memory
        self.assertEqual(retrieve_episodic_memory(''), [])
        self.assertEqual(retrieve_episodic_memory('   '), [])

    def test_clear_episodic_memory_deletes_all(self):
        """clear_episodic_memory 应删除所有文档。"""
        from unittest.mock import patch, MagicMock
        from agent.rag import clear_episodic_memory
        with patch('agent.rag._get_episodic_collection') as mock_get:
            mock_col = MagicMock()
            mock_col.get.return_value = {'ids': ['ep_1', 'ep_2']}
            mock_get.return_value = mock_col
            count = clear_episodic_memory()
            self.assertEqual(count, 2)
            mock_col.delete.assert_called_once_with(ids=['ep_1', 'ep_2'])
