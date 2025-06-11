# assistant/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.submit_audio, name='submit_audio'), # Our main submission page
    path('success/', views.submission_success, name='submission_success'), # Success page
]