"""
Agent 模块公共工具函数。

消除 views.py 和 eval/metrics.py 中 _has_docx_trace 的重复定义。
"""
from .models import AgentTrace


def has_docx_trace(run_id) -> bool:
    """DB trace 中是否有成功的 format_docx 调用。

    供 views.py（_infer_status 回退）和 eval/metrics.py（success/has_docx）共用。
    """
    return AgentTrace.objects.filter(
        run_id=run_id, tool='format_docx'
    ).exclude(output__has_key='error').exists()
