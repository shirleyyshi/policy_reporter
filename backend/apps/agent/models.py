import uuid
from django.conf import settings
from django.db import models


class AgentTrace(models.Model):
    """
    Agent 运行轨迹表。同一次 run 的所有步骤共享 run_id。
    入 DB 而非只写文件：Phase 4 eval 要按 run_id 批量聚合统计
    （平均步数、工具调用分布、Critic 触发率），DB 查询比读日志高效。
    """
    run_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    step = models.IntegerField()
    action = models.CharField(max_length=32)
    tool = models.CharField(max_length=32, null=True, blank=True)
    input = models.JSONField(null=True, blank=True)
    output = models.JSONField(null=True, blank=True)
    reasoning = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'agent_trace'
        ordering = ['run_id', 'step']

    def __str__(self):
        return f"[{self.run_id}] step={self.step} action={self.action} tool={self.tool}"


class AgentRun(models.Model):
    """
    Agent 运行实例表。同一次 run 一条记录，持久化 state 支持：
    - gunicorn 多 worker 共享 state（_RUN_CACHE 是进程内 dict，多 worker 不共享）
    - 服务重启后恢复 state（cache 丢失时从 DB 反序列化）
    - 前端历史 run 列表持久可见（不依赖内存 cache）

    state_json 存可序列化的 state 字段（排除 trace/docx_bytes/callable）。
    trace 在 AgentTrace 表，docx 在 media/agent_docx/{run_id}.docx。
    """
    run_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    # 创建者。nullable：功能上线前的历史 run 无归属，隔离生效后任何用户不可见
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='agent_runs',
    )
    status = models.CharField(max_length=20, default='running')  # running/waiting_human/done/failed
    step = models.IntegerField(default=0)
    task_input = models.JSONField(default=dict)
    state_json = models.JSONField(default=dict)
    summary = models.TextField(default='', blank=True)
    docx_path = models.CharField(max_length=500, null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'agent_run'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.run_id}] status={self.status} step={self.step}"
