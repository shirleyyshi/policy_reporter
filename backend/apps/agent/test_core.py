"""Agent core.py 单元测试。

覆盖：
- Terminator 硬性终止逻辑（max_steps / done / 未知工具 / fail_threshold）
- 重复检测触发 Critic
- 停滞检测触发 Critic
- Critic replan_hint 注入
- _run_loop 集成（mock LLM + 工具）
- save_state / get_state / submit_answer
- docx 持久化到文件系统

所有 LLM 调用（_call_actuator / _call_critic）通过 mock 注入预设决策，
不依赖真实 DeepSeek API。
"""
import uuid
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone

from agent.tools import AgentState, fetch_central, fetch_local
from agent.core import (
    _run_loop, save_state, get_state, submit_answer,
    _serialize_state, _RUN_CACHE, MAX_STEPS,
)
from report.models import CentralPolicy, LocalPolicy


def _make_state(**kwargs):
    """构造测试用 AgentState。"""
    state = AgentState(task_input=kwargs.pop('task_input', {'date': '2026-07-13'}))
    for k, v in kwargs.items():
        setattr(state, k, v)
    return state


class TerminatorTest(TestCase):
    """测试 Terminator 硬性终止逻辑。"""

    def _run_with_decisions(self, decisions, config=None):
        """用预设 decisions 列表跑 _run_loop，mock LLM。"""
        run_id = uuid.uuid4()
        state = _make_state()
        _RUN_CACHE[str(run_id)] = state
        save_state(run_id, state)

        call_iter = iter(decisions)
        with patch('agent.core._call_actuator', side_effect=lambda *a, **k: next(call_iter)), \
             patch('agent.core._call_critic', return_value={'needs_replan': False, 'replan_hint': ''}):
            _run_loop(run_id, state, config)
        return run_id, state

    def test_done_terminates(self):
        """Actuator 输出 done=True 时应立即终止。"""
        decisions = [
            {'reasoning': '完成', 'tool': 'finish', 'params': {}, 'done': True},
        ]
        run_id, state = self._run_with_decisions(decisions)
        self.assertEqual(state.status, 'done')
        self.assertEqual(state.step, 1)

    def test_max_steps_terminates_as_failed(self):
        """达到 max_steps 应终止为 failed。"""
        # 用极小 max_steps，Actuator 永远不 done
        decisions = [
            {'reasoning': f'step {i}', 'tool': 'save_to_db', 'params': {}, 'done': False}
            for i in range(5)
        ]
        run_id, state = self._run_with_decisions(decisions, config={'max_steps': 3})
        self.assertEqual(state.status, 'failed')
        self.assertEqual(state.step, 3)

    def test_unknown_tool_increments_fail_count(self):
        """未知工具应增加 fail_count，达阈值 failed。"""
        decisions = [
            {'reasoning': 'bad', 'tool': 'nonexistent_tool', 'params': {}, 'done': False},
            {'reasoning': 'bad', 'tool': 'nonexistent_tool', 'params': {}, 'done': False},
            {'reasoning': 'bad', 'tool': 'nonexistent_tool', 'params': {}, 'done': False},
        ]
        run_id, state = self._run_with_decisions(decisions, config={'fail_threshold': 3})
        self.assertEqual(state.status, 'failed')
        self.assertEqual(state.fail_count, 3)

    def test_actuator_exception_increments_fail_count(self):
        """Actuator LLM 异常应增加 fail_count。"""
        run_id = uuid.uuid4()
        state = _make_state()
        _RUN_CACHE[str(run_id)] = state
        save_state(run_id, state)

        with patch('agent.core._call_actuator', side_effect=Exception("API down")), \
             patch('agent.core._call_critic', return_value={'needs_replan': False}):
            _run_loop(run_id, state, config={'fail_threshold': 2})
        self.assertEqual(state.status, 'failed')
        self.assertEqual(state.fail_count, 2)


