#!/bin/bash
# ==============================================
# Contract AI System - Deployment Script
# ==============================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.production.yml"
ENV_FILE=".env.production"

# Functions
print_header() {
    echo -e "${BLUE}===================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}===================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check if .env.production exists
check_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        print_error ".env.production file not found!"
        print_info "Please copy .env.production.example and configure it:"
        echo "    cp .env.production .env.production"
        echo "    nano .env.production"
        exit 1
    fi
    print_success ".env.production found"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed!"
        print_info "Please install Docker: https://docs.docker.com/engine/install/"
        exit 1
    fi
    print_success "Docker is installed"
}

# Check if Docker Compose is installed
check_docker_compose() {
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed!"
        print_info "Please install Docker Compose: https://docs.docker.com/compose/install/"
        exit 1
    fi
    print_success "Docker Compose is installed"
}

# Check swap space
check_swap() {
    SWAP_SIZE=$(free -m | awk '/^Swap:/ {print $2}')
    if [ "$SWAP_SIZE" -lt 2000 ]; then
        print_warning "Swap space is less than 2GB (${SWAP_SIZE}MB)"
        print_info "Recommended: Create swap file with setup-swap.sh"
    else
        print_success "Swap space: ${SWAP_SIZE}MB"
    fi
}

# Create necessary directories
create_directories() {
    print_info "Creating necessary directories..."
    mkdir -p data/{uploads,normalized,reports,exports,templates,static}
    mkdir -p database
    mkdir -p logs
    mkdir -p nginx/ssl
    print_success "Directories created"
}

# Generate secret keys if needed
generate_secrets() {
    if grep -q "CHANGE_THIS" "$ENV_FILE"; then
        print_warning "Found default secrets in .env.production!"
        read -p "Generate new secret keys? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            SECRET_KEY=$(openssl rand -hex 32)
            JWT_SECRET=$(openssl rand -hex 32)
            sed -i "s/SECRET_KEY=CHANGE_THIS.*/SECRET_KEY=$SECRET_KEY/" "$ENV_FILE"
            sed -i "s/JWT_SECRET_KEY=CHANGE_THIS.*/JWT_SECRET_KEY=$JWT_SECRET/" "$ENV_FILE"
            print_success "Secret keys generated"
        fi
    fi
}

# Pull latest changes from git
pull_changes() {
    if [ -d .git ]; then
        print_info "Pulling latest changes from git..."
        git pull
        print_success "Git pull completed"
    fi
}

# Build Docker images
build_images() {
    print_info "Building Docker images..."
    docker-compose -f "$COMPOSE_FILE" build --no-cache
    print_success "Docker images built"
}

# Start services
start_services() {
    print_info "Starting services..."
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
    print_success "Services started"
}

# Stop services
stop_services() {
    print_info "Stopping services..."
    docker-compose -f "$COMPOSE_FILE" down
    print_success "Services stopped"
}

# Restart services
restart_services() {
    print_info "Restarting services..."
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" restart
    print_success "Services restarted"
}

# Show logs
show_logs() {
    docker-compose -f "$COMPOSE_FILE" logs -f --tail=100
}

# Show status
show_status() {
    print_header "Service Status"
    docker-compose -f "$COMPOSE_FILE" ps
    echo ""
    print_header "Resource Usage"
    docker stats --no-stream
}

# Database migrations
run_migrations() {
    print_info "Running database migrations..."
    docker-compose -f "$COMPOSE_FILE" exec backend alembic upgrade head
    print_success "Migrations completed"
}

# Health check
health_check() {
    print_info "Checking service health..."

    # Wait for services to be ready
    sleep 10

    # Check backend
    if curl -f http://localhost:8000/health &> /dev/null; then
        print_success "Backend is healthy"
    else
        print_error "Backend is not responding"
    fi

    # Check frontend
    if curl -f http://localhost:3000 &> /dev/null; then
        print_success "Frontend is healthy"
    else
        print_error "Frontend is not responding"
    fi

    # Check nginx
    if curl -f http://localhost/health &> /dev/null; then
        print_success "Nginx is healthy"
    else
        print_error "Nginx is not responding"
    fi
}

# Main menu
show_menu() {
    echo ""
    print_header "Contract AI System - Deployment Menu"
    echo "1) Deploy (First time setup)"
    echo "2) Update (Pull changes and restart)"
    echo "3) Start services"
    echo "4) Stop services"
    echo "5) Restart services"
    echo "6) Show logs"
    echo "7) Show status"
    echo "8) Run migrations"
    echo "9) Health check"
    echo "0) Exit"
    echo ""
}

# Main script
main() {
    print_header "Contract AI System - Deployment Script"

    # Pre-flight checks
    check_docker
    check_docker_compose
    check_swap

    # Show menu
    while true; do
        show_menu
        read -p "Select option: " choice
        case $choice in
            1)
                print_header "DEPLOYING"
                check_env_file
                generate_secrets
                create_directories
                build_images
                start_services
                run_migrations
                health_check
                print_success "Deployment completed!"
                print_info "Access your application at: http://localhost"
                print_info "API docs at: http://localhost/api/docs"
                ;;
            2)
                print_header "UPDATING"
                pull_changes
                build_images
                restart_services
                run_migrations
                health_check
                print_success "Update completed!"
                ;;
            3)
                start_services
                ;;
            4)
                stop_services
                ;;
            5)
                restart_services
                ;;
            6)
                show_logs
                ;;
            7)
                show_status
                ;;
            8)
                run_migrations
                ;;
            9)
                health_check
                ;;
            0)
                print_info "Goodbye!"
                exit 0
                ;;
            *)
                print_error "Invalid option"
                ;;
        esac
    done
}

# Run main function
main
