# Congressional Coalition Analysis Documentation

Welcome to the Congressional Coalition Analysis system documentation. This system analyzes congressional data to detect evolving coalitions, bipartisan cooperation, and voting patterns in the US Congress.

## 📚 Documentation Index

- **[Voting Pattern Analysis Guide](./voting-pattern-analysis.md)** - Comprehensive guide to detecting collusion and coordination patterns
- **[API Reference](./api-reference.md)** - Complete API endpoint documentation
- **[Database Schema](./database-schema.md)** - Database structure and relationships
- **[Deployment Guide](./deployment.md)** - System setup and maintenance
- **[Metadata Extraction](./metadata-extraction.md)** - How bill metadata is automatically populated

## 🎯 System Overview

This system provides:

- **Automated bill discovery** via Congress.gov API integration
- **Rich metadata extraction** including policy areas and legislative subjects
- **Advanced voting pattern analysis** for collusion detection
- **Real-time data updates** via automated cron jobs
- **Web dashboard** for exploring congressional data

## 🚀 Quick Start

1. **View the Dashboard**: Visit the main application at `/`
2. **Explore Bills**: Browse House bills with sponsor information at `/api/bills`
3. **Analyze Members**: View member details and voting patterns at `/api/members`
4. **Check Roll Calls**: Examine voting records at `/api/rollcalls`

## 🔍 Key Features

- **Sponsor Hyperlinks**: Clickable sponsor names linking to member pages
- **Policy Area Classification**: Automatic categorization of bills by policy domain
- **Subject Term Extraction**: Detailed legislative subject classifications
- **Voting Pattern Detection**: Advanced algorithms for coordination analysis

## 📊 Data Sources

- **Congress.gov API**: Primary source for bill data and metadata
- **House Clerk**: Roll call vote data
- **Senate LIS**: Senate voting records
- **CRS Classifications**: Official policy area and subject classifications

## 🛠️ Technical Stack

- **Backend**: Python Flask with SQLAlchemy
- **Database**: MySQL with optimized schemas
- **Frontend**: JavaScript with dynamic data loading
- **Automation**: Cron jobs for data updates
- **Containerization**: Docker for deployment

---

*Last updated: September 2025*
