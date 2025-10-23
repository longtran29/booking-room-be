# Use official Python base image
FROM python:3.13-alpine

RUN apk add --no-cache bash

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project files
COPY . .

RUN chmod +x wait-for-it.sh