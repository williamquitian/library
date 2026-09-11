from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name=""),
    path('login/', views.login, name="accounts-login"),
    path('logout/', views.logout, name="accounts-logout"),
    path('list/', views.list, name="accounts-list"),
    path('new/', views.new, name="accounts-new"),
    path('update/<int:pk>', views.update, name="accounts-update"),
    path('password_update/', views.password_update, name="password-update"),
]
