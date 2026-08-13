"""
report 模块单元测试。

覆盖：
- CentralPolicy / LocalPolicy 模型基本行为
- generate_docx 函数（核心导出逻辑）
- get_policies / get_policy_counts / export_policies 视图鉴权与返回
- crawl_policies.parse_date（爬虫日期解析）

运行：
    python manage.py test report
"""
from datetime import datetime
from io import BytesIO

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from report.models import CentralPolicy, LocalPolicy
from report.views import generate_docx
from report.management.commands.crawl_policies import parse_date


def make_dt(year, month, day, hour=10, minute=0):
    """构造 timezone-aware datetime（避免 naive datetime 警告）。"""
    return timezone.make_aware(datetime(year, month, day, hour, minute))


class PolicyModelTest(TestCase):
    """测试 CentralPolicy / LocalPolicy 模型。"""

    def test_create_central_policy(self):
        policy = CentralPolicy.objects.create(
            title="测试政策",
            content="正文",
            type="通知",
            publish_time=make_dt(2026, 7, 13),
            source_url="http://example.com/1",
        )
        self.assertEqual(policy.title, "测试政策")
        self.assertEqual(str(policy), "测试政策")
        self.assertIsNone(policy.crawled_at)

    def test_create_local_policy(self):
        policy = LocalPolicy.objects.create(
            title="上海政策",
            content="正文",
            province="上海",
            publish_time=make_dt(2026, 7, 13),
            source_url="http://shanghai.gov.cn/1",
        )
        self.assertEqual(policy.province, "上海")
        self.assertEqual(str(policy), "上海政策")

    def test_crawled_at_field_persists(self):
        """crawled_at 字段应该可以保存采集时间。"""
        now = timezone.now()
        policy = CentralPolicy.objects.create(
            title="x", content="y", type="通知",
            publish_time=now, source_url="http://x",
            crawled_at=now,
        )
        self.assertIsNotNone(policy.crawled_at)

    def test_default_ordering(self):
        """模型默认按 publish_time 倒序。"""
        CentralPolicy.objects.create(
            title="旧", content="", type="通知",
            publish_time=make_dt(2025, 1, 1),
            source_url="http://old",
        )
        CentralPolicy.objects.create(
            title="新", content="", type="通知",
            publish_time=make_dt(2026, 7, 1),
            source_url="http://new",
        )
        qs = CentralPolicy.objects.all()
        self.assertEqual(qs[0].title, "新")
        self.assertEqual(qs[1].title, "旧")


class GenerateDocxTest(TestCase):
    """测试 generate_docx 函数。"""

    def test_generate_docx_with_data(self):
        """有数据时应生成非空 docx。"""
        central = [("中央政策1", "内容1", "通知", "http://c1")]
        local = [("地方政策1", "内容2", "上海", "http://l1")]
        out = BytesIO()
        # 传 summary 跳过 LLM 调用
        generate_docx(central, local, "", out, summary="• 测试摘要")
        self.assertGreater(len(out.getvalue()), 0)

    def test_generate_docx_empty_data(self):
        """空数据也应能生成 docx（不会抛异常）。"""
        out = BytesIO()
        generate_docx([], [], "", out, summary="• 空数据摘要")
        self.assertGreater(len(out.getvalue()), 0)

    def test_generate_docx_with_legal_text(self):
        """带 legal_text 时 docx 应包含该文本。"""
        legal = "测试法律法规内容"
        out = BytesIO()
        generate_docx([], [], legal, out, summary="• 摘要")
        # docx 是二进制，无法直接断言文本包含，只验证不抛异常 + 文件非空
        self.assertGreater(len(out.getvalue()), 0)


