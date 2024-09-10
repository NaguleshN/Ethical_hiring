from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home , name ="home"),
    path('login/', views.login , name ="login"),
    path("logout/",views.logout_view , name="logout"),
    path("success/", views.success ,name ="success"),
    path("response/", views.response ,name ="response"),
    path("dashboard/", views.admin_dashboard ,name ="dashboard"),
    path("upload_creteria/", views.upload_creteria ,name ="upload_creteria"),
    path("send_mail/<int:id>", views.send_mail ,name ="send_mail"),
]
