"""Agent eval 模块单元测试。

覆盖：
- metrics.py：确定性指标 + LLM-as-judge + get_summary + collect_run_metrics
- runner.py：EvalRunner.run_single / _aggregate / run_ablation
- reporter.py：to_json / to_markdown / to_ablation_markdown / save_report
- testset.py：discover_test_cases / _count_policies / _has_duplicate_titles

所有 LLM 调用通过 mock，不依赖真实 DeepSeek API。
"""
import json
import uuid
from unittest.mock import patch, MagicMock

from django.test import TestCase

from agent.models import AgentTrace, AgentRun
from agent.tools import AgentState
from agent.core import _RUN_CACHE, save_state


def _seed_traces(run_id, traces_spec):
    """批量创建 AgentTrace 记录。
    traces_spec: list of dict {step, action, tool, input, output, reasoning}
    """
    for spec in traces_spec:
        AgentTrace.objects.create(
            run_id=run_id,
            step=spec.get('step', 1),
            action=spec.get('action', 'actuate'),
            tool=spec.get('tool'),
            input=spec.get('input'),
            output=spec.get('output'),
            reasoning=spec.get('reasoning'),
        )


# ==================== metrics.py ====================

class MetricsDeterministicTest(TestCase):
    """测试确定性指标（从 DB trace 统计）。"""

    def setUp(self):
        self.run_id = uuid.uuid4()
        _seed_traces(self.run_id, [
            {'step': 1, 'action': 'actuate', 'tool': 'fetch_central', 'output': {'fetched': 3}},
            {'step': 2, 'action': 'actuate', 'tool': 'clean_policy', 'output': {'cleaned': 3}},
            {'step': 3, 'action': 'critique', 'output': {'needs_replan': True, 'replan_hint': 'x'}},
            {'step': 4, 'action': 'actuate', 'tool': 'summarize', 'output': {'summary_preview': 'test'}},
            {'step': 4, 'action': 'actuate', 'tool': 'ask_human', 'output': {'question': 'q'}},
            {'step': 4, 'action': 'actuate', 'tool': 'fetch_central', 'output': {'error': 'timeout'}},
            {'step': 5, 'action': 'terminate', 'output': {'status': 'done'}},
        ])

    def test_step_count(self):
        from agent.eval.metrics import step_count
        self.assertEqual(step_count(self.run_id), 5)

    def test_tool_call_distribution(self):
        from agent.eval.metrics import tool_call_distribution
        dist = tool_call_distribution(self.run_id)
        # fetch_central 第一次成功，第二次有 error 被排除
        self.assertEqual(dist.get('fetch_central', 0), 1)
        self.assertEqual(dist.get('clean_policy', 0), 1)
        self.assertEqual(dist.get('summarize', 0), 1)
        self.assertEqual(dist.get('ask_human', 0), 1)

    def test_critic_count(self):
        from agent.eval.metrics import critic_count
        self.assertEqual(critic_count(self.run_id), 1)

    def test_critic_replan_rate(self):
        from agent.eval.metrics import critic_replan_rate
        self.assertEqual(critic_replan_rate(self.run_id), 1.0)

    def test_critic_replan_rate_none_when_no_critic(self):
        """没有 Critic 触发时返回 None。"""
        run_id = uuid.uuid4()
        _seed_traces(run_id, [{'step': 1, 'action': 'actuate', 'tool': 'fetch_central'}])
        from agent.eval.metrics import critic_replan_rate
        self.assertIsNone(critic_replan_rate(run_id))

    def test_error_count(self):
        from agent.eval.metrics import error_count
        self.assertEqual(error_count(self.run_id), 1)

    def test_ask_human_count(self):
        from agent.eval.metrics import ask_human_count
        self.assertEqual(ask_human_count(self.run_id), 1)

    def test_status_done(self):
        from agent.eval.metrics import status
        self.assertEqual(status(self.run_id), 'done')

    def test_status_incomplete(self):
        """无 terminate trace 时返回 incomplete。"""
        run_id = uuid.uuid4()
        _seed_traces(run_id, [{'step': 1, 'action': 'actuate', 'tool': 'fetch_central'}])
        from agent.eval.metrics import status
        self.assertEqual(status(run_id), 'incomplete')

    def test_status_unknown_when_no_traces(self):
        from agent.eval.metrics import status
        self.assertEqual(status(uuid.uuid4()), 'unknown')


