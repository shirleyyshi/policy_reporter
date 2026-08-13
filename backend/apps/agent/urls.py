from django.urls import path
from . import views

urlpatterns = [
    path('run/', views.agent_run, name='agent_run'),
    path('runs/', views.agent_runs_list, name='agent_runs_list'),
    path('runs/<uuid:run_id>/', views.agent_trace, name='agent_trace'),
    path('runs/<uuid:run_id>/answer/', views.agent_answer, name='agent_answer'),
    path('runs/<uuid:run_id>/download/', views.agent_download, name='agent_download'),
]
