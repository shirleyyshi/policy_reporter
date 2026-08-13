from django.contrib import admin
from .models import CentralPolicy, LocalPolicy


@admin.register(CentralPolicy)
class CentralPolicyAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'type', 'publish_time', 'crawled_at')
    search_fields = ('title', 'type')
    list_filter = ('type', 'publish_time')
    ordering = ('-publish_time',)


@admin.register(LocalPolicy)
class LocalPolicyAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'province', 'publish_time', 'crawled_at')
    search_fields = ('title', 'province')
    list_filter = ('province', 'publish_time')
    ordering = ('-publish_time',)