class MetricsSuccessTest(TestCase):
    """测试 success / has_docx。"""

    def test_success_with_done_and_docx_in_cache(self):
        """state.status=done 且有 docx_bytes 时 success=True。"""
        run_id = uuid.uuid4()
        state = AgentState(task_input={'date': '2026-07-13'})
        state.status = 'done'
        state.docx_bytes = b'fake'
        _RUN_CACHE[str(run_id)] = state

        from agent.eval.metrics import success
        self.assertTrue(success(run_id))

    def test_success_false_for_failed(self):
        run_id = uuid.uuid4()
        state = AgentState(task_input={})
        state.status = 'failed'
        _RUN_CACHE[str(run_id)] = state

        from agent.eval.metrics import success
        self.assertFalse(success(run_id))

    def test_success_from_trace_when_cache_miss(self):
        """cache 丢失时从 DB trace 推断。"""
        run_id = uuid.uuid4()
        _seed_traces(run_id, [
            {'step': 1, 'action': 'actuate', 'tool': 'format_docx', 'output': {'ok': True}},
            {'step': 2, 'action': 'terminate', 'output': {'status': 'done'}},
        ])
        from agent.eval.metrics import success
        self.assertTrue(success(run_id))

    def test_has_docx_from_cache(self):
        run_id = uuid.uuid4()
        state = AgentState(task_input={})
        state.docx_bytes = b'x'
        _RUN_CACHE[str(run_id)] = state
        from agent.eval.metrics import has_docx
        self.assertTrue(has_docx(run_id))

    def test_has_docx_false_when_nothing(self):
        from agent.eval.metrics import has_docx
        self.assertFalse(has_docx(uuid.uuid4()))


class GetSummaryTest(TestCase):
    """测试 get_summary 三级回退。"""

    def test_from_state(self):
        """优先从内存 state.summary 取。"""
        run_id = uuid.uuid4()
        state = AgentState(task_input={})
        state.summary = '• 摘要内容'
        _RUN_CACHE[str(run_id)] = state
        from agent.eval.metrics import get_summary
        self.assertEqual(get_summary(run_id), '• 摘要内容')

    def test_from_trace_when_no_state(self):
        """无 state 时从 summarize trace 取 preview。"""
        run_id = uuid.uuid4()
        _seed_traces(run_id, [
            {'step': 1, 'action': 'actuate', 'tool': 'summarize', 'output': {'summary_preview': '前80字预览'}},
        ])
        from agent.eval.metrics import get_summary
        result = get_summary(run_id)
        self.assertIn('前80字预览', result)
        self.assertIn('截断', result)

    def test_empty_when_nothing(self):
        """无 state、无 trace、无 docx 时返回空串。"""
        from agent.eval.metrics import get_summary
        self.assertEqual(get_summary(uuid.uuid4()), '')

    def test_extract_summary_from_docx(self):
        """从 docx bytes 提取圆点段落。"""
        from agent.eval.metrics import _extract_summary_from_docx
        # mock python-docx Document
        mock_para1 = MagicMock()
        mock_para1.text = '• 第一条摘要'
        mock_para2 = MagicMock()
        mock_para2.text = '正文段落'
        mock_para3 = MagicMock()
        mock_para3.text = '• 第二条摘要'

        with patch('docx.Document') as mock_doc:
            mock_doc.return_value.paragraphs = [mock_para1, mock_para2, mock_para3]
            result = _extract_summary_from_docx(b'fake')
            self.assertIn('第一条摘要', result)
            self.assertIn('第二条摘要', result)
            self.assertNotIn('正文段落', result)


