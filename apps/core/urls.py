from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path("register/", views.register_user, name="register_user"),
    path("login/", views.login_with_email, name="login_with_email"),
    path("logout/", views.logout_user, name="logout_user"),
    path("token/refresh-cookie/", views.refresh_access_token, name="refresh_access_token"),
    # Booking Service APIs
    path("rooms/", views.list_rooms, name="list_rooms"),
    path("bookings/", views.create_booking, name="create_booking"),
    path("bookings/all/", views.get_all_bookings, name="get_all_bookings"),
    path("bookings/<int:booking_id>/", views.get_booking, name="get_booking"),
    path("payment-intent/", views.create_payment_intent, name="create_payment_intent"),
    path("stripe-webhook/", views.stripe_webhook, name="stripe_webhook"),
]
