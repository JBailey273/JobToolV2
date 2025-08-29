from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.contractor_summary, name='contractor_summary'),
    path('projects/', views.project_list, name='project_list'),
    path('projects/<int:pk>/', views.project_detail, name='project_detail'),
    path('projects/<int:pk>/add-entry/', views.add_job_entry, name='add_job_entry'),
    path('projects/<int:pk>/add-payment/', views.add_payment, name='add_payment'),
    path('reports/contractor/', views.contractor_report, name='contractor_report'),
    path('projects/<int:pk>/customer-report/', views.customer_report, name='customer_report'),
]
