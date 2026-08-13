"""
Django 管理命令：构建 RAG 向量索引。

用法：
    # 重建索引（默认行为：清空旧索引 + 插入所有 DB 政策）
    python manage.py build_index

    # 只看索引数量，不重建
    python manage.py build_index --count

设计要点：
1. 幂等：每次执行先清空 collection，再批量插入所有 CentralPolicy + LocalPolicy
2. doc_text = title + content[:500]：避免长文档影响 embedding 质量
3. 跑爬虫后建议重跑本命令同步索引
"""
from django.core.management.base import BaseCommand

from report.models import CentralPolicy, LocalPolicy
from agent.rag import rebuild_index, index_count


class Command(BaseCommand):
    help = "构建 RAG 向量索引（ChromaDB）"

    def add_arguments(self, parser):
        parser.add_argument(
            '--count', action='store_true',
            help='只打印当前索引数量，不重建',
        )
        parser.add_argument(
            '--content-length', type=int, default=500,
            help='单文档内容截取长度（默认 500 字）',
        )

    def handle(self, *args, **options):
        if options['count']:
            n = index_count()
            self.stdout.write(f"当前索引文档数: {n}")
            return

        content_len = options['content_length']
        self.stdout.write("开始构建 RAG 索引...")

        # 收集所有政策
        policies = []
        for p in CentralPolicy.objects.all():
            policies.append({
                'id': p.id,
                'source': 'central',
                'title': p.title,
                'source_url': p.source_url or '',
                'publish_time': str(p.publish_time),
                'doc_text': f"{p.title}\n{p.content[:content_len]}",
            })
        central_n = len(policies)

        for p in LocalPolicy.objects.all():
            policies.append({
                'id': p.id,
                'source': 'local',
                'title': p.title,
                'source_url': p.source_url or '',
                'publish_time': str(p.publish_time),
                'doc_text': f"{p.title}\n{p.content[:content_len]}",
            })
        local_n = len(policies) - central_n

        # 重建索引
        total = rebuild_index(policies)

        self.stdout.write(self.style.SUCCESS(
            f"索引构建完成：中央 {central_n} 条 + 地方 {local_n} 条 = 共 {total} 条"
        ))
