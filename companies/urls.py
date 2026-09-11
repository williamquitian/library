from django.urls import path
from . import views

urlpatterns = [
    path('list', views.list, name="companies-list"),
    path('create', views.create, name="companies-create"),
    path('edit/<int:pk>', views.edit, name="companies-edit"),
    path('get_company_info', views.get_company_info, name="get_company_info"),
]
