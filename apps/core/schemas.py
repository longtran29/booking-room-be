"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import date, time, datetime
from decimal import Decimal


class RoomSchema(BaseModel):
    """Schema for Room data"""
    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=255)
    description: str
    price_per_slot: Decimal = Field(..., gt=0)
    capacity: int = Field(..., gt=0)
    amenities: List[str] = Field(default_factory=list)
    is_available: bool = True
    slot_duration_minutes: int = 30
    opening_time: time
    closing_time: time
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v),
            time: lambda v: v.isoformat(),
        }


class BookingCreateSchema(BaseModel):
    """Schema for creating a booking"""
    user_id: Optional[int] = Field(None, gt=0)
    room_id: int = Field(..., gt=0)
    booking_date: date
    start_time: time
    end_time: time
    guest_count: int = Field(..., gt=0)
    special_requests: Optional[str] = None

    @validator('booking_date')
    def validate_booking_date(cls, v):
        if v < date.today():
            raise ValueError('Booking date cannot be in the past')
        return v

    @validator('end_time')
    def validate_time_range(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('End time must be after start time')
        return v

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            time: lambda v: v.isoformat(),
        }


class BookingResponseSchema(BaseModel):
    """Schema for booking response"""
    id: int
    user_id: int
    user_name: str
    user_email: str
    room_id: int
    room_name: str
    booking_date: date
    start_time: time
    end_time: time
    guest_count: int
    total_amount: Decimal
    number_of_slots: int
    status: str
    payment_status: str
    special_requests: Optional[str] = None
    hold_expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v),
            date: lambda v: v.isoformat(),
            time: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        }


class PaymentIntentCreateSchema(BaseModel):
    """Schema for creating a payment intent"""
    booking_id: int = Field(..., gt=0)
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default='usd', min_length=3, max_length=3)

    @validator('currency')
    def validate_currency(cls, v):
        return v.lower()

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
        }


class PaymentIntentResponseSchema(BaseModel):
    """Schema for payment intent response"""
    payment_intent_id: str
    client_secret: str
    amount: Decimal
    currency: str
    status: str
    booking_id: int

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
        }


class PaymentWebhookSchema(BaseModel):
    """Schema for Stripe webhook payload"""
    type: str
    data: dict

    class Config:
        extra = 'allow'


class ErrorResponseSchema(BaseModel):
    """Schema for error responses"""
    error: str
    detail: Optional[str] = None
    status_code: int


class SuccessResponseSchema(BaseModel):
    """Schema for success responses"""
    message: str
    data: Optional[dict] = None
