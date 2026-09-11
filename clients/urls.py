from django.urls import path
from . import views, views_checks

urlpatterns = [
    path('list_clients', views.list_clients, name="clients-list"),
    path('mobile_search_client', views.mobile_search_client, name="mobile_search_client"),
    path('mobile_upload_document/<int:pk>', views.mobile_upload_document, name="mobile_upload_document"),
    path('list_clients_ajax', views.list_clients_ajax, name="list_clients_ajax"),
    path('create_client', views.create_client, name="create_client"),
    path('view_client/<int:pk>/<str:tab>', views.view_client, name="view_client"),
    path('update_client/<int:pk>', views.update_client, name="update_client"),
    path('add_comment/<int:pk>/<str:tab>', views.add_comment, name="add_comment"),
    path('upload_document/<int:pk>', views.upload_document, name="upload_document"),
    path('view_document/<int:pk>', views.view_document, name='view_document'),
    path('new_transfer_package/<int:pk>', views.new_transfer_package, name='new_transfer_package'),
    path('new_moneyorder/<int:pk>', views.new_moneyorder, name='new_moneyorder'),
    path('report_clients', views.report_clients, name="clients-reports"),
    path('report_send_money_ajax', views.report_send_money_ajax, name="report_send_money_ajax"), 
    path('report_money_order_ajax', views.report_money_order_ajax, name="report_money_order_ajax"), 
    path('new_check/<int:pk>', views_checks.new_check, name='new_check'),
    path('update_check/<int:pk>', views_checks.update_check, name='update_check'),
    path('get_manager_phone', views_checks.get_manager_phone, name='get_manager_phone'),
    path('delete_sendmoney/<int:pk>', views.delete_sendmoney, name="delete_sendmoney"),
    path('delete_check/<int:pk>', views_checks.delete_check, name="delete_check"),
    path('list_returned_check', views_checks.list_returned_check, name="list_returned_check"),
    path('new_return_check', views_checks.new_return_check, name="new_return_check"),
    path('update_return_check/<int:pk>', views_checks.update_return_check, name="update_return_check"),
    path('view_return_check_file/<int:pk>/', views_checks.view_return_check_file, name='return-check-view-file'),
    #Autocomplete URLs
    path('autocomplete/profession/', views.ProfessionAutocomplete.as_view(create_field='name', validate_create=True), name='profession-autocomplete'),
    path('autocomplete/client/', views.ClientAutocomplete.as_view(), name='client-autocomplete'),
    path('autocomplete/company/', views.CompanyAutocomplete.as_view(create_field='name', validate_create=True), name='company-autocomplete'),
]
