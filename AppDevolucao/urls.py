from django.urls import path
from . import views

urlpatterns = [
    path('', views.verificar_e_devolver, name='verificar_e_devolver'),
]
