"""Agent views.py API 端点测试。

覆盖：
- agent_run：正常启动 / 缺 date / 启动异常
- agent_trace：存在 / 不存在 / cache 命中 / cache miss 走 _infer_status
- agent_download：有 docx / 无 docx
- agent_answer：正常提交 / 缺 answer / 无等待中 run
- agent_run_list：空列表 / 多条 run
- _infer_status：done/failed/incomplete/unknown + 旧 run 关键词回退
- _has_docx_trace

注意：Agent API 需 JWT 认证，测试用 conftest.py 的 auth_client fixture。
"""
import uuid
import pytest
from unittest.mock import patch, MagicMock

from django.test import TestCase
from rest_framework.test import APIClient

from agent.models import AgentTrace, AgentRun
from agent.tools import AgentState
from agent.core import _RUN_CACHE


def _seed_traces(run_id, specs):
    for s in specs:
        AgentTrace.objects.create(
            run_id=run_id,
            step=s.get('step', 1),
            action=s.get('action', 'actuate'),
            tool=s.get('tool'),
            input=s.get('input'),
            output=s.get('output'),
            reasoning=s.get('reasoning'),
        )


def _seed_run(run_id, user=None, status='done', step=0):
    """创建 AgentRun 记录（D1 用户隔离后，run 级端点要求归属匹配）。"""
    return AgentRun.objects.create(
        run_id=run_id, user=user, status=status, step=step,
        task_input={'date': '2026-07-13'},
    )


class InferStatusTest(TestCase):
    """测试 _infer_status。"""

    def test_unknown_when_no_traces(self):
        from agent.views import _infer_status
        self.assertEqual(_infer_status(uuid.uuid4()), 'unknown')

    def test_incomplete_when_no_terminate(self):
        from agent.views import _infer_status
        run_id = uuid.uuid4()
        _seed_traces(run_id, [{'step': 1, 'action': 'actuate', 'tool': 'fetch_central'}])
        self.assertEqual(_infer_status(run_id), 'incomplete')

    def test_done_from_output_status(self):
        from agent.views import _infer_status
        run_id = uuid.uuid4()
        _seed_traces(run_id, [
            {'step': 1, 'action': 'terminate', 'output': {'status': 'done'}, 'reasoning': '完成'},
        ])
        self.assertEqual(_infer_status(run_id), 'done')

    def test_failed_from_output_status(self):
        from agent.views import _infer_status
        run_id = uuid.uuid4()
        _seed_traces(run_id, [
            {'step': 1, 'action': 'terminate', 'output': {'status': 'failed'}, 'reasoning': '失败'},
        ])
        self.assertEqual(_infer_status(run_id), 'failed')

    def test_done_from_reasoning_keyword_fallback(self):
        """无 output.status 时从 reasoning 关键词回退。"""
        from agent.views import _infer_status
        run_id = uuid.uuid4()
        _seed_traces(run_id, [
            {'step': 1, 'action': 'terminate', 'output': {}, 'reasoning': 'Actuator done'},
        ])
        self.assertEqual(_infer_status(run_id), 'done')

    def test_failed_from_reasoning_no_keyword(self):
        from agent.views import _infer_status
        run_id = uuid.uuid4()
        _seed_traces(run_id, [
            {'step': 1, 'action': 'terminate', 'output': {}, 'reasoning': '连续失败'},
        ])
        self.assertEqual(_infer_status(run_id), 'failed')


class HasDocxTraceTest(TestCase):
    """测试 has_docx_trace（agent.utils，views 与 eval/metrics 共用）。"""

    def test_true_when_format_docx_success(self):
        from agent.utils import has_docx_trace
        run_id = uuid.uuid4()
        _seed_traces(run_id, [
            {'step': 1, 'action': 'actuate', 'tool': 'format_docx', 'output': {'ok': True}},
        ])
        self.assertTrue(has_docx_trace(run_id))

    def test_false_when_format_docx_has_error(self):
        from agent.utils import has_docx_trace
        run_id = uuid.uuid4()
        _seed_traces(run_id, [
            {'step': 1, 'action': 'actuate', 'tool': 'format_docx', 'output': {'error': 'fail'}},
        ])
        self.assertFalse(has_docx_trace(run_id))

    def test_false_when_no_format_docx(self):
        from agent.utils import has_docx_trace
        self.assertFalse(has_docx_trace(uuid.uuid4()))