class RepeatDetectionTest(TestCase):
    """测试重复检测触发 Critic。"""

    def test_repeated_actions_trigger_critic(self):
        """连续3次相同 tool+params 应触发 Critic。"""
        run_id = uuid.uuid4()
        state = _make_state()
        _RUN_CACHE[str(run_id)] = state
        save_state(run_id, state)

        decisions = [
            {'reasoning': 'r', 'tool': 'save_to_db', 'params': {}, 'done': False},
            {'reasoning': 'r', 'tool': 'save_to_db', 'params': {}, 'done': False},
            {'reasoning': 'r', 'tool': 'save_to_db', 'params': {}, 'done': False},
            {'reasoning': 'done', 'tool': 'finish', 'params': {}, 'done': True},
        ]
        critic_calls = []

        def mock_critic(state):
            critic_calls.append(state)
            return {'needs_replan': True, 'replan_hint': '换工具'}

        call_iter = iter(decisions)
        with patch('agent.core._call_actuator', side_effect=lambda *a, **k: next(call_iter)), \
             patch('agent.core._call_critic', side_effect=mock_critic):
            _run_loop(run_id, state, config={'repeat_threshold': 3, 'critic_every_n': 999})

        # Critic 应被调用至少1次（重复触发）
        self.assertGreaterEqual(len(critic_calls), 1)
        # 重复后 last_actions 应被清空
        self.assertEqual(len(state.last_actions), 0)


class StallDetectionTest(TestCase):
    """测试停滞检测触发 Critic。"""

    def test_stall_triggers_critic(self):
        """连续5步 state 无变化应触发 Critic。"""
        run_id = uuid.uuid4()
        state = _make_state()
        _RUN_CACHE[str(run_id)] = state
        save_state(run_id, state)

        # save_to_db 是 stub，不会改变 state.summary_view，模拟停滞
        decisions = [
            {'reasoning': 'r', 'tool': 'save_to_db', 'params': {}, 'done': False}
            for _ in range(6)
        ] + [{'reasoning': 'done', 'tool': 'finish', 'params': {}, 'done': True}]

        critic_calls = []
        with patch('agent.core._call_actuator', side_effect=lambda *a, **k: next(iter(decisions))), \
             patch('agent.core._call_critic', side_effect=lambda s: (critic_calls.append(s), {'needs_replan': False, 'replan_hint': ''})[1]):
            _run_loop(run_id, state, config={'stall_steps': 5, 'critic_every_n': 999})

        self.assertGreaterEqual(len(critic_calls), 1)

    def test_stall_detection_disabled(self):
        """stall_detection_enabled=False 时不触发停滞 Critic。"""
        run_id = uuid.uuid4()
        state = _make_state()
        _RUN_CACHE[str(run_id)] = state
        save_state(run_id, state)

        # 用不同 params 避免触发重复检测（重复检测也会调 Critic）
        decisions = [
            {'reasoning': 'r', 'tool': 'save_to_db', 'params': {'i': i}, 'done': False}
            for i in range(4)
        ] + [{'reasoning': 'done', 'tool': 'finish', 'params': {}, 'done': True}]

        critic_calls = []
        with patch('agent.core._call_actuator', side_effect=lambda *a, **k: next(iter(decisions))), \
             patch('agent.core._call_critic', side_effect=lambda s: (critic_calls.append(s), {'needs_replan': False})[1]):
            _run_loop(run_id, state, config={'stall_steps': 5, 'critic_every_n': 999, 'stall_detection_enabled': False, 'repeat_threshold': 999})

        self.assertEqual(len(critic_calls), 0)


