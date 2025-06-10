#!/bin/bash
# quick_fix.sh - Quick fix script for MediRecord SIS

echo "🚀 Applying quick fixes to MediRecord SIS..."

# 1. Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p logs media media/documents media/patient_documents static staticfiles
mkdir -p metrics/migrations sessions/migrations
mkdir -p core/management/commands

# 2. Create missing __init__.py files
echo "📄 Creating missing __init__.py files..."
touch metrics/__init__.py
touch metrics/migrations/__init__.py
touch sessions/migrations/__init__.py
touch core/management/__init__.py
touch core/management/commands/__init__.py

# 3. Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "⚙️ Creating .env file..."
    cat > .env << 'EOF'
# Django Configuration
DJANGO_SECRET_KEY=django-insecure-development-key-change-in-production
DEBUG=True

# Database Configuration (SQLite for development)
# POSTGRES_DB=mediserve
# POSTGRES_USER=mediserve
# POSTGRES_PASSWORD=your-password
# POSTGRES_HOST=localhost
# POSTGRES_PORT=5432

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Twilio Configuration
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_VERIFY_SID=your-twilio-verify-sid
TWILIO_WHATSAPP_NUMBER=+14155238886

# N8N Configuration
N8N_BASE_URL=http://localhost:5678
N8N_API_KEY=your-n8n-api-key

# Site Configuration
SITE_PUBLIC_URL=http://localhost:8000

# AI Configuration
GEMINI_API_KEY=your-gemini-api-key

# Vector Database Configuration
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_INDEX_NAME=medirecord-rag
EOF
    echo "✅ Created .env file with defaults"
else
    echo "✅ .env file already exists"
fi

# 4. Try to run Django commands
echo "🐍 Running Django setup commands..."

# Make migrations step by step
echo "Making migrations..."
python manage.py makemigrations --empty core 2>/dev/null || true
python manage.py makemigrations patients 2>/dev/null || echo "⚠️ Patients migrations skipped"
python manage.py makemigrations documents 2>/dev/null || echo "⚠️ Documents migrations skipped"
python manage.py makemigrations rag 2>/dev/null || echo "⚠️ RAG migrations skipped"
python manage.py makemigrations messaging 2>/dev/null || echo "⚠️ Messaging migrations skipped"
python manage.py makemigrations sessions 2>/dev/null || echo "⚠️ Sessions migrations skipped"
python manage.py makemigrations metrics 2>/dev/null || echo "⚠️ Metrics migrations skipped"

# Apply migrations
echo "Applying migrations..."
python manage.py migrate 2>/dev/null || echo "⚠️ Some migrations may have failed"

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput 2>/dev/null || echo "⚠️ Static collection skipped"

echo ""
echo "✅ Quick fixes applied!"
echo ""
echo "📝 Next steps:"
echo "1. Update .env file with your real API keys"
echo "2. Install Redis if not installed: sudo apt install redis-server"
echo "3. Start the server: python manage.py runserver"
echo ""
echo "🔗 After starting the server, visit:"
echo "- Admin: http://localhost:8000/admin/"
echo "- API Docs: http://localhost:8000/swagger/"
echo "- Health Check: http://localhost:8000/api/health/"
echo ""
echo "If you still get errors, check the detailed fix guide!"

# Make the script executable
chmod +x quick_fix.sh