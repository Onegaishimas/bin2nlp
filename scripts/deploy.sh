#!/bin/bash

# bin2nlp Deployment Script
# Automates Docker deployment for different environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="development"
BUILD_IMAGES=false
PULL_IMAGES=false
VERBOSE=false

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}==== $1 ====${NC}"
}

# Function to show usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy bin2nlp using Docker Compose

OPTIONS:
    -e, --env ENVIRONMENT    Deployment environment (development|production) [default: development]
    -b, --build             Force rebuild of Docker images
    -p, --pull              Pull latest base images before building
    -v, --verbose           Enable verbose output
    -h, --help              Show this help message

EXAMPLES:
    $0                      Deploy in development mode
    $0 -e production        Deploy in production mode
    $0 -e production -b     Deploy production with image rebuild
    $0 --build --pull       Rebuild with latest base images

ENVIRONMENTS:
    development             Local development with hot reload and debug mode
    production              Production deployment with optimizations and security

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -b|--build)
            BUILD_IMAGES=true
            shift
            ;;
        -p|--pull)
            PULL_IMAGES=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(development|production)$ ]]; then
    print_error "Invalid environment: $ENVIRONMENT. Must be 'development' or 'production'"
    exit 1
fi

# Set verbose mode
if [[ "$VERBOSE" == true ]]; then
    set -x
fi

print_header "bin2nlp Deployment Script"
print_status "Environment: $ENVIRONMENT"
print_status "Build images: $BUILD_IMAGES"
print_status "Pull images: $PULL_IMAGES"

# Check prerequisites
print_header "Checking Prerequisites"

# Check if Docker is installed and running
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! docker info &> /dev/null; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not available. Please install Docker Compose."
    exit 1
fi

# Use docker compose or docker-compose based on availability
COMPOSE_CMD="docker-compose"
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
fi

print_status "Docker and Docker Compose are available"

# Create required directories
print_header "Setting Up Directories"
mkdir -p data/{postgres,uploads,logs,nginx,storage}
chmod 755 data/uploads data/logs

# Set up environment configuration
print_header "Environment Configuration"

if [[ "$ENVIRONMENT" == "production" ]]; then
    # Production environment checks
    if [[ ! -f .env ]]; then
        if [[ -f .env.template ]]; then
            print_warning "No .env file found. Copying from .env.template"
            cp .env.template .env
            print_warning "Please edit .env file with your production settings before continuing"
            print_warning "Especially set your LLM provider API keys!"
            exit 1
        else
            print_error "No .env file found and no .env.template available"
            exit 1
        fi
    fi
    
    # Check critical environment variables
    if ! grep -q "OPENAI_API_KEY=sk-" .env 2>/dev/null; then
        print_warning "OpenAI API key not configured in .env file"
    fi
    
    COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
    print_status "Using production configuration"
else
    # Development environment
    COMPOSE_FILES="-f docker-compose.yml"
    print_status "Using development configuration (with overrides)"
fi

# Pull base images if requested
if [[ "$PULL_IMAGES" == true ]]; then
    print_header "Pulling Base Images"
    $COMPOSE_CMD $COMPOSE_FILES pull
fi

# Build images
if [[ "$BUILD_IMAGES" == true ]]; then
    print_header "Building Docker Images"
    $COMPOSE_CMD $COMPOSE_FILES build --no-cache
else
    print_header "Building Docker Images (using cache)"
    $COMPOSE_CMD $COMPOSE_FILES build
fi

# Stop existing containers
print_header "Stopping Existing Containers"
$COMPOSE_CMD $COMPOSE_FILES down --remove-orphans

# Start services
print_header "Starting Services"
$COMPOSE_CMD $COMPOSE_FILES up -d

# Wait for services to be healthy
print_header "Waiting for Services to Start"
sleep 10

# Check service health
print_header "Checking Service Health"

# Check API health
if curl -f -s http://localhost:8000/api/v1/health > /dev/null; then
    print_status "API service is healthy"
else
    print_error "API service health check failed"
    print_error "Checking logs..."
    $COMPOSE_CMD $COMPOSE_FILES logs api
    exit 1
fi

# Check Database health
if $COMPOSE_CMD $COMPOSE_FILES exec -T database pg_isready -U bin2nlp | grep -q "accepting connections"; then
    print_status "PostgreSQL database is healthy"
else
    print_error "PostgreSQL database health check failed"
fi

# Display running services
print_header "Deployment Status"
$COMPOSE_CMD $COMPOSE_FILES ps

print_header "Deployment Complete"
print_status "Services are running and healthy!"

if [[ "$ENVIRONMENT" == "development" ]]; then
    echo
    print_status "Development URLs:"
    print_status "  API: http://localhost:8000"
    print_status "  Health: http://localhost:8000/api/v1/health" 
    print_status "  API Docs: http://localhost:8000/docs"
    print_status "  Database: localhost:5432 (PostgreSQL)"
    echo
    print_status "Useful commands:"
    print_status "  View logs: $COMPOSE_CMD $COMPOSE_FILES logs -f"
    print_status "  Stop services: $COMPOSE_CMD $COMPOSE_FILES down"
    print_status "  Restart API: $COMPOSE_CMD $COMPOSE_FILES restart api"
else
    echo
    print_status "Production deployment complete"
    print_status "  API: http://localhost:8000"
    print_status "  Health: http://localhost:8000/api/v1/health"
    echo
    print_warning "Remember to:"
    print_warning "  1. Configure SSL certificates for HTTPS"
    print_warning "  2. Set up monitoring and alerting"
    print_warning "  3. Configure log rotation"
    print_warning "  4. Review security settings"
fi