class AgentRunEndpointTest(TestCase):
    """测试 POST /api/agent/run/。"""

    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_missing_date_returns_400(self):
        resp = self.client.post('/api/agent/run/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('date', resp.data['detail'])

    def test_starts_agent_and_returns_running(self):
        mock_run_id = uuid.uuid4()
        with patch('agent.views.run_agent_async', return_value=mock_run_id):
            resp = self.client.post('/api/agent/run/', {'date': '2026-07-13'}, format='json')
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.data['status'], 'running')
        self.assertEqual(resp.data['run_id'], str(mock_run_id))

    def test_exception_returns_500(self):
        with patch('agent.views.run_agent_async', side_effect=Exception("boom")):
            resp = self.client.post('/api/agent/run/', {'date': '2026-07-13'}, format='json')
        self.assertEqual(resp.status_code, 500)
        self.assertIn('启动失败', resp.data['detail'])

    def test_legal_text_stripped(self):
        """legal_text 应被 strip，且以当前用户作为归属启动。"""
        mock_run_id = uuid.uuid4()
        with patch('agent.views.run_agent_async', return_value=mock_run_id) as mock_run:
            self.client.post('/api/agent/run/', {'date': '2026-07-13', 'legal_text': '  text  '}, format='json')
        mock_run.assert_called_once_with('2026-07-13', 'text', user=self.user)


