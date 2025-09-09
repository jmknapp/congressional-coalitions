# Security Configuration Guide

## Environment Variables

Set the following environment variables for secure operation:

### Required Security Variables

```bash
# Developer Mode Password (REQUIRED - Set a strong password)
export DEV_PASSWORD="your_secure_password_here"

# Flask Secret Key (REQUIRED for sessions)
export SECRET_KEY="your_secret_key_here"

# Password Salt (for additional security)
export DEV_PASSWORD_SALT="your_random_salt_here"
```

### Optional Security Variables

```bash
# Developer Session Timeout (in seconds, default: 7200 = 2 hours)
export DEV_SESSION_TIMEOUT="7200"

# Environment (development/production)
export FLASK_ENV="production"

# Allowed Origins for CORS (comma-separated)
export ALLOWED_ORIGINS="https://yourdomain.com,https://www.yourdomain.com"
```

## Security Features Implemented

### 1. Password Security
- ✅ Environment variable-based password storage
- ✅ SHA-256 password hashing with salt
- ✅ Password length validation (8-128 characters)
- ✅ No hardcoded passwords in source code

### 2. Session Management
- ✅ Server-side session management
- ✅ Secure HTTP-only cookies
- ✅ Configurable session timeout
- ✅ Automatic session expiration

### 3. Rate Limiting
- ✅ 5 attempts per minute for password verification
- ✅ 200 requests per day, 50 per hour general limit
- ✅ IP-based rate limiting

### 4. HTTPS Enforcement
- ✅ Automatic HTTPS redirect in production
- ✅ Secure cookie flags
- ✅ CORS origin restrictions

### 5. Audit Logging
- ✅ All dev mode access attempts logged
- ✅ IP address tracking
- ✅ Success/failure status logging
- ✅ Timestamped security events

### 6. Input Validation
- ✅ Request format validation
- ✅ Password format validation
- ✅ JSON payload validation

## Setup Instructions

1. **Set Environment Variables**:
   ```bash
   # Generate secure values
   export DEV_PASSWORD=$(openssl rand -base64 32)
   export SECRET_KEY=$(openssl rand -base64 32)
   export DEV_PASSWORD_SALT=$(openssl rand -base64 16)
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Start Application**:
   ```bash
   python app.py
   ```

## Security Best Practices

1. **Use Strong Passwords**: Minimum 8 characters, mix of letters, numbers, symbols
2. **Regular Password Rotation**: Change DEV_PASSWORD periodically
3. **Monitor Logs**: Check security logs for suspicious activity
4. **HTTPS Only**: Always use HTTPS in production
5. **Restrict Origins**: Set ALLOWED_ORIGINS to your actual domains
6. **Regular Updates**: Keep dependencies updated

## Monitoring

Security events are logged with the following format:
```
SECURITY_EVENT: EVENT_TYPE | SUCCESS/FAILED | IP: address | details | timestamp
```

Monitor these logs for:
- Failed password attempts
- Unusual access patterns
- Rate limit violations
- Session anomalies

## Troubleshooting

### Common Issues

1. **Rate Limited**: Wait 1 minute between password attempts
2. **Session Expired**: Re-authenticate with Shift+Ctrl+D
3. **HTTPS Redirect Loop**: Ensure proper proxy configuration
4. **CORS Errors**: Check ALLOWED_ORIGINS configuration

### Log Locations

- Application logs: Check Flask application output
- Security logs: Look for "SECURITY_EVENT" entries
- Rate limit logs: Check for "429 Too Many Requests" responses
