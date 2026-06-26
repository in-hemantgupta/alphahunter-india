#!/bin/bash

echo "=== QuantumAlpha India - Local Development Setup ==="
echo ""

echo "Step 1: Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo ""
echo "Step 2: Installing dependencies..."
cd backend
pip install -r requirements.txt

echo ""
echo "Step 3: Starting PostgreSQL (make sure it's running on localhost:5432)..."
echo "If not running, start it with: brew services start postgresql"
echo ""

echo "Step 4: Creating database..."
psql -U postgres -c "CREATE DATABASE alphahunter;" 2>/dev/null || echo "Database may already exist"

echo ""
echo "Step 5: Running migrations..."
alembic upgrade head

echo ""
echo "Step 6: Starting server..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
