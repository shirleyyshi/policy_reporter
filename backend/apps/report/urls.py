from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', views.me, name='me'),
    path('policies/', views.get_policies, name='get_policies'),
    path('policies/detail/', views.policy_detail, name='policy_detail'),
    path('export/', views.export_policies, name='export_policies'),
    path('policy-counts/', views.get_policy_counts, name='policy-counts'),
]
