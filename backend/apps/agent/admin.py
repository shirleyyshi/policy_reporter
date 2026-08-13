from django.contrib import admin
from .models import AgentTrace, AgentRun


@admin.register(AgentTrace)
class AgentTraceAdmin(admin.ModelAdmin):
    list_display = ('run_id', 'step', 'action', 'tool', 'timestamp')
    search_fields = ('run_id', 'tool', 'action')
    list_filter = ('action', 'tool')
    ordering = ('run_id', 'step')


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ('run_id', 'status', 'step', 'created_at', 'updated_at')
    list_filter = ('status',)
    search_fields = ('run_id',)
    ordering = ('-created_at',)
    readonly_fields = ('run_id', 'created_at', 'updated_at')
