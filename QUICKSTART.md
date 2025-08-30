# Quick Start Guide

This guide will help you get the Congressional Coalition Tracker up and running quickly.

## Prerequisites

- Python 3.11+
- MySQL or PostgreSQL database
- Git

## Installation

1. **Clone the repository** (if not already done):
   ```bash
   git clone <repository-url>
   cd congressional-coalitions
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up the database**:
   ```bash
   # Create database (MySQL example)
   mysql -u root -p -e "CREATE DATABASE congressional_coalitions;"
   
   # Set up schema
   python scripts/setup_db.py --database-url mysql://username:password@localhost/congressional_coalitions
   ```

4. **Configure environment variables** (optional):
   ```bash
   export DATABASE_URL="mysql://username:password@localhost/congressional_coalitions"
   export GOVINFO_API_KEY="your_govinfo_api_key"  # Optional, for GovInfo access
   ```

## Quick Test Run

1. **Load some sample data** (Congress 119, limited bills):
   ```bash
   # Load bills from current Congress
   python scripts/govinfo_loader.py --congress 119 --chamber house --limit 10
   
   # Load House votes
   python scripts/house_vote_loader.py --congress 119 --limit 5
   
   # Load Senate votes
   python scripts/senate_vote_loader.py --congress 119 --limit 5
   ```

2. **Run analysis**:
   ```bash
   # Analyze House coalitions for last 90 days
   python scripts/analyze_coalitions.py --congress 119 --chamber house --window 90 --print-summary
   ```

## Expected Output

The analysis will produce:
- **Coalition detection**: Groups of members who vote together and cosponsor bills together
- **Outlier detection**: Members who vote unexpectedly (breaking party lines or against predictions)
- **Bipartisan hotspots**: Bills with high cross-party cosponsorship

Example output:
```
CONGRESSIONAL COALITION ANALYSIS SUMMARY
================================================================================
Congress: 119
Chamber: House
Analysis Window: 2024-01-01 to 2024-04-01 (90 days)
Analysis Date: 2024-04-01T10:30:00

Key Findings:
  • Total Members Analyzed: 435
  • Coalitions Detected: 8
  • Outlier Votes Found: 23
  • Bipartisan Bills: 15

Coalition Details:
  • Coalition 0: 45 members, Partisan
    Top subjects: Health, Education, Veterans
  • Coalition 1: 38 members, Bipartisan
    Top subjects: Infrastructure, Technology, Energy

Top Bipartisan Bills:
  1. Infrastructure Investment and Jobs Act... (Score: 0.85)
  2. Cybersecurity Enhancement Act... (Score: 0.82)
  3. Veterans Health Care Improvement... (Score: 0.78)
```

## Data Sources

The system uses these authoritative data sources:
- **GovInfo BILLSTATUS**: Bills, sponsors, cosponsors, actions, subjects
- **House Clerk**: Roll-call votes
- **Senate LIS**: Roll-call votes

## Next Steps

1. **Load more data**: Remove the `--limit` flags to load complete datasets
2. **Customize analysis**: Modify `config.yaml` for different analysis parameters
3. **Build dashboard**: Use the JSON output to create visualizations
4. **Extend functionality**: Add more analysis modules or data sources

## Troubleshooting

**Database connection issues**:
- Check your database URL format
- Ensure database server is running
- Verify user permissions

**No data found**:
- Check if Congress number is correct
- Verify date ranges
- Ensure data sources are accessible

**Memory issues**:
- Reduce analysis window size
- Use smaller Congress numbers
- Process data in chunks

## Support

For issues or questions:
1. Check the logs in `logs/congressional_coalitions.log`
2. Review the full documentation in `README.md`
3. Examine the configuration in `config.yaml`


