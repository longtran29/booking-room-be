from django.shortcuts import render
import uuid
import os
import stripe
from decimal import Decimal
from rest_framework.decorators import api_view
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .models import Room, Booking, Payment
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from rest_framework.permissions import AllowAny
from pydantic import ValidationError
from .schemas import (
    RoomSchema,
    BookingCreateSchema,
    BookingResponseSchema,
    PaymentIntentCreateSchema,
    PaymentIntentResponseSchema,
    ErrorResponseSchema,
)
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Booking hold time in minutes
BOOKING_HOLD_MINUTES = 30


@api_view(["POST"])
@permission_classes([AllowAny])
def register_user(request):
    email = request.data.get("email")
    password = request.data.get("password")
    confirm_password = request.data.get("confirm_password")

    if not email or not password or not confirm_password:
        return Response(
            {"error": "All fields are required."}, status=status.HTTP_400_BAD_REQUEST
        )

    if password != confirm_password:
        return Response(
            {"error": "Password and confirm password do not match"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(email=email).exists():
        return Response(
            {"error": "Email already registered"}, status=status.HTTP_400_BAD_REQUEST
        )

    user = User.objects.create_user(username=email, email=email, password=password)

    return Response(
        {"message": "Registration successful", "user_id": user.id},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def login_with_email(request):
    try:
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response(
                {"error": "Email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid email or password"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = authenticate(username=user.username, password=password)

        if user is not None:
            refresh = RefreshToken.for_user(user)

            response = Response(
                {
                    "message": "Login successful",
                    "user_id": user.id,
                    "email": user.email,
                    "is_staff": user.is_staff,
                    "is_superuser": user.is_superuser,
                    "access": str(refresh.access_token),
                }
            )

            # Set refresh token as HTTP-only cookie
            response.set_cookie(
                key='refresh_token',
                value=str(refresh),
                httponly=True,
                secure=settings.DEBUG is False,  # True in production (HTTPS), False in dev
                samesite='Lax',  # CSRF protection
                max_age=60 * 60 * 24 * 7  # 7 days
            )

            return response
        else:
            return Response(
                {"error": "Invalid email or password"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
    except Exception as e:
        return Response(
            {"error": "Login failed", "detail": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_user(request):
    """
    Logout user by clearing refresh token cookie
    POST /api/logout
    """
    try:
        response = Response(
            {"message": "Logout successful"},
            status=status.HTTP_200_OK
        )

        # Clear refresh token cookie
        response.delete_cookie('refresh_token')

        return response

    except Exception as e:
        return Response(
            {"error": "Logout failed", "detail": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def refresh_access_token(request):
    """
    Refresh access token using HTTP-only cookie
    POST /api/token/refresh-cookie
    """
    try:
        # Get refresh token from cookie
        refresh_token = request.COOKIES.get('refresh_token')

        if not refresh_token:
            return Response(
                {"error": "Refresh token not found"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Verify and refresh token
        refresh = RefreshToken(refresh_token)
        access_token = str(refresh.access_token)

        return Response(
            {
                "access": access_token,
                "message": "Token refreshed successfully"
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response(
            {"error": "Token refresh failed", "detail": str(e)},
            status=status.HTTP_401_UNAUTHORIZED
        )


# ============================================
# Booking Service APIs
# ============================================


@api_view(["GET"])
@permission_classes([AllowAny])
def list_rooms(request):
    """
    List all available rooms/services with time slot information
    GET /api/rooms
    """
    try:
        rooms_data = list(Room.objects.filter(is_available=True).values())

        return Response(
            {"count": len(rooms_data), "rooms": rooms_data}, status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response(
            {"error": "Failed to fetch rooms", "detail": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def calculate_slots_and_amount(start_time, end_time, room):
    """Calculate number of slots and total amount based on time range"""
    from datetime import datetime, timedelta

    # Convert times to datetime for calculation
    start_dt = datetime.combine(datetime.today(), start_time)
    end_dt = datetime.combine(datetime.today(), end_time)

    # Calculate duration in minutes
    duration_minutes = (end_dt - start_dt).total_seconds() / 60

    # Calculate number of slots (each slot is room.slot_duration_minutes)
    number_of_slots = int(duration_minutes / room.slot_duration_minutes)

    # Calculate total amount
    total_amount = room.price_per_slot * number_of_slots

    return number_of_slots, total_amount


def check_time_slot_overlap(
    room, booking_date, start_time, end_time, exclude_booking_id=None
):
    """Check if the requested time slot overlaps with existing bookings"""
    from datetime import datetime

    # Get all confirmed or pending bookings for this room on this date
    bookings = Booking.objects.filter(
        room=room, booking_date=booking_date, status__in=["pending", "confirmed"]
    )

    if exclude_booking_id:
        bookings = bookings.exclude(id=exclude_booking_id)

    # Convert to datetime for comparison
    start_dt = datetime.combine(booking_date, start_time)
    end_dt = datetime.combine(booking_date, end_time)

    for booking in bookings:
        existing_start = datetime.combine(booking_date, booking.start_time)
        existing_end = datetime.combine(booking_date, booking.end_time)

        # Check for overlap
        if start_dt < existing_end and end_dt > existing_start:
            return True, booking

    return False, None


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_booking(request):
    """
    Create a new booking with time slots
    POST /api/bookings
    Body: {
        "user_id": int,
        "room_id": int,
        "booking_date": "YYYY-MM-DD",
        "start_time": "HH:MM:SS",
        "end_time": "HH:MM:SS",
        "guest_count": int,
        "special_requests": "string" (optional)
    }
    """
    try:
        # Validate input data with Pydantic
        booking_data = BookingCreateSchema(**request.data)

        # Get user from request (authenticated user)
        user = request.user
        if not user or not user.is_authenticated:
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Use transaction with row-level locking for concurrent booking handling
        with transaction.atomic():
            # Lock the room row for update to prevent race conditions
            try:
                room = Room.objects.select_for_update().get(
                    id=booking_data.room_id, is_available=True
                )
            except Room.DoesNotExist:
                return Response(
                    {"error": "Room not found or not available"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Validate time slots are within room operating hours
            if (
                booking_data.start_time < room.opening_time
                or booking_data.end_time > room.closing_time
            ):
                return Response(
                    {
                        "error": f"Booking time must be between {room.opening_time.strftime('%H:%M')} and {room.closing_time.strftime('%H:%M')}"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Calculate number of slots and total amount
            number_of_slots, total_amount = calculate_slots_and_amount(
                booking_data.start_time, booking_data.end_time, room
            )

            if number_of_slots < 1:
                return Response(
                    {"error": "Booking duration must be at least one slot"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check for time slot overlap
            has_overlap, conflicting = check_time_slot_overlap(
                room,
                booking_data.booking_date,
                booking_data.start_time,
                booking_data.end_time,
            )

            if has_overlap:
                return Response(
                    {
                        "error": "Time slot conflicts with existing booking",
                        "conflicting_booking": {
                            "start_time": conflicting.start_time.strftime("%H:%M"),
                            "end_time": conflicting.end_time.strftime("%H:%M"),
                        },
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            # Verify guest count doesn't exceed capacity
            if booking_data.guest_count > room.capacity:
                return Response(
                    {"error": f"Guest count exceeds room capacity of {room.capacity}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Calculate hold expiration time (30 minutes from now)
            hold_expires_at = timezone.now() + timedelta(minutes=BOOKING_HOLD_MINUTES)

            # Create booking with hold expiration
            booking = Booking.objects.create(
                user=user,
                room=room,
                booking_date=booking_data.booking_date,
                start_time=booking_data.start_time,
                end_time=booking_data.end_time,
                guest_count=booking_data.guest_count,
                total_amount=total_amount,
                number_of_slots=number_of_slots,
                special_requests=booking_data.special_requests,
                status="pending",
                payment_status="pending",
                hold_expires_at=hold_expires_at,
            )

            # Prepare response
            from django.db.models import F

            response_data = (
                Booking.objects.filter(id=booking.id)
                .annotate(
                    user_name=F("user__username"),
                    user_email=F("user__email"),
                    room_name=F("room__name"),
                )
                .values()
                .first()
            )

        return Response(response_data, status=status.HTTP_201_CREATED)

    except ValidationError as e:
        return Response(
            {"error": "Validation failed", "detail": e.errors()},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        return Response(
            {"error": "Failed to create booking", "detail": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_payment_intent(request):
    """
    Create a Stripe payment intent for a booking
    POST /api/payment-intent
    Body: {
        "booking_id": int,
        "amount": decimal,
        "currency": "usd" (optional)
    }
    """
    try:
        # Validate input data with Pydantic
        payment_data = PaymentIntentCreateSchema(**request.data)

        # Get booking
        try:
            booking = Booking.objects.get(id=payment_data.booking_id)
        except Booking.DoesNotExist:
            return Response(
                {"error": "Booking not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Check if booking already has a successful payment
        if booking.payment_status == "succeeded":
            return Response(
                {"error": "Booking already paid"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Create Stripe PaymentIntent
        # Stripe expects amount in cents
        amount_cents = int(payment_data.amount * 100)

        payment_intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=payment_data.currency,
            metadata={
                "booking_id": booking.id,
                "user_id": booking.user.id,
                "room_name": booking.room.name,
            },
            automatic_payment_methods={
                "enabled": True,
            },
        )

        # Create or update Payment record
        payment, created = Payment.objects.update_or_create(
            booking=booking,
            defaults={
                "stripe_payment_intent_id": payment_intent.id,
                "amount": payment_data.amount,
                "currency": payment_data.currency,
                "status": payment_intent.status,
                "metadata": {"client_secret": payment_intent.client_secret},
            },
        )

        # Update booking payment status
        booking.payment_status = "processing"
        booking.save()

        # Prepare response
        response_data = PaymentIntentResponseSchema(
            payment_intent_id=payment_intent.id,
            client_secret=payment_intent.client_secret,
            amount=payment_data.amount,
            currency=payment_data.currency,
            status=payment_intent.status,
            booking_id=booking.id,
        )

        return Response(response_data.model_dump(), status=status.HTTP_201_CREATED)

    except ValidationError as e:
        return Response(
            {"error": "Validation failed", "detail": e.errors()},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except stripe.error.StripeError as e:
        return Response(
            {"error": "Payment processing failed", "detail": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        return Response(
            {"error": "Failed to create payment intent", "detail": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_booking(request, booking_id):
    """
    Get a specific booking by ID
    GET /api/bookings/:booking_id
    """
    try:
        from django.db.models import F

        # Get booking with user and room details
        booking_data = (
            Booking.objects.filter(id=booking_id)
            .annotate(
                user_name=F("user__username"),
                user_email=F("user__email"),
                room_name=F("room__name"),
            )
            .values()
            .first()
        )

        if not booking_data:
            return Response(
                {"error": "Booking not found"}, status=status.HTTP_404_NOT_FOUND
            )

        return Response(booking_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": "Failed to fetch booking", "detail": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def stripe_webhook(request):
    """
    Handle Stripe webhook events
    POST /api/stripe-webhook
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        return Response(
            {"error": "Invalid payload"}, status=status.HTTP_400_BAD_REQUEST
        )
    except stripe.error.SignatureVerificationError:
        return Response(
            {"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST
        )

    # Handle the event
    if event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]

        try:
            # Update payment and booking status
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent["id"])
            payment.status = "succeeded"
            payment.payment_method = payment_intent.get("payment_method")
            payment.save()

            booking = payment.booking
            booking.payment_status = "succeeded"
            booking.status = "confirmed"
            booking.save()

        except Payment.DoesNotExist:
            pass

    elif event["type"] == "payment_intent.payment_failed":
        payment_intent = event["data"]["object"]

        try:
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent["id"])
            payment.status = "failed"
            payment.save()

            booking = payment.booking
            booking.payment_status = "failed"
            booking.save()

        except Payment.DoesNotExist:
            pass

    elif event["type"] == "payment_intent.canceled":
        payment_intent = event["data"]["object"]

        try:
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent["id"])
            payment.status = "canceled"
            payment.save()

            booking = payment.booking
            # Check if hold has expired
            if booking.is_hold_expired():
                booking.status = "expired"
            else:
                booking.status = "cancelled"
            booking.payment_status = "failed"
            booking.save()

        except Payment.DoesNotExist:
            pass

    return Response({"status": "success"}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_all_bookings(request):
    """
    Get all bookings (Staff/Admin only)
    GET /api/bookings/all
    """
    try:
        # Check if user is staff/admin
        if not request.user.is_staff:
            return Response(
                {"error": "Permission denied. Admin access required."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get all bookings with user and room details
        from django.db.models import F

        bookings_data = list(
            Booking.objects.select_related("room", "user")
            .annotate(
                user_name=F("user__username"),
                user_email=F("user__email"),
                room_name=F("room__name"),
            )
            .order_by("-created_at")
            .values()
        )

        return Response(
            {
                "count": len(bookings_data),
                "bookings": bookings_data,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {"error": "Failed to fetch bookings", "detail": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
