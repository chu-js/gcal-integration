from django.urls import path
from . import views

urlpatterns = [
    path('available_slots', views.get_available_slots),
    path('book_slot', views.book_slot),
    path('update_booking', views.update_booking),
    path('auth', views.auth_test)
]
