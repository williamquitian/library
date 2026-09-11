from django.urls import path
from . import views

urlpatterns = [
    path('reports_chk', views.reports_chk, name="reports_chk"),
    path('reports_mo', views.reports_mo, name="reports_mo"),
    path('reports_sm', views.reports_sm, name="reports_sm"),
]
