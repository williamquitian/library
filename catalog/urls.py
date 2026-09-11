from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("books/add/", views.book_create, name="book_create"),
    path("books/add/dropdown/", views.book_create_dropdown, name="book_create_dropdown"),
    path("books/add/datalist/", views.book_create_datalist, name="book_create_datalist"),
    path("search/<str:model_name>/", views.model_search, name="model_search"),
]
