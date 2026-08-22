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
        # 过滤空串：ADMIN_ALLOWED_IPS 设为空值时解析可能得到 ['']，会误拦截所有人
        allowed_ips = [ip for ip in getattr(settings, 'ADMIN_ALLOWED_IPS', []) if ip]
        # 只在配置了白名单时启用拦截；空列表 = 开发环境放行
        if allowed_ips and request.path.startswith('/admin/'):
            client_ip = _client_ip(request)
            if client_ip not in allowed_ips:
                return HttpResponseForbidden("Access denied.", content_type="text/plain")
        return get_response(request)

    return middleware


def _client_ip(request):
    """取真实客户端 IP。

    优先 X-Real-IP：由我们自己的 Nginx 设置（proxy_set_header X-Real-IP $remote_addr），
    客户端伪造的值会被覆盖，不可绕过。
    回退 X-Forwarded-For 最后一项（由本代理追加），再回退 REMOTE_ADDR。
    不取 XFF 首项——那是客户端可自带的可伪造值。
    """
    real_ip = request.META.get('HTTP_X_REAL_IP', '').strip()
    if real_ip:
        return real_ip
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[-1].strip()
    return request.META.get('REMOTE_ADDR', '')
