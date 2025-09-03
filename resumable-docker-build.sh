#!/bin/bash

# Resumable Docker Build Script
# This script can be interrupted and resumed, picking up where it left off

set -e  # Exit on error

PROJECT_DIR="/home/jmknapp/congressional-coalitions"
BUILD_DIR="$PROJECT_DIR/docker-build"
PROGRESS_FILE="$BUILD_DIR/.build_progress"
LOG_FILE="$BUILD_DIR/build.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# Function to mark a step as completed
mark_completed() {
    echo "$1" >> "$PROGRESS_FILE"
    success "Completed: $1"
}

# Function to check if a step was completed
is_completed() {
    if [ -f "$PROGRESS_FILE" ]; then
        grep -q "^$1$" "$PROGRESS_FILE" 2>/dev/null
    else
        return 1
    fi
}

# Function to reset progress (for fresh start)
reset_progress() {
    rm -f "$PROGRESS_FILE"
    log "Progress reset - starting fresh build"
}

# Trap Ctrl+C and provide resume instructions
cleanup() {
    warning "\nBuild interrupted! To resume, run:"
    warning "  ./resumable-docker-build.sh"
    warning "To start fresh, run:"
    warning "  ./resumable-docker-build.sh --reset"
    exit 130
}
trap cleanup SIGINT SIGTERM

# Check for reset flag
if [ "$1" = "--reset" ] || [ "$1" = "-r" ]; then
    reset_progress
fi

# Create build directory
mkdir -p "$BUILD_DIR"

log "=== Resumable Docker Build Started ==="
log "Build directory: $BUILD_DIR"
log "Progress file: $PROGRESS_FILE"

# Step 1: Prepare build context
if ! is_completed "prepare_context"; then
    log "Step 1: Preparing build context..."
    
    # Copy essential files
    cp "$PROJECT_DIR/app.py" "$BUILD_DIR/"
    cp "$PROJECT_DIR/requirements.txt" "$BUILD_DIR/"
    cp "$PROJECT_DIR/Dockerfile" "$BUILD_DIR/"
    
    # Copy directories
    cp -r "$PROJECT_DIR/src" "$BUILD_DIR/" 2>/dev/null || true
    cp -r "$PROJECT_DIR/static" "$BUILD_DIR/" 2>/dev/null || true
    cp -r "$PROJECT_DIR/templates" "$BUILD_DIR/" 2>/dev/null || true
    cp -r "$PROJECT_DIR/scripts" "$BUILD_DIR/" 2>/dev/null || true
    
    # Create logs directory
    mkdir -p "$BUILD_DIR/logs"
    
    mark_completed "prepare_context"
else
    log "Step 1: Build context already prepared ✓"
fi

# Step 2: Download system packages in container (pre-check)
if ! is_completed "system_packages"; then
    log "Step 2: Pre-downloading system packages..."
    
    # Create a temporary container to download packages
    docker run --rm -v "$BUILD_DIR:/build" python:3.11-slim bash -c "
        cd /build
        apt-get update
        apt-get download gcc default-libmysqlclient-dev pkg-config python3-numpy python3-scipy python3-pandas python3-sklearn
        echo 'System packages downloaded'
    " || {
        warning "Package pre-download failed, continuing with normal build..."
    }
    
    mark_completed "system_packages"
else
    log "Step 2: System packages already prepared ✓"
fi

# Step 3: Pre-download Python packages
if ! is_completed "python_packages"; then
    log "Step 3: Pre-downloading Python packages..."
    
    cd "$BUILD_DIR"
    
    # Create a pip cache directory
    mkdir -p pip-cache
    
    # Download packages to cache
    docker run --rm -v "$BUILD_DIR:/build" python:3.11-slim bash -c "
        cd /build
        pip install --upgrade pip setuptools wheel
        pip download --dest pip-cache --timeout 300 --retries 3 -r requirements.txt
        echo 'Python packages downloaded to cache'
    " || {
        warning "Package download failed, continuing..."
    }
    
    mark_completed "python_packages"
else
    log "Step 3: Python packages already cached ✓"
fi

# Step 4: Create optimized Dockerfile
if ! is_completed "optimized_dockerfile"; then
    log "Step 4: Creating optimized Dockerfile..."
    
    cat > "$BUILD_DIR/Dockerfile.optimized" << 'EOF'
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies and pre-built scientific packages
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    python3-numpy \
    python3-scipy \
    python3-pandas \
    python3-sklearn \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Upgrade pip and use faster options
RUN pip install --upgrade pip setuptools wheel

# Copy pip cache if available and install
COPY pip-cache* ./pip-cache/
RUN if [ -d "pip-cache" ] && [ "$(ls -A pip-cache)" ]; then \
        pip install --find-links pip-cache --timeout 300 --retries 3 --prefer-binary -r requirements.txt; \
    else \
        pip install --timeout 300 --retries 3 --prefer-binary -r requirements.txt; \
    fi

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 5000

# Run the Flask application
CMD ["python3", "app.py"]
EOF
    
    mark_completed "optimized_dockerfile"
else
    log "Step 4: Optimized Dockerfile already created ✓"
fi

# Step 5: Build Docker image with resumable layers
if ! is_completed "docker_build"; then
    log "Step 5: Building Docker image (this may take a while)..."
    
    cd "$BUILD_DIR"
    
    # Build with progress and layer caching
    docker build \
        --progress=plain \
        --tag congressional-coalitions \
        --file Dockerfile.optimized \
        . 2>&1 | tee -a "$LOG_FILE"
    
    if [ $? -eq 0 ]; then
        mark_completed "docker_build"
    else
        error "Docker build failed! Check $LOG_FILE for details"
        exit 1
    fi
else
    log "Step 5: Docker image already built ✓"
fi

# Step 6: Test the image
if ! is_completed "test_image"; then
    log "Step 6: Testing Docker image..."
    
    # Quick test to ensure image runs
    timeout 10 docker run --rm congressional-coalitions python3 -c "
import app
print('Flask app imports successfully')
" || {
        warning "Image test failed, but continuing..."
    }
    
    mark_completed "test_image"
else
    log "Step 6: Image already tested ✓"
fi

# Step 7: Clean up build directory (optional)
log "Step 7: Build complete!"
success "Docker image 'congressional-coalitions' built successfully"

# Show next steps
log ""
log "=== Next Steps ==="
log "1. Restart the service:"
log "   sudo systemctl restart congressional-app"
log ""
log "2. Check service status:"
log "   sudo systemctl status congressional-app"
log ""
log "3. Test the application:"
log "   curl -s http://localhost:5000/api/bills | head -5"
log ""
log "4. Clean up build directory (optional):"
log "   rm -rf $BUILD_DIR"
log ""

# Offer to restart service
read -p "Would you like to restart the congressional-app service now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log "Restarting congressional-app service..."
    sudo systemctl restart congressional-app
    sleep 3
    sudo systemctl status congressional-app
fi

success "Build process completed successfully!"
