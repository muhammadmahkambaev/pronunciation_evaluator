# assistant/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.submit_audio, name='submit_audio'),
    # Removed submission_success, now going to submission_detail
    path('submission/<int:submission_id>/', views.submission_detail, name='submission_detail'),
    path('submission/not-found/', views.submission_not_found, name='submission_not_found'),
]