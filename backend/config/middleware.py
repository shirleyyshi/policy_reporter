"""
Django admin IP 白名单中间件。

生产环境通过 ADMIN_ALLOWED_IPS 限制 /admin/ 只能从指定 IP 访问，
防止公网暴力破解 Django admin。

配置（settings.py）：
    ADMIN_ALLOWED_IPS = env.list('ADMIN_ALLOWED_IPS', default=[])

环境变量（.env）：
    ADMIN_ALLOWED_IPS=1.2.3.4,5.6.7.8

若 ADMIN_ALLOWED_IPS 为空（开发环境），中间件放行所有请求。
"""
from django.conf import settings
from django.http import HttpResponseForbidden


def admin_ip_whitelist(get_response):
    """拦截 /admin/ 路径，仅放行白名单 IP。"""

    def middleware(request):
        allowed_ips = getattr(settings, 'ADMIN_ALLOWED_IPS', [])
        # 只在配置了白名单时启用拦截；空列表 = 开发环境放行
        if allowed_ips and request.path.startswith('/admin/'):
            # nginx 反代场景取 X-Forwarded-For 首个 IP，否则取 REMOTE_ADDR
            forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
            client_ip = forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR', '')
            if client_ip not in allowed_ips:
                return HttpResponseForbidden("Access denied.", content_type="text/plain")
        return get_response(request)

    return middleware