class LlmJudgeScoreTest(TestCase):
    """测试 LLM-as-judge。"""

    def test_empty_summary_returns_low_scores(self):
        """空摘要应返回全1分。"""
        from agent.eval.metrics import llm_judge_score
        result = llm_judge_score('')
        self.assertEqual(result['overall_score'], 1)
        self.assertEqual(result['format_score'], 1)

    def test_whitespace_only_summary(self):
        from agent.eval.metrics import llm_judge_score
        result = llm_judge_score('   ')
        self.assertEqual(result['overall_score'], 1)

    def test_judge_calls_api(self):
        """非空摘要应调 LLM API。"""
        from agent.eval.metrics import llm_judge_score
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            'format_score': 4, 'coverage_score': 5, 'language_score': 4,
            'overall_score': 4, 'reasoning': 'good'
        })

        with patch('agent.eval.metrics._get_judge_client') as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_response
            result = llm_judge_score('• 测试摘要内容')

        self.assertEqual(result['overall_score'], 4)
        self.assertEqual(result['coverage_score'], 5)

    def test_judge_handles_api_error(self):
        """API 异常时返回 None。"""
        from agent.eval.metrics import llm_judge_score
        with patch('agent.eval.metrics._get_judge_client') as mock_client:
            mock_client.return_value.chat.completions.create.side_effect = Exception("API down")
            result = llm_judge_score('• 摘要')
        self.assertIsNone(result)

    def test_judge_handles_invalid_json(self):
        """LLM 返回非 JSON 时尝试正则提取，仍失败返回 None。"""
        from agent.eval.metrics import llm_judge_score
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '这不是JSON'

        with patch('agent.eval.metrics._get_judge_client') as mock_client:
            mock_client.return_value.chat.completions.create.return_value = mock_response
            result = llm_judge_score('• 摘要')
        self.assertIsNone(result)


class CollectRunMetricsTest(TestCase):
    """测试 collect_run_metrics 聚合。"""

    def test_collects_all_metrics(self):
        run_id = uuid.uuid4()
        state = AgentState(task_input={})
        state.status = 'done'
        state.summary = '• 摘要'
        state.docx_bytes = b'x'
        _RUN_CACHE[str(run_id)] = state
        _seed_traces(run_id, [
            {'step': 1, 'action': 'actuate', 'tool': 'fetch_central', 'output': {'fetched': 1}},
            {'step': 2, 'action': 'terminate', 'output': {'status': 'done'}},
        ])

        from agent.eval.metrics import collect_run_metrics
        with patch('agent.eval.metrics.llm_judge_score', return_value={'overall_score': 4}):
            metrics = collect_run_metrics(run_id)

        self.assertEqual(metrics['status'], 'done')
        self.assertTrue(metrics['success'])
        self.assertEqual(metrics['step_count'], 2)
        self.assertEqual(metrics['summary_length'], len('• 摘要'))
        self.assertEqual(metrics['llm_judge']['overall_score'], 4)
        self.assertIn('fetch_central', metrics['tool_calls'])


# ==================== runner.py ====================

