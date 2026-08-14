"""Agent prompts.py 测试。

覆盖：
- ACTUATOR_SYSTEM / CRITIC_SYSTEM 常量内容
- build_step_prompt：基本字段 / trace 渲染 / replan_hint / context_hints
- build_critic_prompt：状态 + 步数 + trace
"""
import json
from django.test import SimpleTestCase

from agent.prompts import (
    ACTUATOR_SYSTEM, CRITIC_SYSTEM,
    build_step_prompt, build_critic_prompt,
)
from agent.tools import AgentState


class ActuatorSystemTest(SimpleTestCase):
    """测试 ACTUATOR_SYSTEM 常量。"""

    def test_contains_tool_description(self):
        self.assertIn('可用工具', ACTUATOR_SYSTEM)

    def test_contains_json_format(self):
        self.assertIn('reasoning', ACTUATOR_SYSTEM)
        self.assertIn('tool', ACTUATOR_SYSTEM)
        self.assertIn('params', ACTUATOR_SYSTEM)
        self.assertIn('done', ACTUATOR_SYSTEM)

    def test_contains_decision_rules(self):
        self.assertIn('决策规则', ACTUATOR_SYSTEM)
        self.assertIn('format_docx', ACTUATOR_SYSTEM)


class CriticSystemTest(SimpleTestCase):
    """测试 CRITIC_SYSTEM 常量。"""

    def test_contains_checks(self):
        self.assertIn('原地打转', CRITIC_SYSTEM)
        self.assertIn('数据为空', CRITIC_SYSTEM)

    def test_contains_json_format(self):
        self.assertIn('needs_replan', CRITIC_SYSTEM)
        self.assertIn('replan_hint', CRITIC_SYSTEM)


