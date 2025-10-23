from django.db import models
from django.contrib.auth.models import User


class Room(models.Model):
    """Model for rooms/services available for booking"""

    name = models.CharField(max_length=255)
    description = models.TextField()
    price_per_slot = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price per 30-minute slot")
    capacity = models.IntegerField()
    amenities = models.JSONField(default=list, blank=True)
    is_available = models.BooleanField(default=True)
    slot_duration_minutes = models.IntegerField(default=30, help_text="Duration of each time slot in minutes")
    opening_time = models.TimeField(default="09:00:00", help_text="Daily opening time")
    closing_time = models.TimeField(default="18:00:00", help_text="Daily closing time")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]


class Booking(models.Model):
    """Model for bookings"""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
        ("completed", "Completed"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("succeeded", "Succeeded"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="bookings")
    booking_date = models.DateField()
    start_time = models.TimeField(help_text="Booking start time")
    end_time = models.TimeField(help_text="Booking end time")
    guest_count = models.IntegerField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    number_of_slots = models.IntegerField(default=1, help_text="Number of 30-minute slots booked")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="pending"
    )
    special_requests = models.TextField(blank=True, null=True)
    hold_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.room.name} - {self.booking_date} ({self.start_time}-{self.end_time})"

    def is_hold_expired(self):
        """Check if the booking hold has expired"""
        from django.utils import timezone
        if self.hold_expires_at and self.status == 'pending' and self.payment_status == 'pending':
            return timezone.now() > self.hold_expires_at
        return False

    class Meta:
        ordering = ["-created_at"]


class Payment(models.Model):
    """Model for payment transactions"""

    booking = models.OneToOneField(
        Booking, on_delete=models.CASCADE, related_name="payment"
    )
    stripe_payment_intent_id = models.CharField(max_length=255, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="usd")
    status = models.CharField(max_length=50)
    payment_method = models.CharField(max_length=100, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment for {self.booking.id} - {self.status}"

    class Meta:
        ordering = ["-created_at"]
