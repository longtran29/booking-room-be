# Booking Service API

A Django-based booking service application with time slot management, Stripe payment integration, and secure JWT authentication.

## Test Accounts

**Regular User:**
- Email: `longtran20014@gmail.com`
- Password: `123456Long`

**Staff/Admin User:**
- Email: `admin@gmail.com`
- Password: `123456Long`

**Stripe Test Cards:**
- **Valid Card (Success)**: `4242 4242 4242 4242` - Exp: `03/29` - CVC: `333`
- **Insufficient Funds (Decline)**: `4000 0000 0000 9995` - Exp: `03/29` - CVC: `333`

## Overview

This application provides a complete booking system for rooms/services with the following features:

- **Time Slot Management**: Book rooms in 30-minute slots with customizable time ranges
- **Stripe Payment Integration**: Secure payment processing with PaymentIntent API
- **JWT Authentication**: Access and refresh tokens with HTTP-only cookie security
- **Admin Dashboard**: Staff-only endpoint to view all bookings

## Technology Stack

- **Backend**: Django 5.2.2 + Django REST Framework
- **Database**: PostgreSQL (via Supabase or local)
- **Payment**: Stripe API
- **Authentication**: JWT with simplejwt
- **Containerization**: Docker + Docker Compose
- **Validation**: Pydantic

## Local Setup with Docker

### Prerequisites

- Docker & Docker Compose installed
- Stripe account (for payment integration)
- Supabase account (optional, for remote PostgreSQL)

### 1. Clone Repository

```bash
git clone <repository-url>
cd CSV_UPLOAD
```

### 2. Environment Configuration

Copy the example environment file and update with your credentials:

```bash
cp .env.example .env
```

Edit `.env` file with your settings:

```env
# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/booking_db

# Supabase Configuration (optional)
PUBLIC_SUPABASE_URL=your_supabase_url_here
PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key_here

# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
STRIPE_CALLBACK_SUCCESS_URL=http://localhost:8000/payment/success
STRIPE_CALLBACK_CANCEL_URL=http://localhost:8000/payment/cancel

# Django Configuration
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=True
```

### 3. Create .env.example

```bash
cat > .env.example << 'EOF'
# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/booking_db

# Supabase Configuration
PUBLIC_SUPABASE_URL=your_supabase_url_here
PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key_here

# Stripe Configuration
STRIPE_SECRET_KEY=your_stripe_secret_key_here
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret_here
STRIPE_CALLBACK_SUCCESS_URL=http://localhost:8000/payment/success
STRIPE_CALLBACK_CANCEL_URL=http://localhost:8000/payment/cancel

# Django Configuration
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=True
EOF
```

### 4. Build and Run with Docker

```bash
# Build and start containers
docker-compose up --build

# Or run in detached mode
docker-compose up -d --build
```

The API will be available at: `http://localhost:8000`

### 5. Create Superuser (Admin)

```bash
docker-compose exec web python manage.py createsuperuser
```

### 6. Access Admin Panel

Visit: `http://localhost:8000/admin`

## API Documentation

### Authentication APIs

#### Register User
```http
POST /api/register/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "yourpassword",
  "confirm_password": "yourpassword"
}
```

**Response:**
```json
{
  "message": "Registration successful",
  "user_id": 1
}
```