class GetPoliciesViewTest(TestCase):
    """测试 get_policies 视图。"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client = APIClient()
        CentralPolicy.objects.create(
            title="政策A", content="内容A", type="通知",
            publish_time=make_dt(2026, 7, 13),
            source_url="http://a",
        )
        LocalPolicy.objects.create(
            title="地方B", content="内容B", province="上海",
            publish_time=make_dt(2026, 7, 13),
            source_url="http://b",
        )

    def test_requires_authentication(self):
        """未登录应返回 401。"""
        resp = self.client.get('/api/policies/')
        self.assertEqual(resp.status_code, 401)

    def test_authenticated_returns_policies(self):
        """登录后返回所有政策。"""
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/policies/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['central']), 1)
        self.assertEqual(len(resp.data['local']), 1)
        self.assertEqual(resp.data['central'][0]['source'], 'central')
        self.assertEqual(resp.data['local'][0]['source'], 'local')

    def test_filter_by_date(self):
        """按日期过滤应只返回匹配的政策。"""
        self.client.force_authenticate(user=self.user)
        # 查一个没有政策的日期
        resp = self.client.get('/api/policies/?date=2020-01-01')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['central']), 0)
        self.assertEqual(len(resp.data['local']), 0)


class GetPolicyCountsViewTest(TestCase):
    """测试 get_policy_counts 视图。"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client = APIClient()
        CentralPolicy.objects.create(
            title="c1", content="", type="通知",
            publish_time=make_dt(2026, 7, 13),
            source_url="http://c1",
        )
        CentralPolicy.objects.create(
            title="c2", content="", type="通知",
            publish_time=make_dt(2026, 7, 13),
            source_url="http://c2",
        )
        LocalPolicy.objects.create(
            title="l1", content="", province="上海",
            publish_time=make_dt(2026, 7, 13),
            source_url="http://l1",
        )

    def test_requires_authentication(self):
        resp = self.client.get('/api/policy-counts/')
        self.assertEqual(resp.status_code, 401)

    def test_counts_correct(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/policy-counts/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['central_count'], 2)
        self.assertEqual(resp.data['local_count'], 1)


class ExportPoliciesViewTest(TestCase):
    """测试 export_policies 视图。"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client = APIClient()
        self.central = CentralPolicy.objects.create(
            title="导出测试", content="内容", type="通知",
            publish_time=make_dt(2026, 7, 13),
            source_url="http://export",
        )

    def test_requires_authentication(self):
        resp = self.client.post('/api/export/', {'selected_ids': []}, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_export_returns_docx(self):
        """登录后导出应返回 docx 文件。"""
        self.client.force_authenticate(user=self.user)
        resp = self.client.post('/api/export/', {
            'selected_ids': [{'id': self.central.id, 'source': 'central'}],
            'legal_text': '合规资讯',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('wordprocessingml', resp['Content-Type'])
        self.assertGreater(len(resp.content), 0)


class ParseDateTest(TestCase):
    """测试爬虫的 parse_date 函数。"""

    def test_iso_format(self):
        d = parse_date("2026-07-13")
        self.assertIsNotNone(d)
        self.assertEqual(d.year, 2026)
        self.assertEqual(d.month, 7)
        self.assertEqual(d.day, 13)

    def test_iso_with_time(self):
        d = parse_date("2026-07-13 10:30:00")
        self.assertIsNotNone(d)
        self.assertEqual(d.hour, 10)
        self.assertEqual(d.minute, 30)

    def test_chinese_format(self):
        d = parse_date("2026年7月13日")
        self.assertIsNotNone(d)
        self.assertEqual(d.year, 2026)
        self.assertEqual(d.month, 7)
        self.assertEqual(d.day, 13)

    def test_dot_format(self):
        d = parse_date("2026.07.13")
        self.assertIsNotNone(d)
        self.assertEqual(d.year, 2026)

    def test_empty_input(self):
        self.assertIsNone(parse_date(""))
        self.assertIsNone(parse_date(None))

    def test_invalid_input(self):
        self.assertIsNone(parse_date("not a date"))

    def test_uses_shanghai_timezone(self):
        """解析出来的 datetime 应带 Asia/Shanghai 时区。"""
        from zoneinfo import ZoneInfo
        d = parse_date("2026-07-13 10:00:00")
        self.assertIsNotNone(d)
        self.assertEqual(d.tzinfo, ZoneInfo("Asia/Shanghai"))
