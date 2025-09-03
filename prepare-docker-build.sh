#!/bin/bash

# Create clean build directory
BUILD_DIR="docker-build"
echo "Creating clean build directory: $BUILD_DIR"
rm -rf $BUILD_DIR
mkdir -p $BUILD_DIR

# Copy essential application files
echo "Copying application files..."
cp app.py $BUILD_DIR/
cp requirements.txt $BUILD_DIR/
cp config.yaml $BUILD_DIR/

# Copy source code directory
echo "Copying source code..."
cp -r src $BUILD_DIR/

# Copy templates and static files
echo "Copying web assets..."
cp -r templates $BUILD_DIR/
cp -r static $BUILD_DIR/

# Copy scripts directory (might be needed for some functionality)
echo "Copying scripts..."
cp -r scripts $BUILD_DIR/

# Create logs directory
mkdir -p $BUILD_DIR/logs

# Copy Dockerfile
cp Dockerfile $BUILD_DIR/

echo "Build directory prepared at: $BUILD_DIR"
echo "Files copied:"
ls -la $BUILD_DIR/

echo ""
echo "To build Docker image, run:"
echo "cd $BUILD_DIR && docker build -t congressional-coalitions ."


