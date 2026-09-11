from django.urls import path
from . import views

urlpatterns = [
    path('list', views.list, name="tasks-list"),
    path('create', views.create, name="tasks-create"),
    path('detail/<int:pk>/', views.detail, name='task-detail'),
    path('list_ajax', views.list_ajax, name="tasks-list-ajax"),
    path('view_file/<int:pk>/', views.view_file, name='task-view-file'),
]
