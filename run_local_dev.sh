#!/bin/bash
# Local Development Server Runner for bin2nlp
# This script starts the FastAPI server locally with proper environment overrides
# while maintaining compatibility with containerized deployment

# Activate virtual environment
source .env-bin2nlp/bin/activate

# Create a development .env file with local overrides
cp .env .env.dev

# Replace production values with local development values
sed -i 's|STORAGE_BASE_PATH=/var/lib/app/data|STORAGE_BASE_PATH=./data/storage|g' .env.dev
sed -i 's|LOG_FILE_PATH=|LOG_FILE_PATH=./data/logs/app.log|g' .env.dev 
sed -i 's|ENVIRONMENT=production|ENVIRONMENT=development|g' .env.dev
sed -i 's|DEBUG=false|DEBUG=true|g' .env.dev

# Ensure local data directories exist
mkdir -p ./data/storage ./data/logs ./data/uploads

# Clear Python cache to ensure fresh configuration loading
find src -name "*.pyc" -delete 2>/dev/null || true
find src -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Temporarily disable LRU cache on get_settings for development  
cp src/core/config.py src/core/config.py.backup
sed -i 's/@lru_cache()/#@lru_cache()  # Disabled for local development/' src/core/config.py

# Set environment variables to override .env file
export STORAGE_BASE_PATH="$(pwd)/data/storage"
export LOG_FILE_PATH="$(pwd)/data/logs/app.log" 
export ENVIRONMENT="development"
export DEBUG="true"

echo "Environment variables set:"
echo "  STORAGE_BASE_PATH=$STORAGE_BASE_PATH"
echo "  LOG_FILE_PATH=$LOG_FILE_PATH"

# Temporarily rename .env so only .env.dev is loaded
if [ -f .env ]; then
    mv .env .env.production
fi
mv .env.dev .env

echo "🚀 Starting bin2nlp FastAPI server in local development mode..."
echo "📊 Database: PostgreSQL container (localhost:5432)"
echo "💾 Storage: Local directory (./data/storage)"
echo "📝 Logs: Local file (./data/logs/app.log)"
echo "🌐 Server: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo "💡 Config: Using development .env with local overrides"
echo ""

# Cleanup function to restore original .env file and config.py
cleanup() {
    echo "🔄 Restoring production .env file..."
    if [ -f .env ]; then
        rm .env
    fi
    if [ -f .env.production ]; then
        mv .env.production .env
    fi
    echo "✅ Production .env file restored"
    
    echo "🔄 Restoring original config.py file..."
    if [ -f src/core/config.py.backup ]; then
        mv src/core/config.py.backup src/core/config.py
        echo "✅ Original config.py file restored"
    fi
}

# Set trap to restore .env file on exit
trap cleanup EXIT INT TERM

# Start the FastAPI server with uvicorn
# Use PYTHONDONTWRITEBYTECODE to avoid cache issues
PYTHONDONTWRITEBYTECODE=1 uvicorn src.api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --reload-dir src \
  --log-level info