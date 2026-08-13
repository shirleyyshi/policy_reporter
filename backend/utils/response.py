"""
统一响应封装：所有 API 返回统一格式
{
    "code": 200,          # 业务状态码（200 成功，非 200 失败）
    "message": "success", # 提示信息
    "data": {}            # 业务数据
}
"""
from rest_framework.response import Response
from rest_framework import status as http_status


def success(data=None, message='success', code=200):
    """成功响应"""
    return Response({
        'code': code,
        'message': message,
        'data': data or {},
    }, status=http_status.HTTP_200_OK)


def error(message='error', code=400, http_code=None):
    """失败响应"""
    return Response({
        'code': code,
        'message': message,
        'data': {},
    }, status=http_code or code)
