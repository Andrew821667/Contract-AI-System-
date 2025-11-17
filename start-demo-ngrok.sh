#!/bin/bash
# ==============================================
# Contract AI System - Quick Demo with Ngrok
# ==============================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}===================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}===================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_header "Contract AI System - Quick Demo Setup"

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    print_info "Ngrok not found. Installing..."

    # Download ngrok
    wget -q https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
    tar xzf ngrok-v3-stable-linux-amd64.tgz
    sudo mv ngrok /usr/local/bin/
    rm ngrok-v3-stable-linux-amd64.tgz

    print_success "Ngrok installed"

    echo ""
    print_info "Please sign up at https://dashboard.ngrok.com/signup"
    print_info "Then run: ngrok config add-authtoken YOUR_AUTH_TOKEN"
    print_info "After that, run this script again."
    exit 0
fi

# Check if ngrok is authenticated
if ! ngrok config check &> /dev/null; then
    print_error "Ngrok is not authenticated!"
    print_info "Sign up at: https://dashboard.ngrok.com/signup"
    print_info "Get your authtoken and run:"
    echo "    ngrok config add-authtoken YOUR_AUTH_TOKEN"
    exit 1
fi

# Check if system is running
if ! docker-compose -f docker-compose.production.yml ps | grep -q "Up"; then
    print_info "Starting Contract AI System..."
    ./deploy.sh <<< "3"  # Option 3: Start services

    print_info "Waiting for services to be ready (30 seconds)..."
    sleep 30
fi

# Check health
print_info "Checking system health..."
if curl -f http://localhost/health &> /dev/null; then
    print_success "System is healthy"
else
    print_error "System is not responding. Please check logs:"
    echo "    ./deploy.sh"
    echo "    # Select: 6) Show logs"
    exit 1
fi

print_header "Starting Ngrok Tunnel"

# Start ngrok in background
print_info "Creating public URL..."
ngrok http 80 > /dev/null &
NGROK_PID=$!

# Wait for ngrok to start
sleep 3

# Get public URL
PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | grep -o 'https://.*' | head -1)

if [ -z "$PUBLIC_URL" ]; then
    print_error "Failed to get public URL"
    kill $NGROK_PID 2>/dev/null || true
    exit 1
fi

print_header "🎉 Contract AI System is Live!"

echo ""
echo -e "${GREEN}Public URL:${NC} ${BLUE}$PUBLIC_URL${NC}"
echo ""
echo "Share this URL with your clients to demo the system!"
echo ""
print_info "System Features:"
echo "  ✅ Contract Analysis (AI-powered)"
echo "  ✅ Document Generation"
echo "  ✅ Risk Assessment"
echo "  ✅ Multi-language support"
echo ""
print_info "Ngrok Dashboard: http://localhost:4040"
print_info "Press Ctrl+C to stop the tunnel"
echo ""
echo -e "${YELLOW}Note: Free Ngrok URLs expire after session ends${NC}"
echo -e "${YELLOW}For permanent URL, consider purchasing a domain${NC}"
echo ""

# Keep script running
trap "kill $NGROK_PID 2>/dev/null || true; echo ''; print_info 'Tunnel stopped'; exit 0" INT TERM

# Wait for ngrok process
wait $NGROK_PID