class CriticReplanTest(TestCase):
    """测试 Critic replan_hint 注入。"""

    def test_critic_replan_hint_injected(self):
        """Critic 返回 needs_replan=True 时应注入 replan_hint。"""
        run_id = uuid.uuid4()
        state = _make_state()
        _RUN_CACHE[str(run_id)] = state
        save_state(run_id, state)

        decisions = [
            {'reasoning': 'r', 'tool': 'save_to_db', 'params': {}, 'done': False},
            {'reasoning': 'r', 'tool': 'save_to_db', 'params': {}, 'done': False},
            {'reasoning': 'r', 'tool': 'save_to_db', 'params': {}, 'done': False},  # 第3步触发 Critic
            {'reasoning': 'done', 'tool': 'finish', 'params': {}, 'done': True},
        ]
        replan_hints_received = []

        def mock_actuator(state, replan_hint=None):
            if replan_hint:
                replan_hints_received.append(replan_hint)
            return next(iter(decisions))

        with patch('agent.core._call_actuator', side_effect=mock_actuator), \
             patch('agent.core._call_critic', return_value={'needs_replan': True, 'replan_hint': '试试 summarize'}):
            _run_loop(run_id, state, config={'critic_every_n': 3})

        self.assertGreater(len(replan_hints_received), 0)
        self.assertIn('试试 summarize', replan_hints_received[0])

    def test_replanner_disabled_no_hint(self):
        """replanner_enabled=False 时不注入 replan_hint。"""
        run_id = uuid.uuid4()
        state = _make_state()
        _RUN_CACHE[str(run_id)] = state
        save_state(run_id, state)

        decisions = [
            {'reasoning': 'r', 'tool': 'save_to_db', 'params': {}, 'done': False},
            {'reasoning': 'r', 'tool': 'save_to_db', 'params': {}, 'done': False},
            {'reasoning': 'r', 'tool': 'save_to_db', 'params': {}, 'done': False},
            {'reasoning': 'done', 'tool': 'finish', 'params': {}, 'done': True},
        ]
        hints = []

        def mock_actuator(state, replan_hint=None):
            if replan_hint:
                hints.append(replan_hint)
            return next(iter(decisions))

        with patch('agent.core._call_actuator', side_effect=mock_actuator), \
             patch('agent.core._call_critic', return_value={'needs_replan': True, 'replan_hint': '应注入但被禁'}):
            _run_loop(run_id, state, config={'critic_every_n': 3, 'replanner_enabled': False})

        self.assertEqual(len(hints), 0)


class RunLoopIntegrationTest(TestCase):
    """_run_loop 集成测试：mock 工具 + LLM，验证完整流程。"""

    def test_tool_execution_records_trace(self):
        """工具执行成功应记录 trace 到 DB。"""
        run_id = uuid.uuid4()
        state = _make_state()
        _RUN_CACHE[str(run_id)] = state
        save_state(run_id, state)

        decisions = [
            {'reasoning': 'fetch', 'tool': 'save_to_db', 'params': {}, 'done': False},
            {'reasoning': 'done', 'tool': 'finish', 'params': {}, 'done': True},
        ]

        from agent.models import AgentTrace
        with patch('agent.core._call_actuator', side_effect=lambda *a, **k: next(iter(decisions))), \
             patch('agent.core._call_critic', return_value={'needs_replan': False}):
            _run_loop(run_id, state)

        traces = AgentTrace.objects.filter(run_id=run_id)
        self.assertGreaterEqual(traces.count(), 2)
        # 应有 actuate 和 terminate
        actions = [t.action for t in traces]
        self.assertIn('actuate', actions)
        self.assertIn('terminate', actions)

    def test_tool_exception_increments_fail_count(self):
        """工具执行抛异常应增加 fail_count。"""
        run_id = uuid.uuid4()
        state = _make_state()
        _RUN_CACHE[str(run_id)] = state
        save_state(run_id, state)

        decisions = [
            {'reasoning': 'r', 'tool': 'fetch_central', 'params': {'i': 1}, 'done': False},
            {'reasoning': 'r', 'tool': 'fetch_central', 'params': {'i': 2}, 'done': False},
            {'reasoning': 'done', 'tool': 'finish', 'params': {}, 'done': True},
        ]

        # patch core.py 里已导入的 TOOLS 引用
        mock_tools = {'fetch_central': MagicMock(side_effect=Exception("DB down"))}
        with patch('agent.core._call_actuator', side_effect=lambda *a, **k: next(iter(decisions))), \
             patch('agent.core._call_critic', return_value={'needs_replan': False}), \
             patch('agent.core.TOOLS', mock_tools):
            _run_loop(run_id, state, config={'fail_threshold': 3, 'repeat_threshold': 999})

        self.assertGreaterEqual(state.fail_count, 1)

    def test_docx_persisted_to_filesystem(self):
        """run 结束时若有 docx_bytes 应持久化到文件系统。"""
        run_id = uuid.uuid4()
        state = _make_state()
        state.docx_bytes = b'fake docx content'
        _RUN_CACHE[str(run_id)] = state
        save_state(run_id, state)

        decisions = [{'reasoning': 'done', 'tool': 'finish', 'params': {}, 'done': True}]

        from agent.core import _DOCX_DIR
        with patch('agent.core._call_actuator', side_effect=lambda *a, **k: next(iter(decisions))), \
             patch('agent.core._call_critic', return_value={'needs_replan': False}):
            _run_loop(run_id, state)

        docx_path = _DOCX_DIR / f"{run_id}.docx"
        self.assertTrue(docx_path.exists())
        self.assertEqual(docx_path.read_bytes(), b'fake docx content')
        # 清理
        docx_path.unlink(missing_ok=True)


