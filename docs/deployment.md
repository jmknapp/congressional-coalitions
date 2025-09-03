# Deployment Guide

## 🚀 System Setup and Production Deployment

This guide covers the complete deployment process for the Congressional Coalition Analysis system, from initial setup to production maintenance.

## 📋 Prerequisites

### System Requirements

**Operating System**: Ubuntu 20.04+ or CentOS 8+
**Memory**: Minimum 4GB RAM, recommended 8GB+
**Storage**: Minimum 50GB, recommended 100GB+
**CPU**: 2+ cores recommended
**Network**: Stable internet connection for API calls

### Software Dependencies

```bash
# Core system packages
sudo apt-get update
sudo apt-get install -y \
    docker.io \
    docker-compose \
    mysql-server \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    unzip

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add user to docker group
sudo usermod -aG docker $USER
```

## 🗄️ Database Setup

### MySQL Installation and Configuration

```bash
# Install MySQL
sudo apt-get install -y mysql-server

# Secure MySQL installation
sudo mysql_secure_installation

# Create database and user
sudo mysql -u root -p
```

```sql
-- Create database
CREATE DATABASE congressional_coalitions 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

-- Create user
CREATE USER 'congressional'@'localhost' 
IDENTIFIED BY 'congressional123';

-- Grant privileges
GRANT ALL PRIVILEGES ON congressional_coalitions.* 
TO 'congressional'@'localhost';

-- Apply changes
FLUSH PRIVILEGES;
EXIT;
```

### Database Schema Creation

```bash
# Navigate to project directory
cd /home/jmknapp/congressional-coalitions

# Activate virtual environment
source venv/bin/activate

# Run database setup
python scripts/setup_db.py
```

## 🐳 Docker Configuration

### Build Docker Image

```bash
# Build optimized image
docker build -t congressional-coalitions .

# Verify image creation
docker images | grep congressional-coalitions
```

### Docker Run Commands

**Development Mode**:
```bash
docker run --rm -p 5000:5000 \
  -v /var/run/mysqld:/var/run/mysqld \
  -v /run/mysqld:/run/mysqld \
  -e FLASK_ENV=development \
  congressional-coalitions
```

**Production Mode**:
```bash
docker run -d --name congressional-app \
  --network host \
  -v /var/run/mysqld:/var/run/mysqld \
  -v /run/mysqld:/run/mysqld \
  -e FLASK_ENV=production \
  congressional-coalitions
```

## ⚙️ Systemd Service Configuration

### Service File Creation

Create `/etc/systemd/system/congressional-app.service`:

```ini
[Unit]
Description=Congressional Coalition Tracker
After=docker.service mysql.service network-online.target
Wants=network-online.target
Requires=docker.service

[Service]
Type=simple
RemainAfterExit=no
Restart=always
RestartSec=10
TimeoutStartSec=300
ExecStartPre=/usr/bin/docker rm -f congressional-app || true
ExecStart=/usr/bin/docker run --network host \
  -v /var/run/mysqld:/var/run/mysqld \
  -v /run/mysqld:/run/mysqld \
  --name congressional-app congressional-coalitions
ExecStop=/usr/bin/docker stop congressional-app || true
ExecStopPost=/usr/bin/docker rm congressional-app || true

[Install]
WantedBy=multi-user.target
```

### Service Management

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable congressional-app

# Start service
sudo systemctl start congressional-app

# Check status
sudo systemctl status congressional-app

# View logs
sudo journalctl -u congressional-app -f
```

## 🔑 Environment Configuration

### API Keys Setup

```bash
# Add to ~/.profile
echo 'export CONGRESSGOV_API_KEY="your_api_key_here"' >> ~/.profile
echo 'export GOVINFO_API_KEY="your_govinfo_key_here"' >> ~/.profile

# Reload profile
source ~/.profile

# Verify environment variables
echo $CONGRESSGOV_API_KEY
```

### Configuration Files

**Database Configuration**:
```python
# src/utils/database.py
DATABASE_URL = os.getenv('DATABASE_URL', 
    'mysql://congressional:congressional123@localhost/congressional_coalitions')
```

**Flask Configuration**:
```python
# app.py
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['FLASK_ENV'] = os.getenv('FLASK_ENV', 'production')
```

## 📅 Cron Job Setup

### Automated Data Updates

```bash
# Edit crontab
crontab -e

# Add daily bill discovery (6 AM)
0 6 * * * cd /home/jmknapp/congressional-coalitions && \
  venv/bin/python scripts/enhanced_daily_update.py --congress 119 --max-bills 100 \
  >> /tmp/enhanced_bill_discovery.log 2>&1

# Add hourly analysis updates
0 * * * * cd /home/jmknapp/congressional-coalitions && \
  venv/bin/python scripts/cron_update_analysis.py --congress 119 --chamber house \
  >> /tmp/analysis_cron.log 2>&1
```

### Cron Job Management

```bash
# List current cron jobs
crontab -l

# Check cron logs
tail -f /tmp/enhanced_bill_discovery.log
tail -f /tmp/analysis_cron.log

