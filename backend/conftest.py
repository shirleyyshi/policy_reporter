"""Pytest 共享 fixtures。

所有测试文件可复用这里的 fixture，避免每个 tests.py 重复造数据。
"""
import pytest


@pytest.fixture
def user(db):
    """创建普通用户。"""
    from django.contrib.auth.models import User
    return User.objects.create_user(username='testuser', password='testpass123')


@pytest.fixture
def auth_client(user):
    """已登录认证的 DRF APIClient。"""
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_user(db):
    """创建超级用户。"""
    from django.contrib.auth.models import User
    return User.objects.create_superuser(username='admin', password='adminpass123', email='admin@test.com')


@pytest.fixture
def admin_client(admin_user):
    """已登录超管的 DRF APIClient。"""
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client
