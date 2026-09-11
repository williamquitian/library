from django.urls import path

from . import views

urlpatterns = [
    path('personal', views.personal, name="balance-personal"),
    path('diario', views.diario, name="balance-diario"),
    path('mensual', views.mensual, name="balance-mensual"),
    path('movimiento/nuevo', views.movement_create, name="balance-movement-create"),
    path('movimiento/<int:pk>/eliminar', views.movement_delete, name="balance-movement-delete"),
]