#### Login
```http
POST /api/login/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

**Response:**
```json
{
  "message": "Login successful",
  "user_id": 1,
  "email": "user@example.com",
  "is_staff": false,
  "is_superuser": false,
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Note**: Refresh token is set as HTTP-only cookie automatically.

#### Refresh Access Token
```http
POST /api/token/refresh-cookie/
```

**Response:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "message": "Token refreshed successfully"
}
```

#### Logout
```http
POST /api/logout/
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "message": "Logout successful"
}
```

### Booking Service APIs

All booking endpoints require authentication via `Authorization: Bearer <access_token>` header.

#### 1. List Available Rooms
```http
GET /api/rooms/
```

**Response:**
```json
{
  "count": 2,
  "rooms": [
    {
      "id": 1,
      "name": "Conference Room A",
      "description": "Large conference room",
      "price_per_slot": 50.00,
      "capacity": 10,
      "amenities": ["WiFi", "Projector", "Whiteboard"],
      "is_available": true,
      "slot_duration_minutes": 30,
      "opening_time": "09:00:00",
      "closing_time": "18:00:00"
    }
  ]
}
```

#### 2. Create Booking
```http
POST /api/bookings/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "user_id": 1,
  "room_id": 1,
  "booking_date": "2025-10-25",
  "start_time": "09:00:00",
  "end_time": "10:00:00",
  "guest_count": 5,
  "special_requests": "Need projector setup"
}
```

**Response:**
```json
{
  "id": 1,
  "user_id": 1,
  "user_name": "user@example.com",
  "user_email": "user@example.com",
  "room_id": 1,
  "room_name": "Conference Room A",
  "booking_date": "2025-10-25",
  "start_time": "09:00:00",
  "end_time": "10:00:00",
  "guest_count": 5,
  "total_amount": 100.00,
  "number_of_slots": 2,
  "status": "pending",
  "payment_status": "pending",
  "hold_expires_at": "2025-10-25T09:30:00Z"
}
```

#### 3. Create Payment Intent
```http
POST /api/payment-intent/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "booking_id": 1,
  "amount": 100.00,
  "currency": "usd"
}
```

**Response:**
```json
{
  "payment_intent_id": "pi_xxxxxxxxxxxxx",
  "client_secret": "pi_xxxxxxxxxxxxx_secret_xxxxxxxxxxxxx",
  "amount": 100.00,
  "currency": "usd",
  "status": "requires_payment_method",
  "booking_id": 1
}
```

#### 4. Get Specific Booking
```http
GET /api/bookings/1/
Authorization: Bearer <access_token>
```

#### 5. Get All Bookings (Admin Only)
```http
GET /api/bookings/all/
Authorization: Bearer <admin_access_token>
```

**Response:**
```json
{
  "count": 25,
  "bookings": [...]
}
```

**Note**: Returns 403 Forbidden if user is not staff.

### Stripe Webhook
```http
POST /api/stripe-webhook/
Stripe-Signature: <signature>
```

Handles events:
- `payment_intent.succeeded` - Confirms booking
- `payment_intent.payment_failed` - Marks payment as failed

## Extra Features

### Automatic Room Release

**How it works:**

1. When a booking is created, a **30-minute hold** is placed on the room
2. The `hold_expires_at` timestamp is set to current time + 30 minutes
3. If payment is not completed within 30 minutes:
   - The booking status automatically changes to `expired`
   - The room becomes available again for other customers
   - Stripe PaymentIntent is canceled (if exists)

**Implementation:**

- **During Booking Creation**: Expired bookings are automatically cleaned up before checking availability
- **Webhook Handler**: Handles `payment_intent.canceled` events to expire bookings

**Manual Cleanup (Optional):**

You can also schedule a cleanup task to run periodically:

```bash
# Add to crontab (runs every 5 minutes)
*/5 * * * * curl -X POST http://localhost:8000/api/cleanup-expired-bookings
```

### Security Features

1. **HTTP-Only Cookies**: Refresh tokens stored in secure, HTTP-only cookies
2. **CSRF Protection**: SameSite cookie attribute
3. **JWT Authentication**: Short-lived access tokens (30 min)
4. **Row-Level Locking**: Prevents race conditions during concurrent bookings

## Database Schema

### Models

**Room**
- `name`: Room/service name
- `price_per_slot`: Price per 30-minute slot
- `capacity`: Maximum guests
- `slot_duration_minutes`: Duration of each slot (default: 30)
- `opening_time`: Daily opening time
- `closing_time`: Daily closing time

**Booking**
- `user`: Foreign key to User
- `room`: Foreign key to Room
- `booking_date`: Date of booking
- `start_time`: Booking start time
- `end_time`: Booking end time
- `number_of_slots`: Number of 30-min slots
- `total_amount`: Total payment amount
- `status`: pending/confirmed/expired/cancelled/completed
- `payment_status`: pending/processing/succeeded/failed
- `hold_expires_at`: When the booking hold expires

**Payment**
- `booking`: One-to-one with Booking
- `stripe_payment_intent_id`: Stripe PaymentIntent ID
- `amount`: Payment amount
- `currency`: Payment currency
- `status`: Payment status from Stripe

## Troubleshooting

### Common Issues

**Database Connection Error:**
```bash
# Check if PostgreSQL is running
docker-compose ps

# View logs
docker-compose logs postgres
```

**Migration Issues:**
```bash
# Reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up --build
```

**Port Already in Use:**
```bash
# Change port in docker-compose.yml
ports:
  - "8001:8000"  # Use 8001 instead
```

## Development

### Run Tests
```bash
docker-compose exec web python manage.py test
```

### Create Migrations
```bash
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate
```

### Shell Access
```bash
docker-compose exec web python manage.py shell
```

## Production Deployment

For production, update these settings:

1. Set `DEBUG=False` in `.env`
2. Set `secure=True` for cookies (HTTPS required)
3. Update `ALLOWED_HOSTS` in settings
4. Use proper Stripe live keys
5. Configure CORS for your frontend domain
6. Set strong `DJANGO_SECRET_KEY`
7. Use managed PostgreSQL (Supabase, AWS RDS, etc.)

## License

MIT License

## Support

For issues or questions, please open an issue in the repository.
