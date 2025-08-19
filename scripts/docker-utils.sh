#!/bin/bash

# Docker Utility Scripts for bin2nlp
# Common Docker operations for development and maintenance

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Detect docker-compose command
COMPOSE_CMD="docker-compose"
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
fi

# Function to show usage
usage() {
    cat << EOF
Usage: $0 COMMAND [OPTIONS]

Docker utility commands for bin2nlp

COMMANDS:
    build           Build Docker images
    start           Start services
    stop            Stop services
    restart         Restart services  
    logs            View logs
    shell           Open shell in API container
    redis-cli       Open Redis CLI
    test            Run tests in container
    clean           Clean up Docker resources
    health          Check service health
    status          Show service status

EXAMPLES:
    $0 build                Build images
    $0 start                Start all services
    $0 logs api             Show API logs
    $0 shell                Open bash shell in API container
    $0 redis-cli            Connect to Redis
    $0 test                 Run integration tests
    $0 clean                Clean up unused Docker resources

EOF
}

# Build images
build_images() {
    print_header "Building Docker Images"
    $COMPOSE_CMD build "$@"
}

# Start services
start_services() {
    print_header "Starting Services"
    $COMPOSE_CMD up -d "$@"
    print_status "Services started. Use '$0 logs' to view logs."
}

# Stop services
stop_services() {
    print_header "Stopping Services"
    $COMPOSE_CMD down "$@"
}

# Restart services
restart_services() {
    print_header "Restarting Services"
    $COMPOSE_CMD restart "$@"
}

# View logs
view_logs() {
    if [[ $# -eq 0 ]]; then
        print_status "Showing logs for all services (Ctrl+C to exit)"
        $COMPOSE_CMD logs -f
    else
        print_status "Showing logs for: $*"
        $COMPOSE_CMD logs -f "$@"
    fi
}

# Open shell in API container
open_shell() {
    print_status "Opening shell in API container..."
    if $COMPOSE_CMD ps api | grep -q "Up"; then
        $COMPOSE_CMD exec api bash
    else
        print_error "API container is not running. Start it first with '$0 start'"
        exit 1
    fi
}

# Open Redis CLI
open_redis_cli() {
    print_status "Opening Redis CLI..."
    if $COMPOSE_CMD ps redis | grep -q "Up"; then
        $COMPOSE_CMD exec redis redis-cli
    else
        print_error "Redis container is not running. Start it first with '$0 start'"
        exit 1
    fi
}

# Run tests
run_tests() {
    print_header "Running Tests in Container"
    if $COMPOSE_CMD ps api | grep -q "Up"; then
        print_status "Running integration tests..."
        $COMPOSE_CMD exec api python -m pytest tests/integration/ -v
    else
        print_error "API container is not running. Start it first with '$0 start'"
        exit 1
    fi
}

# Check service health
check_health() {
    print_header "Service Health Check"
    
    # Check API health
    if curl -f -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        print_status "✅ API service is healthy"
    else
        print_error "❌ API service is not healthy"
    fi
    
    # Check Redis health
    if $COMPOSE_CMD exec -T redis redis-cli ping | grep -q PONG 2>/dev/null; then
        print_status "✅ Redis service is healthy"
    else
        print_error "❌ Redis service is not healthy"
    fi
    
    echo
    print_status "Service Status:"
    $COMPOSE_CMD ps
}

# Show service status
show_status() {
    print_header "Service Status"
    $COMPOSE_CMD ps
}

# Clean up Docker resources
clean_resources() {
    print_header "Cleaning Up Docker Resources"
    
    print_warning "This will remove:"
    print_warning "  - Stopped containers"
    print_warning "  - Unused networks"
    print_warning "  - Unused images"
    print_warning "  - Build cache"
    
    echo
    read -p "Continue? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Removing stopped containers..."
        docker container prune -f
        
        print_status "Removing unused networks..."
        docker network prune -f
        
        print_status "Removing unused images..."
        docker image prune -f
        
        print_status "Removing build cache..."
        docker builder prune -f
        
        print_status "Cleanup complete!"
    else
        print_status "Cleanup cancelled"
    fi
}

# Main script logic
if [[ $# -eq 0 ]]; then
    usage
    exit 1
fi

COMMAND=$1
shift

case $COMMAND in
    build)
        build_images "$@"
        ;;
    start)
        start_services "$@"
        ;;
    stop)
        stop_services "$@"
        ;;
    restart)
        restart_services "$@"
        ;;
    logs)
        view_logs "$@"
        ;;
    shell)
        open_shell
        ;;
    redis-cli)
        open_redis_cli
        ;;
    test)
        run_tests
        ;;
    health)
        check_health
        ;;
    status)
        show_status
        ;;
    clean)
        clean_resources
        ;;
    *)
        print_error "Unknown command: $COMMAND"
        echo
        usage
        exit 1
        ;;
esac