#!/bin/bash
# ==============================================
# Setup Swap File for Contract AI System
# ==============================================
# This script creates a 3GB swap file on Ubuntu

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
SWAP_SIZE=3G  # 3GB swap
SWAP_FILE=/swapfile

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root (sudo ./setup-swap.sh)"
    exit 1
fi

echo "=========================================="
echo "Contract AI System - Swap Setup"
echo "=========================================="

# Check current swap
CURRENT_SWAP=$(free -m | awk '/^Swap:/ {print $2}')
print_info "Current swap: ${CURRENT_SWAP}MB"

if [ "$CURRENT_SWAP" -gt 2000 ]; then
    print_success "Swap already configured (${CURRENT_SWAP}MB)"
    read -p "Do you want to recreate swap? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi

    # Turn off existing swap
    print_info "Disabling existing swap..."
    swapoff -a
    sed -i '/swapfile/d' /etc/fstab
fi

# Check if swapfile exists
if [ -f "$SWAP_FILE" ]; then
    print_info "Removing old swapfile..."
    rm -f "$SWAP_FILE"
fi

# Check available disk space
AVAILABLE_SPACE=$(df -BG / | tail -1 | awk '{print $4}' | sed 's/G//')
print_info "Available disk space: ${AVAILABLE_SPACE}GB"

if [ "$AVAILABLE_SPACE" -lt 4 ]; then
    print_error "Not enough disk space! Need at least 4GB free"
    exit 1
fi

# Create swap file
print_info "Creating ${SWAP_SIZE} swap file..."
fallocate -l $SWAP_SIZE $SWAP_FILE

if [ ! -f "$SWAP_FILE" ]; then
    print_error "Failed to create swap file!"
    exit 1
fi

# Set permissions
chmod 600 $SWAP_FILE
print_success "Swap file created"

# Make swap
print_info "Setting up swap space..."
mkswap $SWAP_FILE

# Enable swap
print_info "Enabling swap..."
swapon $SWAP_FILE

# Make permanent
if ! grep -q "$SWAP_FILE" /etc/fstab; then
    echo "$SWAP_FILE none swap sw 0 0" >> /etc/fstab
    print_success "Added to /etc/fstab"
fi

# Optimize swap settings
print_info "Optimizing swap settings..."

# Set swappiness to 10 (use swap only when needed)
sysctl vm.swappiness=10
echo "vm.swappiness=10" >> /etc/sysctl.conf

# Set cache pressure
sysctl vm.vfs_cache_pressure=50
echo "vm.vfs_cache_pressure=50" >> /etc/sysctl.conf

print_success "Swap settings optimized"

# Show results
echo ""
echo "=========================================="
echo "Swap Configuration Complete!"
echo "=========================================="
free -h
echo ""

print_success "Swap file: $SWAP_FILE"
print_success "Size: $SWAP_SIZE"
print_success "Swappiness: 10"
print_success "Status: Active"

echo ""
print_info "You can now deploy Contract AI System with:"
print_info "  ./deploy.sh"
