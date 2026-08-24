"""
admin IP 白名单中间件测试。

覆盖：
- 客户端 IP 解析优先级：X-Real-IP > XFF 末项 > REMOTE_ADDR（不信任 XFF 首项，防伪造）
- 伪造 XFF 首项无法绕过白名单
- ADMIN_ALLOWED_IPS 含空串（环境变量设为空值）时不误拦截所有人
- 非 /admin/ 路径不受影响
"""
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.conf import settings

from config.middleware import admin_ip_whitelist, _client_ip


class AllowedHostsProbeTest(TestCase):
    """healthcheck 探活的 Host 头放行（2026-08-24 生产 400 故障回归）。"""

    def test_loopback_in_allowed_hosts(self):
        """settings 固定追加回环地址，不依赖 .env 配置。"""
        self.assertIn('127.0.0.1', settings.ALLOWED_HOSTS)

    def test_health_with_loopback_host(self):
        """Host: 127.0.0.1 直连探活返回 200（原故障：DisallowedHost → 400 → 容器 unhealthy）。"""
        resp = self.client.get('/api/health/', HTTP_HOST='127.0.0.1')
        self.assertEqual(resp.status_code, 200)


class ClientIpTest(SimpleTestCase):
    """_client_ip 解析优先级。"""

    def setUp(self):
        self.factory = RequestFactory()

    def test_x_real_ip_wins_over_spoofed_xff(self):
        """X-Real-IP 由本方 Nginx 覆盖设置，优先于 XFF（含客户端伪造值）。"""
        request = self.factory.get(
            '/admin/',
            HTTP_X_REAL_IP='5.6.7.8',
            HTTP_X_FORWARDED_FOR='1.2.3.4, 5.6.7.8',
        )
        self.assertEqual(_client_ip(request), '5.6.7.8')

    def test_xff_last_entry_when_no_x_real_ip(self):
        """无 X-Real-IP 时取 XFF 末项（本代理追加的真实 IP），不取首项。"""
        request = self.factory.get('/admin/', HTTP_X_FORWARDED_FOR='1.2.3.4, 5.6.7.8')
        self.assertEqual(_client_ip(request), '5.6.7.8')

    def test_remote_addr_fallback(self):
        """无任何代理头时回退 REMOTE_ADDR。"""
        request = self.factory.get('/admin/')
        self.assertEqual(_client_ip(request), '127.0.0.1')


class AdminWhitelistTest(SimpleTestCase):
    """白名单拦截行为。"""

    def setUp(self):
        self.factory = RequestFactory()
        self.mw = admin_ip_whitelist(lambda request: HttpResponse("ok"))

    @override_settings(ADMIN_ALLOWED_IPS=['5.6.7.8'])
    def test_spoofed_xff_first_entry_cannot_bypass(self):
        """伪造 XFF 首项为白名单 IP，真实 IP 不在名单 → 仍 403。"""
        request = self.factory.get('/admin/', HTTP_X_FORWARDED_FOR='5.6.7.8, 9.9.9.9')
        response = self.mw(request)
        self.assertEqual(response.status_code, 403)

    @override_settings(ADMIN_ALLOWED_IPS=['5.6.7.8'])
    def test_allowed_real_ip_passes(self):
        request = self.factory.get('/admin/', HTTP_X_REAL_IP='5.6.7.8')
        response = self.mw(request)
        self.assertEqual(response.status_code, 200)

    @override_settings(ADMIN_ALLOWED_IPS=['5.6.7.8'])
    def test_denied_ip_gets_403(self):
        request = self.factory.get('/admin/', HTTP_X_REAL_IP='9.9.9.9')
        response = self.mw(request)
        self.assertEqual(response.status_code, 403)

    @override_settings(ADMIN_ALLOWED_IPS=[''])
    def test_empty_string_entries_do_not_lock_out(self):
        """ADMIN_ALLOWED_IPS 设为空值时解析可能得到 ['']，应视为未配置白名单放行。"""
        request = self.factory.get('/admin/')
        response = self.mw(request)
        self.assertEqual(response.status_code, 200)

    @override_settings(ADMIN_ALLOWED_IPS=['5.6.7.8'])
    def test_non_admin_path_unaffected(self):
        request = self.factory.get('/api/policies/')
        response = self.mw(request)
        self.assertEqual(response.status_code, 200)