# Test cron job manually
cd /home/jmknapp/congressional-coalitions
source venv/bin/activate
python scripts/enhanced_daily_update.py --congress 119 --max-bills 5
```

## 🌐 Web Server Configuration

### Nginx Reverse Proxy (Optional)

```nginx
# /etc/nginx/sites-available/congressional
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/congressional /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### SSL Certificate (Optional)

```bash
# Install Certbot
sudo apt-get install -y certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

## 📊 Monitoring and Maintenance

### Health Checks

```bash
# Service status
sudo systemctl status congressional-app

# Docker container status
docker ps | grep congressional-app

# API endpoint test
curl -f http://localhost:5000/api/summary

# Database connection test
mysql -u congressional -p'congressional123' \
  -e "SELECT COUNT(*) FROM bills;"
```

### Log Management

```bash
# View service logs
sudo journalctl -u congressional-app --no-pager -n 100

# View Docker logs
docker logs congressional-app --tail 100

# Rotate logs
sudo journalctl --vacuum-time=30d
```

### Performance Monitoring

```bash
# System resources
htop
free -h
df -h

# Docker resource usage
docker stats congressional-app

# Database performance
mysql -u congressional -p'congressional123' \
  -e "SHOW PROCESSLIST;"
```

## 🔄 Update Procedures

### Application Updates

```bash
# Pull latest code
cd /home/jmknapp/congressional-coalitions
git pull origin main

# Rebuild Docker image
docker build -t congressional-coalitions .

# Restart service
sudo systemctl restart congressional-app

# Verify update
curl -f http://localhost:5000/api/summary
```

### Database Migrations

```bash
# Run migration scripts
cd /home/jmknapp/congressional-coalitions
source venv/bin/activate

# Add new columns
python scripts/add_last_updated_column.py

# Backfill metadata
python scripts/backfill_bill_metadata.py --congress 119 --api-key $CONGRESSGOV_API_KEY
```

## 🚨 Troubleshooting

### Common Issues

**Service Won't Start**:
```bash
# Check Docker status
sudo systemctl status docker

# Check container logs
docker logs congressional-app

# Verify image exists
docker images | grep congressional-coalitions
```

**Database Connection Issues**:
```bash
# Check MySQL status
sudo systemctl status mysql

# Test connection
mysql -u congressional -p'congressional123' -e "SELECT 1;"

# Check socket permissions
ls -la /var/run/mysqld/
```

**API Endpoints Not Working**:
```bash
# Check service status
sudo systemctl status congressional-app

# Test local endpoint
curl -v http://localhost:5000/api/bills

# Check firewall
sudo ufw status
```

### Recovery Procedures

**Service Recovery**:
```bash
# Restart service
sudo systemctl restart congressional-app

# Check logs for errors
sudo journalctl -u congressional-app --no-pager -n 50

# Verify container is running
docker ps | grep congressional-app
```

**Database Recovery**:
```bash
# Check MySQL status
sudo systemctl status mysql

# Restart MySQL if needed
sudo systemctl restart mysql

# Verify database connectivity
mysql -u congressional -p'congressional123' \
  -e "USE congressional_coalitions; SHOW TABLES;"
```

## 📈 Scaling Considerations

### Performance Optimization

**Database Optimization**:
```sql
-- Add indexes for common queries
CREATE INDEX idx_bills_congress_chamber_date 
ON bills(congress, chamber, introduced_date);

-- Optimize table structures
OPTIMIZE TABLE bills;
ANALYZE TABLE bills;
```

**Application Optimization**:
```python
# Enable caching
app.config['CACHE_TYPE'] = 'redis'
app.config['CACHE_REDIS_URL'] = 'redis://localhost:6379/0'

# Database connection pooling
from sqlalchemy.pool import QueuePool
engine = create_engine(DATABASE_URL, poolclass=QueuePool, pool_size=20, max_overflow=30)
```

### Load Balancing

**Multiple Instances**:
```bash
# Run multiple containers
docker run -d --name congressional-app-1 -p 5001:5000 congressional-coalitions
docker run -d --name congressional-app-2 -p 5002:5000 congressional-coalitions

# Configure load balancer
# (Nginx, HAProxy, or cloud load balancer)
```

## 🔒 Security Considerations

### Access Control

```bash
# Firewall configuration
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (if using Nginx)
sudo ufw allow 443/tcp   # HTTPS (if using SSL)
sudo ufw enable

# Restrict database access
sudo ufw deny 3306/tcp   # MySQL
```

### API Security

```python
# Rate limiting
from flask_limiter import Limiter
limiter = Limiter(app, key_func=get_remote_address)

@app.route('/api/analysis/<congress>/<chamber>')
@limiter.limit("100 per hour")
def get_analysis(congress, chamber):
    # ... implementation
```

## 📚 Additional Resources

### Documentation

- **Voting Pattern Analysis**: `/docs/voting-pattern-analysis.md`
- **API Reference**: `/docs/api-reference.md`
- **Database Schema**: `/docs/database-schema.md`
- **Metadata Extraction**: `/docs/metadata-extraction.md`

### Support

- **GitHub Issues**: Report bugs and feature requests
- **System Logs**: Check service and application logs
- **Community**: Join congressional analysis discussions

---

*This deployment guide provides comprehensive instructions for setting up and maintaining the Congressional Coalition Analysis system in production. For specific issues, consult the troubleshooting section or system logs.*
