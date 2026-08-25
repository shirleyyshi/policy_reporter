"""
Agent API 视图（Phase 2 同步）。

端点：
- POST /api/agent/run/         同步运行 Agent，返回 run_id + 状态 + trace
- GET  /api/agent/runs/        列出所有历史 run
- GET  /api/agent/runs/<id>/   查询某次 run 的 trace
- GET  /api/agent/runs/<id>/download/  下载生成的 docx

Phase 5 改后台线程 + 轮询以支持 ask_human 异步。
"""
import datetime
import logging
from django.http import HttpResponse
from django.db.models import Max, Min, Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status as http_status

from .core import run_agent_async, get_state, get_docx, submit_answer
from .models import AgentTrace, AgentRun
from .utils import has_docx_trace

logger = logging.getLogger(__name__)


def _get_owned_run(run_id, user):
    """取属于当前用户的 AgentRun；不存在或不属于该用户返回 None。

    归属校验统一走这里，所有 run 级端点（trace/answer/download）共用。
    不属于本人时与不存在同响应（404），不泄露 run 的存在性。
    历史 run（user 为 null）对所有人不可见。
    """
    return AgentRun.objects.filter(run_id=run_id, user=user).first()


def _infer_status(run_id):
    """从 DB trace 推断 run 状态（cache 丢失时用）。

    优先读 terminate trace 的 output.status（确定性），
    回退到关键词匹配（兼容旧 run）。
    """
    last = AgentTrace.objects.filter(run_id=run_id).order_by('-step').first()
    if not last:
        return 'unknown'
    if last.action != 'terminate':
        return 'incomplete'
    if last.output and isinstance(last.output, dict) and 'status' in last.output:
        return last.output['status']
    reasoning = (last.reasoning or '').lower()
    if 'done' in reasoning or 'finish' in reasoning or 'actuator' in reasoning:
        return 'done'
    return 'failed'


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def agent_run(request):
    """
    异步启动 Agent（Phase 5：后台线程 + 轮询）。
    body: { date: "2025-07-31", legal_text: "..." }
    resp: { run_id, status: "running" }
    """
    date = request.data.get('date')
    legal_text = (request.data.get('legal_text') or '').strip()

    if not date:
        return Response(
            {'detail': 'date 为必填项'},
            status=http_status.HTTP_400_BAD_REQUEST
        )
    try:
        datetime.date.fromisoformat(str(date))
    except (TypeError, ValueError):
        return Response(
            {'detail': 'date 必须是 YYYY-MM-DD 格式'},
            status=http_status.HTTP_400_BAD_REQUEST
        )

    try:
        run_id = run_agent_async(date, legal_text, user=request.user)
    except Exception:
        logger.exception("Agent 启动异常")
        return Response(
            {'detail': 'Agent 启动失败'},
            status=http_status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return Response({
        'run_id': str(run_id),
        'status': 'running',
    })


@api_view(['GET'])
def agent_trace(request, run_id):
    """查询某次 run 的 trace（从 DB 读，仅本人可见）。"""
    if not _get_owned_run(run_id, request.user):
        return Response(
            {'error': 'run_id 不存在'},
            status=http_status.HTTP_404_NOT_FOUND
        )
    traces = AgentTrace.objects.filter(run_id=run_id).order_by('step')
    trace_list = [
        {
            'step': t.step,
            'action': t.action,
            'tool': t.tool,
            'input': t.input,
            'output': t.output,
            'reasoning': t.reasoning,
            'timestamp': t.timestamp.isoformat() if t.timestamp else None,
        }
        for t in traces
    ]
    state = get_state(run_id)
    if state:
        run_status = state.status
        step = state.step
        state_summary = state.summary_view()
        docx_available = state.docx_bytes is not None
    else:
        run_status = _infer_status(run_id)
        step = trace_list[-1]['step'] if trace_list else 0
        state_summary = None
        docx_available = has_docx_trace(run_id)
    return Response({
        'run_id': str(run_id),
        'status': run_status,
        'step': step,
        'state_summary': state_summary,
        'docx_available': docx_available,
        'trace': trace_list,
        'pending_question': state.pending_question if (state and state.status == "waiting_human") else None,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_download(request, run_id):
    """下载某次 run 生成的 docx（仅本人）。文件名用报告日期，而非 run_id。"""
    run = _get_owned_run(run_id, request.user)
    if not run:
        return Response(
            {'error': 'docx 未生成（run 不存在或未产出 docx）'},
            status=http_status.HTTP_404_NOT_FOUND
        )
    docx_bytes = get_docx(run_id)
    if not docx_bytes:
        return Response(
            {'error': 'docx 未生成（run 不存在或未产出 docx）'},
            status=http_status.HTTP_404_NOT_FOUND
        )
    # 文件名带报告日期：Word 窗口标题直接可读；无日期（异常数据）回退 run_id
    date_str = (run.task_input.get('date') or '')[:10].replace('-', '.')
    filename = f'每日财税日报（{date_str}）.docx' if date_str else f'agent_report_{run_id}.docx'
    # RFC 5987：中文文件名需 URL 编码，避免部分浏览器/代理解析成乱码
    from urllib.parse import quote
    return HttpResponse(
        docx_bytes,
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(filename)}"}
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def agent_answer(request, run_id):
    """
    提交人工回答（Phase 5：人在回路）。
    body: { answer: "用户选择的答案" }
    resp: { ok: true/false }
    """
    answer = request.data.get('answer')
    if not answer:
        return Response(
            {'error': 'answer 为必填项'},
            status=http_status.HTTP_400_BAD_REQUEST
        )
    if not _get_owned_run(run_id, request.user):
        return Response(
            {'error': 'run_id 不存在'},
            status=http_status.HTTP_404_NOT_FOUND
        )
    ok = submit_answer(run_id, answer)
    if not ok:
        return Response(
            {'ok': False, 'error': '该 run 未在等待人工回答（可能已超时或已回答）'},
            status=http_status.HTTP_409_CONFLICT
        )
    return Response({'ok': True})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_runs_list(request):
    """列出当前用户的历史 run（从 DB 聚合，按时间倒序）。

    隔离：只聚合 AgentRun.user = request.user 的 run。
    历史 run（user 为 null）不出现在任何人的列表里。
    """
    owned_run_ids = list(
        AgentRun.objects.filter(user=request.user).values_list('run_id', flat=True)
    )
    runs = (
        AgentTrace.objects
        .filter(run_id__in=owned_run_ids)
        .values('run_id')
        .annotate(
            step_count=Max('step'),
            trace_count=Count('id'),
            created_at=Min('timestamp'),
            last_updated=Max('timestamp'),
        )
        .order_by('-last_updated')
    )
    result = []
    for r in runs:
        has_docx = has_docx_trace(r['run_id'])
        state = get_state(r['run_id'])
        status = state.status if state else _infer_status(r['run_id'])
        result.append({
            'run_id': str(r['run_id']),
            'step_count': r['step_count'],
            'trace_count': r['trace_count'],
            'status': status,
            'has_docx': has_docx or (state.docx_bytes is not None if state else False),
            'created_at': r['created_at'].isoformat() if r['created_at'] else None,
            'last_updated': r['last_updated'].isoformat() if r['last_updated'] else None,
        })
    return Response({'runs': result, 'total': len(result)})