class AgentTraceEndpointTest(TestCase):
    """测试 GET /api/agent/runs/<id>/。"""

    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_404_when_not_exist(self):
        resp = self.client.get(f'/api/agent/runs/{uuid.uuid4()}/')
        self.assertEqual(resp.status_code, 404)

    def test_returns_traces_from_db(self):
        run_id = uuid.uuid4()
        _seed_run(run_id, self.user)
        _seed_traces(run_id, [
            {'step': 1, 'action': 'actuate', 'tool': 'fetch_central', 'output': {'fetched': 3}},
            {'step': 2, 'action': 'terminate', 'output': {'status': 'done'}, 'reasoning': '完成'},
        ])
        resp = self.client.get(f'/api/agent/runs/{run_id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['trace']), 2)
        self.assertEqual(resp.data['trace'][0]['tool'], 'fetch_central')

    def test_state_from_cache_when_available(self):
        """cache 有 state 时优先用。"""
        run_id = uuid.uuid4()
        _seed_run(run_id, self.user)
        state = AgentState(task_input={})
        state.status = 'running'
        state.step = 5
        _RUN_CACHE[str(run_id)] = state
        _seed_traces(run_id, [{'step': 1, 'action': 'actuate', 'tool': 'fetch_central'}])

        resp = self.client.get(f'/api/agent/runs/{run_id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'running')
        self.assertEqual(resp.data['step'], 5)
        self.assertIsNotNone(resp.data['state_summary'])

    def test_state_from_db_when_cache_miss(self):
        """cache miss 且归属记录存在时，从 DB AgentRun 恢复 status/step。

        D1 隔离后归属校验保证 AgentRun 存在，get_state 必然返回 DB state，
        视图层的 _infer_status 回退仅在 AgentRun 缺失时触发（此时已被 404 拦截）。
        """
        run_id = uuid.uuid4()
        _seed_run(run_id, self.user, status='done', step=3)
        _RUN_CACHE.clear()
        _seed_traces(run_id, [
            {'step': 3, 'action': 'terminate', 'output': {'status': 'done'}, 'reasoning': '完成'},
        ])
        resp = self.client.get(f'/api/agent/runs/{run_id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'done')
        self.assertEqual(resp.data['step'], 3)

    def test_pending_question_when_waiting_human(self):
        """waiting_human 时应返回 pending_question。"""
        run_id = uuid.uuid4()
        _seed_run(run_id, self.user, status='waiting_human')
        state = AgentState(task_input={})
        state.status = 'waiting_human'
        state.pending_question = {'question': '选哪个？', 'options': ['A', 'B']}
        _RUN_CACHE[str(run_id)] = state
        _seed_traces(run_id, [{'step': 1, 'action': 'actuate', 'tool': 'ask_human'}])

        resp = self.client.get(f'/api/agent/runs/{run_id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.data['pending_question'])
        self.assertEqual(resp.data['pending_question']['question'], '选哪个？')


class AgentDownloadEndpointTest(TestCase):
    """测试 GET /api/agent/runs/<id>/download/。"""

    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_404_when_no_docx(self):
        with patch('agent.views.get_docx', return_value=None):
            resp = self.client.get(f'/api/agent/runs/{uuid.uuid4()}/download/')
        self.assertEqual(resp.status_code, 404)

    def test_returns_docx_file(self):
        run_id = uuid.uuid4()
        _seed_run(run_id, self.user)
        with patch('agent.views.get_docx', return_value=b'fake docx bytes'):
            resp = self.client.get(f'/api/agent/runs/{run_id}/download/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('attachment', resp['Content-Disposition'])
        # 文件名用报告日期（_seed_run 的 task_input.date=2026-07-13），RFC 5987 URL 编码
        from urllib.parse import quote
        self.assertIn(quote('每日财税日报（2026.07.13）.docx'), resp['Content-Disposition'])
        self.assertEqual(resp.content, b'fake docx bytes')


class AgentAnswerEndpointTest(TestCase):
    """测试 POST /api/agent/runs/<id>/answer/。"""

    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_400_when_missing_answer(self):
        resp = self.client.post(f'/api/agent/runs/{uuid.uuid4()}/answer/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_409_when_no_waiting_run(self):
        run_id = uuid.uuid4()
        _seed_run(run_id, self.user)
        with patch('agent.views.submit_answer', return_value=False):
            resp = self.client.post(f'/api/agent/runs/{run_id}/answer/', {'answer': 'A'}, format='json')
        self.assertEqual(resp.status_code, 409)
        self.assertIn('等待人工回答', resp.data['detail'])

    def test_200_when_submitted(self):
        run_id = uuid.uuid4()
        _seed_run(run_id, self.user)
        with patch('agent.views.submit_answer', return_value=True):
            resp = self.client.post(f'/api/agent/runs/{run_id}/answer/', {'answer': 'A'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['ok'])


class AgentRunsListEndpointTest(TestCase):
    """测试 GET /api/agent/runs/。"""

    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_empty_list(self):
        resp = self.client.get('/api/agent/runs/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total'], 0)
        self.assertEqual(resp.data['runs'], [])

    def test_lists_multiple_runs(self):
        run1 = uuid.uuid4()
        run2 = uuid.uuid4()
        _seed_run(run1, self.user)
        _seed_run(run2, self.user)
        _seed_traces(run1, [
            {'step': 2, 'action': 'actuate', 'tool': 'fetch_central'},
            {'step': 2, 'action': 'terminate', 'output': {'status': 'done'}},
        ])
        _seed_traces(run2, [
            {'step': 1, 'action': 'actuate', 'tool': 'fetch_local'},
        ])
        _RUN_CACHE.clear()

        resp = self.client.get('/api/agent/runs/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total'], 2)
        run_ids = [r['run_id'] for r in resp.data['runs']]
        self.assertIn(str(run1), run_ids)
        self.assertIn(str(run2), run_ids)

    def test_run_has_docx_from_trace(self):
        run_id = uuid.uuid4()
        _seed_run(run_id, self.user)
        _seed_traces(run_id, [
            {'step': 1, 'action': 'actuate', 'tool': 'format_docx', 'output': {'ok': True}},
        ])
        _RUN_CACHE.clear()
        resp = self.client.get('/api/agent/runs/')
        run = [r for r in resp.data['runs'] if r['run_id'] == str(run_id)][0]
        self.assertTrue(run['has_docx'])


class AgentIsolationTest(TestCase):
    """D1 用户隔离：run 级端点只能访问本人创建的 run。

    覆盖：trace/download/answer 跨用户 404、列表只含本人 run、
    历史 run（user=null）对所有人不可见、未登录 401。
    """

    def setUp(self):
        from django.contrib.auth.models import User
        self.alice = User.objects.create_user(username='alice', password='pass12345')
        self.bob = User.objects.create_user(username='bob', password='pass12345')
        self.client = APIClient()
        self.client.force_authenticate(user=self.alice)

    def test_trace_cross_user_404(self):
        run_id = uuid.uuid4()
        _seed_run(run_id, self.bob)
        _seed_traces(run_id, [{'step': 1, 'action': 'actuate', 'tool': 'fetch_central'}])
        resp = self.client.get(f'/api/agent/runs/{run_id}/')
        self.assertEqual(resp.status_code, 404)

    def test_download_cross_user_404(self):
        run_id = uuid.uuid4()
        _seed_run(run_id, self.bob)
        with patch('agent.views.get_docx', return_value=b'bytes'):
            resp = self.client.get(f'/api/agent/runs/{run_id}/download/')
        self.assertEqual(resp.status_code, 404)

    def test_answer_cross_user_404(self):
        run_id = uuid.uuid4()
        _seed_run(run_id, self.bob)
        with patch('agent.views.submit_answer', return_value=True) as mock_submit:
            resp = self.client.post(f'/api/agent/runs/{run_id}/answer/', {'answer': 'A'}, format='json')
        self.assertEqual(resp.status_code, 404)
        mock_submit.assert_not_called()

    def test_list_excludes_other_users_runs(self):
        own = uuid.uuid4()
        other = uuid.uuid4()
        _seed_run(own, self.alice)
        _seed_run(other, self.bob)
        _seed_traces(own, [{'step': 1, 'action': 'actuate', 'tool': 'fetch_central'}])
        _seed_traces(other, [{'step': 1, 'action': 'actuate', 'tool': 'fetch_central'}])
        _RUN_CACHE.clear()
        resp = self.client.get('/api/agent/runs/')
        self.assertEqual(resp.data['total'], 1)
        self.assertEqual(resp.data['runs'][0]['run_id'], str(own))

    def test_legacy_run_without_user_invisible(self):
        """功能上线前的历史 run（user=null）不出现在任何人的列表，详情 404。"""
        legacy = uuid.uuid4()
        _seed_run(legacy, user=None)
        _seed_traces(legacy, [{'step': 1, 'action': 'actuate', 'tool': 'fetch_central'}])
        _RUN_CACHE.clear()
        resp = self.client.get('/api/agent/runs/')
        self.assertEqual(resp.data['total'], 0)
        resp = self.client.get(f'/api/agent/runs/{legacy}/')
        self.assertEqual(resp.status_code, 404)

    def test_unauthenticated_401(self):
        anonymous = APIClient()
        resp = anonymous.get('/api/agent/runs/')
        self.assertEqual(resp.status_code, 401)

    def test_owner_still_sees_own_run(self):
        """回归：本人 run 正常访问（跨用户 404 不是全局拒绝）。"""
        run_id = uuid.uuid4()
        _seed_run(run_id, self.alice)
        _seed_traces(run_id, [{'step': 1, 'action': 'actuate', 'tool': 'fetch_central'}])
        resp = self.client.get(f'/api/agent/runs/{run_id}/')
        self.assertEqual(resp.status_code, 200)