class EvalRunnerTest(TestCase):
    """测试 EvalRunner。"""

    def test_run_single_success(self):
        """run_single 成功时应返回 metrics。"""
        from agent.eval.runner import EvalRunner
        from agent.eval.testset import TestCase

        case = TestCase("test_1", "2026-07-13", "", "sparse", "测试")

        mock_state = AgentState(task_input={})
        mock_state.status = 'done'
        mock_state.summary = '• 摘要'
        mock_state.docx_bytes = b'x'

        mock_metrics = {'status': 'done', 'success': True, 'step_count': 3}

        with patch('agent.eval.runner.run_agent', return_value=(uuid.uuid4(), mock_state)), \
             patch('agent.eval.runner.collect_run_metrics', return_value=mock_metrics):
            runner = EvalRunner(test_cases=[case])
            result = runner.run_single(case)

        self.assertEqual(result['case_id'], 'test_1')
        self.assertIsNone(result['error'])
        self.assertEqual(result['metrics']['step_count'], 3)
        self.assertEqual(result['config_name'], 'baseline')

    def test_run_single_handles_exception(self):
        """run_agent 抛异常时 error 字段应有值。"""
        from agent.eval.runner import EvalRunner
        from agent.eval.testset import TestCase

        case = TestCase("test_err", "2026-07-13", "", "sparse", "测试")

        with patch('agent.eval.runner.run_agent', side_effect=Exception("boom")):
            runner = EvalRunner(test_cases=[case])
            result = runner.run_single(case)

        self.assertIsNotNone(result['error'])
        self.assertIn('boom', result['error'])
        self.assertIsNone(result['metrics'])

    def test_aggregate_calculates_success_rate(self):
        """_aggregate 应正确计算成功率。"""
        from agent.eval.runner import EvalRunner

        runner = EvalRunner(test_cases=[])
        results = [
            {'metrics': {'success': True, 'step_count': 3, 'critic_count': 1,
                         'critic_replan_rate': 0.5, 'error_count': 0,
                         'status': 'done', 'tool_calls': {'fetch_central': 1},
                         'llm_judge': {'overall_score': 4}},
             'error': None, 'duration_sec': 10.0},
            {'metrics': {'success': False, 'step_count': 5, 'critic_count': 2,
                         'critic_replan_rate': None, 'error_count': 1,
                         'status': 'failed', 'tool_calls': {},
                         'llm_judge': None},
             'error': None, 'duration_sec': 20.0},
        ]
        agg = runner._aggregate(results, 'baseline', 30.0)

        self.assertEqual(agg['valid_cases'], 2)
        self.assertEqual(agg['success_count'], 1)
        self.assertEqual(agg['success_rate'], 0.5)
        self.assertEqual(agg['avg_step_count'], 4.0)

    def test_aggregate_all_failed(self):
        """全部 error 时 valid_cases=0。"""
        from agent.eval.runner import EvalRunner

        runner = EvalRunner(test_cases=[])
        results = [
            {'metrics': None, 'error': 'boom', 'duration_sec': 1.0},
        ]
        agg = runner._aggregate(results, 'baseline', 1.0)

        self.assertEqual(agg['valid_cases'], 0)
        self.assertEqual(agg['failed_cases'], 1)
        self.assertEqual(agg['success_rate'], 0)

    def test_run_ablation_unknown_name_raises(self):
        """未知 ablation 名应抛 ValueError。"""
        from agent.eval.runner import EvalRunner
        runner = EvalRunner(test_cases=[])
        with self.assertRaises(ValueError):
            runner.run_ablation("nonexistent")

    def test_config_name_detection(self):
        """config 匹配 ABLATION_CONFIGS 时应识别名称。"""
        from agent.eval.runner import EvalRunner, ABLATION_CONFIGS
        from agent.eval.testset import TestCase

        case = TestCase("test", "2026-07-13", "", "sparse", "t")
        mock_state = AgentState(task_input={})
        mock_state.status = 'done'

        with patch('agent.eval.runner.run_agent', return_value=(uuid.uuid4(), mock_state)), \
             patch('agent.eval.runner.collect_run_metrics', return_value={'success': True, 'step_count': 1}):
            runner = EvalRunner(test_cases=[case])
            result = runner.run_single(case, config=ABLATION_CONFIGS['no_critic'])

        self.assertEqual(result['config_name'], 'no_critic')


# ==================== reporter.py ====================

