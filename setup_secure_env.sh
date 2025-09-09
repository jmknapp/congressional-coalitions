#!/bin/bash

# Secure Environment Setup Script for Congressional Coalitions
# This script sets up secure environment variables for the application

set -e  # Exit on any error

echo "🔒 Setting up secure environment variables for Congressional Coalitions..."

# Check if running as root (not recommended)
if [ "$EUID" -eq 0 ]; then
    echo "⚠️  Warning: Running as root. Consider using a non-root user for security."
fi

# Create .env file if it doesn't exist
ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
    echo "📝 Creating .env file..."
    touch "$ENV_FILE"
    chmod 600 "$ENV_FILE"  # Restrict access to owner only
else
    echo "📝 .env file already exists. Backing up to .env.backup..."
    cp "$ENV_FILE" ".env.backup.$(date +%Y%m%d_%H%M%S)"
fi

# Function to generate secure random string
generate_secure_string() {
    openssl rand -base64 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_urlsafe(32))"
}

# Function to prompt for sensitive input
prompt_secure_input() {
    local prompt="$1"
    local var_name="$2"
    local current_value="${!var_name}"
    
    if [ -n "$current_value" ]; then
        echo "Current $var_name is set. Press Enter to keep current value or type new value:"
        read -s new_value
        if [ -n "$new_value" ]; then
            echo "$var_name=$new_value" >> "$ENV_FILE"
        else
            echo "$var_name=$current_value" >> "$ENV_FILE"
        fi
    else
        echo "$prompt"
        read -s new_value
        echo "$var_name=$new_value" >> "$ENV_FILE"
    fi
}

# Clear the .env file
> "$ENV_FILE"

echo ""
echo "🔐 Setting up security variables..."

# Generate secure random values
SECRET_KEY=$(generate_secure_string)
DEV_PASSWORD_SALT=$(generate_secure_string)

# Add generated values
echo "SECRET_KEY=$SECRET_KEY" >> "$ENV_FILE"
echo "DEV_PASSWORD_SALT=$DEV_PASSWORD_SALT" >> "$ENV_FILE"

echo ""
echo "🔑 Setting up database connection..."
echo "Enter your database connection details:"

# Database URL
echo "Database URL (format: mysql://username:password@host:port/database):"
read -p "DATABASE_URL: " DATABASE_URL
echo "DATABASE_URL=$DATABASE_URL" >> "$ENV_FILE"

echo ""
echo "🛡️ Setting up developer mode security..."

# Developer password
prompt_secure_input "Enter a strong password for developer mode (min 8 characters):" "DEV_PASSWORD"

# Session timeout
echo "Developer session timeout in seconds (default: 7200 = 2 hours):"
read -p "DEV_SESSION_TIMEOUT [7200]: " DEV_SESSION_TIMEOUT
DEV_SESSION_TIMEOUT=${DEV_SESSION_TIMEOUT:-7200}
echo "DEV_SESSION_TIMEOUT=$DEV_SESSION_TIMEOUT" >> "$ENV_FILE"

echo ""
echo "🌐 Setting up CORS and environment..."

# Environment
echo "Environment (development/production):"
read -p "FLASK_ENV [production]: " FLASK_ENV
FLASK_ENV=${FLASK_ENV:-production}
echo "FLASK_ENV=$FLASK_ENV" >> "$ENV_FILE"

# CORS origins
echo "Allowed CORS origins (comma-separated, * for all):"
read -p "ALLOWED_ORIGINS [*]: " ALLOWED_ORIGINS
ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-*}
echo "ALLOWED_ORIGINS=$ALLOWED_ORIGINS" >> "$ENV_FILE"

# Development mode
echo "Enable development mode? (true/false):"
read -p "DEV_MODE [false]: " DEV_MODE
DEV_MODE=${DEV_MODE:-false}
echo "DEV_MODE=$DEV_MODE" >> "$ENV_FILE"

echo ""
echo "✅ Environment variables configured successfully!"
echo ""
echo "📋 Summary of configured variables:"
echo "   - SECRET_KEY: Generated secure key"
echo "   - DEV_PASSWORD_SALT: Generated secure salt"
echo "   - DATABASE_URL: Your database connection"
echo "   - DEV_PASSWORD: Your developer mode password"
echo "   - DEV_SESSION_TIMEOUT: $DEV_SESSION_TIMEOUT seconds"
echo "   - FLASK_ENV: $FLASK_ENV"
echo "   - ALLOWED_ORIGINS: $ALLOWED_ORIGINS"
echo "   - DEV_MODE: $DEV_MODE"
echo ""
echo "🔒 Security notes:"
echo "   - .env file is restricted to owner only (chmod 600)"
echo "   - Never commit .env file to version control"
echo "   - Rotate DEV_PASSWORD regularly"
echo "   - Use HTTPS in production"
echo ""
echo "🚀 To start the application:"
echo "   source .env && python app.py"
echo ""
echo "📖 For more security information, see SECURITY_CONFIG.md"