class SerializeStateTest(TestCase):
    """测试 _serialize_state 排除不可序列化字段。"""

    def test_excludes_callable_and_trace(self):
        """序列化应排除 human_input_callback、trace、docx_bytes。"""
        state = _make_state()
        state.human_input_callback = lambda q, o: o[0]
        state.trace = [{'step': 1}]
        state.docx_bytes = b'fake'
        state.raw_policies = [1, 2]
        state.summary = 'test'

        data = _serialize_state(state)
        self.assertNotIn('human_input_callback', data)
        self.assertNotIn('trace', data)
        self.assertNotIn('docx_bytes', data)
        self.assertNotIn('pending_question', data)
        self.assertEqual(data['raw_policies'], [1, 2])
        self.assertEqual(data['summary'], 'test')

    def test_includes_context_hints(self):
        """context_hints 应在序列化数据中。"""
        state = _make_state()
        state.context_hints = ['hint1', 'hint2']
        data = _serialize_state(state)
        self.assertEqual(data['context_hints'], ['hint1', 'hint2'])


class SubmitAnswerTest(TestCase):
    """测试人在回路 submit_answer。"""

    def test_submit_answer_returns_false_for_no_waiter(self):
        """没有等待中的 run 应返回 False。"""
        result = submit_answer(uuid.uuid4(), "answer")
        self.assertFalse(result)

    def test_submit_answer_wakes_waiter(self):
        """submit_answer 应唤醒等待的 Agent 线程。"""
        run_id = uuid.uuid4()
        from agent.core import _WAIT_EVENTS, _HUMAN_ANSWERS
        import threading
        event = threading.Event()
        _WAIT_EVENTS[str(run_id)] = event

        result = submit_answer(run_id, "用户回答")
        self.assertTrue(result)
        self.assertEqual(_HUMAN_ANSWERS.get(str(run_id)), "用户回答")
        self.assertTrue(event.is_set())

        # 清理
        _WAIT_EVENTS.pop(str(run_id), None)
        _HUMAN_ANSWERS.pop(str(run_id), None)


def _make_dt(year, month, day, hour=10, minute=0):
    """构造 timezone-aware datetime（避免 naive datetime 警告）。"""
    return timezone.make_aware(datetime(year, month, day, hour, minute))


