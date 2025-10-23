from django.contrib import admin
from .models import Room, Booking, Payment


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "price_per_slot",
        "capacity",
        "slot_duration_minutes",
        "opening_time",
        "closing_time",
        "is_available",
        "created_at",
    ]
    list_filter = ["is_available", "created_at"]
    search_fields = ["name", "description"]
    list_editable = ["is_available"]


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "room",
        "booking_date",
        "start_time",
        "end_time",
        "number_of_slots",
        "status",
        "payment_status",
        "total_amount",
        "hold_expires_at",
        "created_at",
    ]
    list_filter = ["status", "payment_status", "booking_date", "created_at"]
    search_fields = ["user__username", "user__email", "room__name"]
    readonly_fields = ["created_at", "updated_at", "hold_expires_at"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "booking",
        "stripe_payment_intent_id",
        "amount",
        "currency",
        "status",
        "created_at",
    ]
    list_filter = ["status", "currency", "created_at"]
    search_fields = ["stripe_payment_intent_id", "booking__id"]
    readonly_fields = ["created_at", "updated_at"]
