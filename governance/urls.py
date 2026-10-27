from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('review/<int:pk>/', views.review_detail_view, name='review_detail'),
]