class FetchToolsTest(TestCase):
    """测试 fetch_central / fetch_local 工具的 DB 查询逻辑（PROJECT_AUDIT #23）。"""

    def test_fetch_central_by_date(self):
        """fetch_central 应按 date 过滤，只返回匹配日期的政策。"""
        CentralPolicy.objects.create(
            title="匹配政策", content="c1", type="通知",
            publish_time=_make_dt(2026, 7, 13),
            source_url="http://c/1",
        )
        CentralPolicy.objects.create(
            title="不匹配", content="c2", type="通知",
            publish_time=_make_dt(2026, 7, 14),
            source_url="http://c/2",
        )
        state = _make_state()
        result = fetch_central(state, {"date": "2026-07-13"})

        self.assertEqual(result["fetched"], 1)
        self.assertEqual(result["source"], "central")
        self.assertEqual(len(state.raw_policies), 1)
        self.assertEqual(state.raw_policies[0]["title"], "匹配政策")
        self.assertEqual(state.raw_policies[0]["source"], "central")

    def test_fetch_central_no_date_returns_all(self):
        """不传 date 时应返回全部中央政策。"""
        CentralPolicy.objects.create(
            title="a", content="", type="通知",
            publish_time=_make_dt(2026, 7, 1), source_url="http://x/1",
        )
        CentralPolicy.objects.create(
            title="b", content="", type="公告",
            publish_time=_make_dt(2026, 7, 2), source_url="http://x/2",
        )
        state = _make_state(task_input={})  # 无 date
        result = fetch_central(state, {})

        self.assertEqual(result["fetched"], 2)
        self.assertEqual(len(state.raw_policies), 2)

    def test_fetch_central_uses_task_input_date(self):
        """params 无 date 时应回退到 state.task_input['date']。"""
        CentralPolicy.objects.create(
            title="t", content="", type="通知",
            publish_time=_make_dt(2026, 7, 13), source_url="http://x",
        )
        state = _make_state(task_input={"date": "2026-07-13"})
        result = fetch_central(state, {})

        self.assertEqual(result["fetched"], 1)
        self.assertEqual(result["date"], "2026-07-13")

    def test_fetch_local_by_date(self):
        """fetch_local 应按 date 过滤地方政策，并标记 source='local'。"""
        LocalPolicy.objects.create(
            title="沪政策", content="c", province="上海",
            publish_time=_make_dt(2026, 7, 13),
            source_url="http://sh/1",
        )
        LocalPolicy.objects.create(
            title="其他天", content="c", province="上海",
            publish_time=_make_dt(2026, 7, 14),
            source_url="http://sh/2",
        )
        state = _make_state()
        result = fetch_local(state, {"date": "2026-07-13"})

        self.assertEqual(result["fetched"], 1)
        self.assertEqual(result["source"], "local")
        self.assertEqual(state.raw_policies[0]["province"], "上海")
        self.assertEqual(state.raw_policies[0]["type"], "")  # 模型 default=""
        self.assertEqual(state.raw_policies[0]["source"], "local")

    def test_fetch_extends_not_replaces_raw_policies(self):
        """多次 fetch 应扩展 raw_policies，而非覆盖。"""
        CentralPolicy.objects.create(
            title="c1", content="", type="通知",
            publish_time=_make_dt(2026, 7, 13), source_url="http://c/1",
        )
        LocalPolicy.objects.create(
            title="l1", content="", province="上海",
            publish_time=_make_dt(2026, 7, 13), source_url="http://l/1",
        )
        state = _make_state()
        fetch_central(state, {"date": "2026-07-13"})
        fetch_local(state, {"date": "2026-07-13"})

        self.assertEqual(len(state.raw_policies), 2)

    def test_fetch_empty_db_returns_zero(self):
        """空数据库应返回 fetched=0，不抛异常。"""
        state = _make_state()
        result = fetch_central(state, {"date": "2026-07-13"})
        self.assertEqual(result["fetched"], 0)
        self.assertEqual(state.raw_policies, [])