class ReporterTest(TestCase):
    """测试报告生成。"""

    def _sample_report(self):
        return {
            'config_name': 'baseline',
            'timestamp': '2026-07-13T12:00:00',
            'total_duration_sec': 30.0,
            'test_case_count': 2,
            'results': [
                {'case_id': 'c1', 'scenario': 'dense', 'date': '2026-07-13',
                 'config_name': 'baseline', 'run_id': 'r1',
                 'metrics': {'status': 'done', 'success': True, 'step_count': 3,
                             'critic_count': 1, 'llm_judge': {'overall_score': 4},
                             'summary_preview': '• 摘要预览'},
                 'duration_sec': 15.0, 'error': None},
                {'case_id': 'c2', 'scenario': 'sparse', 'date': '2026-07-12',
                 'config_name': 'baseline', 'run_id': None,
                 'metrics': None, 'duration_sec': 15.0, 'error': 'timeout'},
            ],
            'aggregate': {
                'config_name': 'baseline',
                'total_cases': 2, 'valid_cases': 1, 'failed_cases': 1,
                'success_count': 1, 'success_rate': 1.0,
                'avg_step_count': 3.0, 'avg_critic_count': 1.0,
                'avg_critic_replan_rate': 0.5, 'avg_error_count': 0.0,
                'avg_llm_judge_score': 4.0, 'avg_duration_sec': 15.0,
                'total_duration_sec': 30.0,
                'status_distribution': {'done': 1},
                'tool_call_distribution': {'fetch_central': 2, 'summarize': 1},
            },
        }

    def test_to_json(self):
        from agent.eval.reporter import to_json
        result = to_json(self._sample_report())
        data = json.loads(result)
        self.assertEqual(data['config_name'], 'baseline')

    def test_to_markdown_contains_key_sections(self):
        from agent.eval.reporter import to_markdown
        md = to_markdown(self._sample_report())
        self.assertIn('# Eval 报告: baseline', md)
        self.assertIn('聚合指标', md)
        self.assertIn('状态分布', md)
        self.assertIn('工具调用分布', md)
        self.assertIn('单 run 明细', md)
        self.assertIn('100.0%', md)  # success_rate 1.0

    def test_to_markdown_handles_error_case(self):
        from agent.eval.reporter import to_markdown
        md = to_markdown(self._sample_report())
        self.assertIn('ERROR', md)

    def test_to_ablation_markdown(self):
        from agent.eval.reporter import to_ablation_markdown
        reports = [self._sample_report()]
        md = to_ablation_markdown(reports)
        self.assertIn('# Ablation 消融实验对比', md)
        self.assertIn('聚合对比', md)
        self.assertIn('逐用例对比', md)

    def test_fmt_pct_none(self):
        from agent.eval.reporter import _fmt_pct
        self.assertEqual(_fmt_pct(None), '-')

    def test_fmt_pct_value(self):
        from agent.eval.reporter import _fmt_pct
        self.assertEqual(_fmt_pct(0.5), '50.0%')

    def test_save_report(self):
        from agent.eval.reporter import save_report
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = save_report(self._sample_report(), output_dir=tmpdir)
            self.assertTrue(os.path.exists(paths['json']))
            self.assertTrue(os.path.exists(paths['markdown']))


# ==================== testset.py ====================

class TestsetTest(TestCase):
    """测试测试集发现。"""

    def test_discover_empty_db(self):
        """DB 完全空时返回最小测试集。"""
        from agent.eval.testset import discover_test_cases
        cases = discover_test_cases()
        self.assertGreaterEqual(len(cases), 1)
        self.assertEqual(cases[0].scenario, 'empty')

    def test_count_policies_empty(self):
        from agent.eval.testset import _count_policies
        central, local = _count_policies('2026-07-13')
        self.assertEqual(central, 0)
        self.assertEqual(local, 0)

    def test_has_duplicate_titles_false(self):
        from agent.eval.testset import _has_duplicate_titles
        self.assertFalse(_has_duplicate_titles('2026-07-13'))

    def test_has_partial_missing_false(self):
        from agent.eval.testset import _has_partial_missing
        self.assertFalse(_has_partial_missing('2026-07-13'))
