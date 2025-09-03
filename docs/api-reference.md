# API Reference

## 📡 Complete API Endpoint Documentation

This document provides comprehensive documentation for all API endpoints in the Congressional Coalition Analysis system.

## 🔗 Base URL

All API endpoints are relative to the base URL of your deployment:
- **Local Development**: `http://localhost:5000`
- **Production**: `https://yourdomain.com`

## 📊 Core Endpoints

### GET /api/bills

**Description**: Retrieve House bills with comprehensive metadata including policy areas and subjects.

**Response Format**:
```json
[
  {
    "id": "hr-1234-119",
    "title": "Bill Title",
    "congress": 119,
    "chamber": "House",
    "number": 1234,
    "type": "HR",
    "sponsor": "John Smith",
    "sponsor_bioguide": "S000123",
    "sponsor_party": "D",
    "cosponsor_count": 5,
    "introduced_date": "2025-01-15",
    "last_action_date": "2025-02-01",
    "last_action_code": "INTRODUCED"
  }
]
```

**Query Parameters**:
- `congress` (optional): Filter by Congress number (default: 119)
- `chamber` (optional): Filter by chamber (default: house)

### GET /api/members

**Description**: Retrieve all congressional members with their details.

**Response Format**:
```json
[
  {
    "member_id_bioguide": "S000123",
    "first": "John",
    "last": "Smith",
    "party": "D",
    "state": "CA",
    "district": 1,
    "start_date": "2023-01-03",
    "end_date": null
  }
]
```

### GET /api/rollcalls

**Description**: Retrieve roll call voting records.

**Response Format**:
```json
[
  {
    "rollcall_id": "119-2025-001",
    "congress": 119,
    "chamber": "house",
    "session": 1,
    "rc_number": 1,
    "date": "2025-01-15",
    "question": "On Passage",
    "bill_id": "hr-1234-119"
  }
]
```

### GET /api/summary

**Description**: Get system summary statistics.

**Response Format**:
```json
{
  "total_members": 435,
  "total_bills": 9043,
  "total_rollcalls": 1500,
  "congress": 119,
  "last_updated": "2025-09-03T18:45:00Z"
}
```

## 🔍 Analysis Endpoints

### GET /api/analysis/{congress}/{chamber}

**Description**: Retrieve coalition analysis data for a specific Congress and chamber.

**Path Parameters**:
- `congress`: Congress number (e.g., 119)
- `chamber`: Chamber type (house, senate)

**Response Format**:
```json
{
  "congress": 119,
  "chamber": "house",
  "analysis_date": "2025-09-03T18:45:00Z",
  "coalitions": [
    {
      "name": "Democratic Party",
      "member_count": 213,
      "average_agreement": 0.85
    }
  ]
}
```

## 📋 Bill Detail Endpoints

### GET /api/bill/{bill_id}

**Description**: Get detailed information about a specific bill.

**Path Parameters**:
- `bill_id`: Bill identifier (e.g., hr-1234-119)

**Response Format**:
```json
{
  "bill_id": "hr-1234-119",
  "title": "Bill Title",
  "congress": 119,
  "chamber": "house",
  "type": "HR",
  "number": 1234,
  "sponsor": {
    "name": "John Smith",
    "bioguide": "S000123",
    "party": "D",
    "state": "CA"
  },
  "policy_area": "Health",
  "subjects": [
    "Healthcare",
    "Insurance",
    "Pharmaceuticals"
  ],
  "cosponsors": [
    {
      "name": "Jane Doe",
      "bioguide": "D000456",
      "party": "D",
      "state": "NY"
    }
  ],
  "actions": [
    {
      "date": "2025-01-15",
      "action": "INTRODUCED",
      "description": "Bill introduced in House"
    }
  ]
}
```

## 🗳️ Voting Endpoints

### GET /api/votes/{rollcall_id}

**Description**: Get detailed voting results for a specific roll call.

**Path Parameters**:
- `rollcall_id`: Roll call identifier

**Response Format**:
```json
{
  "rollcall_id": "119-2025-001",
  "bill_id": "hr-1234-119",
  "question": "On Passage",
  "date": "2025-01-15",
  "result": "Passed",
  "votes": {
    "Yea": 250,
    "Nay": 180,
    "Present": 3,
    "Not Voting": 2
  },
  "member_votes": [
    {
      "member_id": "S000123",
      "name": "John Smith",
      "party": "D",
      "state": "CA",
      "vote": "Yea"
    }
  ]
}
```

## 🔐 Authentication

**Current Status**: No authentication required for read endpoints.

**Future Plans**: API key authentication for write operations and rate limiting.

## 📊 Rate Limiting

**Current Limits**:
- **Read Endpoints**: No rate limiting
- **Analysis Endpoints**: 100 requests per hour per IP

**Future Plans**: Implement comprehensive rate limiting with API keys.

## 🚨 Error Handling

### Standard Error Response Format

```json
{
  "error": "Error description",
  "code": "ERROR_CODE",
  "timestamp": "2025-09-03T18:45:00Z"
}
```

### Common HTTP Status Codes

- **200 OK**: Request successful
- **400 Bad Request**: Invalid parameters
- **404 Not Found**: Resource not found
- **429 Too Many Requests**: Rate limit exceeded
- **500 Internal Server Error**: Server error

### Error Examples

**Invalid Bill ID**:
```json
{
  "error": "Bill not found: hr-9999-119",
  "code": "BILL_NOT_FOUND",
  "timestamp": "2025-09-03T18:45:00Z"
}
```

**Rate Limit Exceeded**:
```json
{
  "error": "Rate limit exceeded. Try again in 3600 seconds.",
  "code": "RATE_LIMIT_EXCEEDED",
  "timestamp": "2025-09-03T18:45:00Z"
}
```

## 📈 Usage Examples

### JavaScript/Fetch API

```javascript
// Get all bills
const response = await fetch('/api/bills');
const bills = await response.json();

// Get specific bill
const billResponse = await fetch('/api/bill/hr-1234-119');
const bill = await billResponse.json();

// Get analysis data
const analysisResponse = await fetch('/api/analysis/119/house');
const analysis = await analysisResponse.json();
```

### Python/Requests

```python
import requests

# Get all bills
response = requests.get('http://localhost:5000/api/bills')
bills = response.json()

# Get specific bill
bill_response = requests.get('http://localhost:5000/api/bill/hr-1234-119')
bill = bill_response.json()

# Get analysis data
analysis_response = requests.get('http://localhost:5000/api/analysis/119/house')
analysis = analysis_response.json()
```

### cURL

```bash
# Get all bills
curl http://localhost:5000/api/bills

# Get specific bill
curl http://localhost:5000/api/bill/hr-1234-119

# Get analysis data
curl http://localhost:5000/api/analysis/119/house
```

## 🔄 Data Freshness

**Update Frequency**:
- **Bill Data**: Updated daily via automated cron jobs
- **Voting Data**: Updated within 24 hours of roll calls
- **Member Data**: Updated when changes occur

**Last Updated**: All endpoints include timestamp information in responses.

## 🚀 Future Endpoints

**Planned for Next Release**:
- `POST /api/analysis/run`: Trigger custom analysis
- `GET /api/patterns`: Retrieve detected voting patterns
- `GET /api/alerts`: Get coordination alerts
- `POST /api/queries`: Execute custom SQL queries

---

*This API provides programmatic access to all congressional data and analysis capabilities. For implementation examples, see the Quick Start guide.*
