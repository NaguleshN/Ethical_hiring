from django.contrib import admin
from django.urls import path ,include
from . import views

urlpatterns = [
    path('screen/', views.screen, name='screen'),
    path('upload/', views.upload_video, name='upload_video'),
    path("completed/",views.completed_task, name ="completed"),
    path('verify_face/', views.verify_face_view, name='verify_face'),
    path('upload_aadhaar/', views.upload_aadhaar_view, name='upload_aadhaar'),
]