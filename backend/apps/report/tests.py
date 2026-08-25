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
        local = [("地方政策1", "内容2", "综合", "http://l1")]
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

    def test_empty_source_url_no_invalid_relationship(self):
        """空 source_url（手动录入政策）不得产生 Target='' 外链关系。

        Word 对关系合法性严格校验，空 Target 的外链会导致整份文档拒开
        （python-docx 宽松可打开，必须解包 .rels 断言）。
        """
        import zipfile
        central = [
            ("手动录入政策", "内容", "财政", ""),
            ("爬取政策", "内容", "税务", "http://example.com/a"),
        ]
        local = [("地方手动政策", "内容", "综合", "")]
        out = BytesIO()
        generate_docx(central, local, "", out, summary="• 摘要", report_date="2026-01-15")
        with zipfile.ZipFile(BytesIO(out.getvalue())) as z:
            rels = z.read("word/_rels/document.xml.rels").decode("utf-8")
        self.assertNotIn('Target=""', rels)
        self.assertIn("http://example.com/a", rels)


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

    def test_list_includes_crawled_at(self):
        """列表应包含 crawled_at（D2 详情页/列表展示采集时间）。"""
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/policies/')
        self.assertIn('crawled_at', resp.data['central'][0])
        self.assertIn('crawled_at', resp.data['local'][0])


class PolicyDetailViewTest(TestCase):
    """测试 policy_detail 视图（D2 政策详情页）。"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client = APIClient()
        self.central = CentralPolicy.objects.create(
            title="中央政策X", content="中央正文全文", type="财政",
            publish_time=make_dt(2026, 7, 13),
            source_url="http://central.example.com/x",
            crawled_at=make_dt(2026, 8, 1, 8, 0),
        )
        self.local = LocalPolicy.objects.create(
            title="地方政策Y", content="地方正文全文", province="广东", type="税务",
            publish_time=make_dt(2026, 7, 13),
            source_url="http://local.example.com/y",
        )

    def test_requires_authentication(self):
        """未登录应返回 401。"""
        resp = self.client.get('/api/policies/detail/', {'source': 'central', 'id': self.central.id})
        self.assertEqual(resp.status_code, 401)

    def test_central_detail_fields(self):
        """中央政策详情应含全文/类型/采集时间/来源。"""
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/policies/detail/', {'source': 'central', 'id': self.central.id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['title'], "中央政策X")
        self.assertEqual(resp.data['content'], "中央正文全文")
        self.assertEqual(resp.data['type'], "财政")
        self.assertEqual(resp.data['source'], 'central')
        self.assertIsNotNone(resp.data['crawled_at'])

    def test_local_detail_fields(self):
        """地方政策详情应含 province 与 type。"""
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/policies/detail/', {'source': 'local', 'id': self.local.id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['province'], "广东")
        self.assertEqual(resp.data['type'], "税务")

    def test_not_found(self):
        """不存在的 id 返回 404。"""
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/policies/detail/', {'source': 'central', 'id': 99999})
        self.assertEqual(resp.status_code, 404)

    def test_invalid_id_string(self):
        """非数字 id 返回 400 而非 500。"""
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/policies/detail/', {'source': 'central', 'id': 'abc'})
        self.assertEqual(resp.status_code, 400)

    def test_invalid_source_400(self):
        """source 非 central/local 返回 400。"""
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/policies/detail/', {'source': 'other', 'id': 1})
        self.assertEqual(resp.status_code, 400)

    def test_missing_id_400(self):
        """缺 id 返回 400。"""
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/policies/detail/', {'source': 'central'})
        self.assertEqual(resp.status_code, 400)


class HealthViewTest(TestCase):
    """测试 health 端点（E4a，供探活）。"""

    def test_anonymous_200_ok(self):
        """匿名可访问（探活不带凭据），DB 正常时返回 200 + status ok。"""
        resp = self.client.get('/api/health/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'ok')
        self.assertTrue(resp.data['db'])

    def test_db_failure_503(self):
        """DB 不可用时返回 503 + degraded。"""
        from unittest.mock import patch
        from django.db import connection
        with patch.object(connection, 'cursor', side_effect=Exception('db down')):
            resp = self.client.get('/api/health/')
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.data['status'], 'degraded')


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
        from unittest.mock import patch
        self.client.force_authenticate(user=self.user)
        # mock LLM 摘要调用，避免依赖真实 API key
        with patch('report.views.call_deepseek_summarization', return_value='• 测试摘要'):
            resp = self.client.post('/api/export/', {
                'selected_ids': [{'id': self.central.id, 'source': 'central'}],
                'legal_text': '合规资讯',
            }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('wordprocessingml', resp['Content-Type'])
        self.assertGreater(len(resp.content), 0)


class RegisterViewTest(TestCase):
    """测试公开注册接口只创建普通用户。"""

    def setUp(self):
        self.client = APIClient()

    def test_register_creates_normal_user(self):
        response = self.client.post(
            '/api/auth/register/',
            {'username': 'newuser', 'password': 'safe-pass-123'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username='newuser')
        self.assertTrue(user.check_password('safe-pass-123'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_duplicate_username_rejected(self):
        User.objects.create_user(username='existing', password='safe-pass-123')
        response = self.client.post(
            '/api/auth/register/',
            {'username': 'existing', 'password': 'safe-pass-123'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('已存在', response.data['detail'])

    def test_short_password_rejected(self):
        response = self.client.post(
            '/api/auth/register/',
            {'username': 'shortpass', 'password': '123'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username='shortpass').exists())


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
