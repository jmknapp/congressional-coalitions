# FEC Data Service

A comprehensive web service for downloading and managing US House candidate information from the Federal Election Commission (FEC) API. This service automatically downloads candidate data daily and provides a web interface for viewing and managing the data.

## Features

- **Automated Daily Downloads**: Downloads candidate data from FEC API every day at 6 AM UTC
- **Database Storage**: Stores candidate information in MySQL database with proper indexing
- **Web Interface**: Modern web interface for viewing and filtering candidates
- **API Endpoints**: RESTful API for programmatic access to candidate data
- **Financial Data**: Includes fundraising and spending information for each candidate
- **Real-time Updates**: Manual download capability with force update options
- **Error Handling**: Comprehensive error handling and logging
- **Scheduler Service**: Background daemon for automated operations

## Quick Start

### 1. Get FEC API Key

1. Visit [https://api.data.gov/signup/](https://api.data.gov/signup/)
2. Register for an account
3. Set the `FEC_API_KEY` environment variable:
   ```bash
   export FEC_API_KEY="your_api_key_here"
   ```

### 2. Setup the Service

```bash
# Install dependencies and setup database
python setup_fec_service.py

# Test the setup
python setup_fec_service.py --test-only
```

### 3. Run Initial Download

```bash
# Download candidate data
python src/etl/fec_scheduler.py --manual

# Test API connection
python src/etl/fec_scheduler.py --test
```

### 4. Start the Web Service

```bash
# Start Flask application
python app.py

# Visit http://localhost:5000/fec-candidates
```

## Usage

### Web Interface

Access the FEC candidates interface at `/fec-candidates`:

- **View Candidates**: Browse all House candidates for 2026
- **Filter Data**: Filter by state, district, party, and status
- **Financial Information**: View fundraising and spending data
- **Manual Downloads**: Trigger manual data downloads
- **Statistics**: View database statistics and last update times

### API Endpoints

#### Get Candidates
```http
GET /api/fec/candidates?office=H&election_year=2026&state=CA&party=DEM
```

#### Get Statistics
```http
GET /api/fec/candidates/stats
```

#### Trigger Download
```http
POST /api/fec/candidates/download
Content-Type: application/json

{
  "force_update": false,
  "office": "H",
  "election_year": 2026
}
```

#### Get Candidate Details
```http
GET /api/fec/candidates/{candidate_id}
```

#### Scheduler Status
```http
GET /api/fec/scheduler/status
```

### Command Line Interface

#### Manual Operations
```bash
# Run manual download
python src/etl/fec_scheduler.py --manual

# Force update existing records
python src/etl/fec_scheduler.py --manual --force

# Test API connection
python src/etl/fec_scheduler.py --test
```

#### Daemon Mode
```bash
# Start scheduler daemon
python src/etl/fec_scheduler.py --daemon

# Stop with Ctrl+C
```

#### Systemd Service
```bash
# Setup systemd service
python setup_fec_service.py --systemd

# Start service
sudo systemctl start fec-scheduler

# Check status
sudo systemctl status fec-scheduler

# View logs
sudo journalctl -u fec-scheduler -f
```

## Configuration

### Environment Variables

- `FEC_API_KEY`: Your FEC API key (required)
- `DATABASE_URL`: Database connection string (optional, defaults to MySQL)
- `DEV_MODE`: Enable development mode (optional)

### Configuration File

Edit `fec_config.yaml` to customize:

- Download schedules
- API rate limits
- Database settings
- Logging configuration
- Error handling

## Database Schema

The service creates a `fec_candidates` table with the following structure:

```sql
CREATE TABLE fec_candidates (
    id INT PRIMARY KEY AUTO_INCREMENT,
    candidate_id VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    party VARCHAR(50),
    office VARCHAR(10) NOT NULL,
    state VARCHAR(2),
    district VARCHAR(10),
    election_year INT NOT NULL,
    election_season VARCHAR(20),
    incumbent_challenge_status VARCHAR(50),
    total_receipts FLOAT DEFAULT 0.0,
    total_disbursements FLOAT DEFAULT 0.0,
    cash_on_hand FLOAT DEFAULT 0.0,
    debts_owed FLOAT DEFAULT 0.0,
    principal_committee_id VARCHAR(20),
    principal_committee_name VARCHAR(255),
    active BOOLEAN DEFAULT TRUE,
    candidate_status VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_fec_update DATETIME,
    raw_fec_data TEXT
);
```

## Scheduling

The service includes a built-in scheduler that runs:

- **Daily Download**: 6:00 AM UTC - Downloads latest candidate data
- **Weekly Cleanup**: Sunday 2:00 AM UTC - Removes old records
- **Health Checks**: Every 6 hours - Monitors system health

## Error Handling

- **Rate Limiting**: Respects FEC API rate limits (1000 requests/hour)
- **Retry Logic**: Automatic retries for failed requests
- **Error Logging**: Comprehensive logging to `logs/fec_service.log`
- **Health Monitoring**: Regular health checks and status reporting

## Development

### Project Structure

```
src/etl/
├── fec_client.py      # FEC API client
├── fec_service.py     # Data service layer
└── fec_scheduler.py   # Scheduler daemon

scripts/
└── setup_fec_candidates_table.py  # Database setup

templates/
└── fec_candidates.html  # Web interface

fec_config.yaml        # Configuration
setup_fec_service.py   # Setup script
fec-scheduler.service  # Systemd service
```

### Testing

```bash
# Test FEC client
python src/etl/fec_client.py

# Test data service
python src/etl/fec_service.py

# Test scheduler
python src/etl/fec_scheduler.py --test
```

## Troubleshooting

### Common Issues

1. **API Key Not Set**
   ```bash
   export FEC_API_KEY="your_key_here"
   ```

2. **Database Connection Failed**
   - Check MySQL is running
   - Verify database credentials
   - Ensure database exists

3. **Rate Limit Exceeded**
   - Wait for rate limit to reset
   - Check API key usage at data.gov

4. **No Data Downloaded**
   - Check API key is valid
   - Verify network connectivity
   - Check logs for errors

### Logs

- **Application Logs**: `logs/fec_service.log`
- **Scheduler Logs**: `logs/fec_scheduler.log`
- **Systemd Logs**: `sudo journalctl -u fec-scheduler`

## License

This project is part of the Congressional Coalitions application. See the main project LICENSE file for details.

## Support

For issues and questions:

1. Check the logs for error messages
2. Verify configuration settings
3. Test API connectivity
4. Review the troubleshooting section above