class BuildStepPromptTest(SimpleTestCase):
    """测试 build_step_prompt。"""

    def test_contains_task_input(self):
        state = AgentState(task_input={'date': '2026-07-13'})
        prompt = build_step_prompt(state)
        self.assertIn('2026-07-13', prompt)
        self.assertIn('任务:', prompt)

    def test_contains_step_and_max_steps(self):
        state = AgentState(task_input={})
        state.step = 3
        prompt = build_step_prompt(state, max_steps=15)
        self.assertIn('3/15', prompt)

    def test_contains_state_summary(self):
        state = AgentState(task_input={})
        state.raw_policies = [1, 2, 3]
        prompt = build_step_prompt(state)
        self.assertIn('raw=3', prompt)

    def test_empty_trace_shows_placeholder(self):
        state = AgentState(task_input={})
        prompt = build_step_prompt(state)
        self.assertIn('无历史', prompt)

    def test_trace_rendered(self):
        state = AgentState(task_input={})
        state.trace = [
            {'step': 1, 'tool': 'fetch_central', 'input': {'date': '2026-07-13'}, 'output': {'fetched': 3}},
        ]
        prompt = build_step_prompt(state)
        self.assertIn('fetch_central', prompt)
        self.assertIn('2026-07-13', prompt)
        self.assertIn('step 1', prompt)

    def test_trace_params_preview_truncated(self):
        """params 超长应截断到 80 字。"""
        long_params = {'data': 'x' * 200}
        state = AgentState(task_input={})
        state.trace = [{'step': 1, 'tool': 't', 'input': long_params, 'output': {}}]
        prompt = build_step_prompt(state)
        # 应截断，不会出现完整的 200 个 x
        self.assertNotIn('x' * 200, prompt)

    def test_empty_params_not_shown(self):
        """params 为空时不显示 ()。"""
        state = AgentState(task_input={})
        state.trace = [{'step': 1, 'tool': 'fetch_central', 'input': {}, 'output': {'ok': True}}]
        prompt = build_step_prompt(state)
        self.assertIn('fetch_central', prompt)
        # 空参数应显示为 "fetch_central" 而非 "fetch_central()"
        self.assertNotIn('fetch_central()', prompt)

    def test_replan_hint_injected(self):
        state = AgentState(task_input={})
        prompt = build_step_prompt(state, replan_hint='换用 fetch_local')
        self.assertIn('Critic 反馈', prompt)
        self.assertIn('换用 fetch_local', prompt)

    def test_no_replan_hint_section_when_none(self):
        state = AgentState(task_input={})
        prompt = build_step_prompt(state, replan_hint=None)
        self.assertNotIn('Critic 反馈', prompt)

    def test_context_hints_injected(self):
        """A3: context_hints 非空时应注入历史经验段落。"""
        state = AgentState(task_input={})
        state.context_hints = ['历史经验1: fetch→clean→summarize']
        prompt = build_step_prompt(state)
        self.assertIn('历史 run 经验参考', prompt)
        self.assertIn('历史经验1', prompt)

    def test_context_hints_truncated_to_200_chars(self):
        """context_hints 每条截断到 200 字。"""
        long_hint = 'a' * 300
        state = AgentState(task_input={})
        state.context_hints = [long_hint]
        prompt = build_step_prompt(state)
        self.assertNotIn('a' * 300, prompt)

    def test_context_hints_max_3_items(self):
        """context_hints 最多显示 3 条。"""
        state = AgentState(task_input={})
        state.context_hints = ['hint1', 'hint2', 'hint3', 'hint4', 'hint5']
        prompt = build_step_prompt(state)
        self.assertIn('hint1', prompt)
        self.assertIn('hint3', prompt)
        self.assertNotIn('hint4', prompt)

    def test_no_context_hints_section_when_empty(self):
        state = AgentState(task_input={})
        state.context_hints = []
        prompt = build_step_prompt(state)
        self.assertNotIn('历史 run 经验参考', prompt)

    def test_only_last_5_traces_shown(self):
        """trace 只显示最近 5 步。"""
        state = AgentState(task_input={})
        state.trace = [
            {'step': i, 'tool': f'tool_{i}', 'input': {}, 'output': {}} for i in range(1, 11)
        ]
        prompt = build_step_prompt(state)
        self.assertIn('tool_6', prompt)
        self.assertIn('tool_10', prompt)
        # tool_1/2/3/4/5 应被排除（注意 tool_10 含子串 tool_1，用 step 上下文判断）
        self.assertNotIn('step 1:', prompt)
        self.assertNotIn('step 5:', prompt)
        self.assertIn('step 6:', prompt)


class BuildCriticPromptTest(SimpleTestCase):
    """测试 build_critic_prompt。"""

    def test_contains_state_summary(self):
        state = AgentState(task_input={})
        state.raw_policies = [1, 2]
        prompt = build_critic_prompt(state)
        self.assertIn('raw=2', prompt)
        self.assertIn('状态:', prompt)

    def test_contains_step(self):
        state = AgentState(task_input={})
        state.step = 7
        prompt = build_critic_prompt(state)
        self.assertIn('7', prompt)
        self.assertIn('步数:', prompt)

    def test_empty_trace_shows_placeholder(self):
        state = AgentState(task_input={})
        prompt = build_critic_prompt(state)
        self.assertIn('无历史', prompt)

    def test_trace_rendered(self):
        state = AgentState(task_input={})
        state.trace = [
            {'step': 1, 'tool': 'fetch_central', 'output': {'fetched': 3}},
        ]
        prompt = build_critic_prompt(state)
        self.assertIn('fetch_central', prompt)
        self.assertIn('step 1', prompt)

    def test_only_last_6_traces_shown(self):
        """Critic trace 只显示最近 6 步。"""
        state = AgentState(task_input={})
        state.trace = [
            {'step': i, 'tool': f'tool_{i}', 'output': {}} for i in range(1, 11)
        ]
        prompt = build_critic_prompt(state)
        self.assertIn('tool_5', prompt)
        self.assertIn('tool_10', prompt)
        # 用 step 上下文判断，避免 tool_10 含 tool_1 子串误判
        self.assertNotIn('step 1:', prompt)
        self.assertNotIn('step 4:', prompt)
        self.assertIn('step 5:', prompt)
