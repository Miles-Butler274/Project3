#!/bin/sh
set -e

echo "--- Starting Django Management Tasks ---"

echo "Step 1: Making migrations..."
uv run python manage.py makemigrations
echo "Step 2: Applying migrations..."
uv run python manage.py migrate
echo "Step 3: Starting server..."
uv run python manage.py runserver
