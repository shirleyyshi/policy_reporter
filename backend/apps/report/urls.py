from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    path('health/', views.health, name='health'),
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/register/', views.register, name='register'),
    path('auth/me/', views.me, name='me'),
    path('policies/', views.policy_list, name='policy_list'),
    path('policies/detail/', views.policy_detail, name='policy_detail'),
    path('export/', views.policy_export, name='policy_export'),
    path('policy-counts/', views.policy_counts, name='policy_counts'),
    path('policy-dates/', views.policy_dates, name='policy_dates'),
]
