#!/bin/bash

echo "=== QuantumAlpha India Setup ==="
echo ""

echo "Step 1: Starting database and Redis..."
docker-compose up -d db redis
sleep 5

echo ""
echo "Step 2: Running database migrations..."
cd backend
alembic upgrade head

echo ""
echo "Step 3: Starting backend server..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
