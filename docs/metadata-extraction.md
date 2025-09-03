# Metadata Extraction Guide

## 🔍 How Bill Metadata is Automatically Populated

This guide explains how our system automatically extracts rich metadata from Congress.gov API to enable sophisticated voting pattern analysis.

## 📊 Metadata Sources

### Congress.gov API Integration

Our system integrates with the official Congress.gov API to extract:

- **Bill Information**: Titles, sponsors, introduction dates, policy areas
- **Legislative Subjects**: CRS (Congressional Research Service) classification terms
- **Policy Areas**: Official government policy domain classifications
- **Sponsor Networks**: Cosponsorship relationships and amendment sponsors

### Data Flow

```
Congress.gov API → Enhanced Daily Update Script → Database → Analysis Engine
```

## 🚀 Automatic Extraction Process

### Daily Discovery Workflow

**Every day at 6 AM**, our cron job runs:

```bash
# Automated daily discovery
0 6 * * * cd /home/jmknapp/congressional-coalitions && \
  venv/bin/python scripts/enhanced_daily_update.py --congress 119 --max-bills 100
```

**For each bill discovered:**

1. **Fetch Bill Data**: Congress.gov API call for basic bill information
2. **Extract Policy Area**: Official CRS policy classification
3. **Fetch Subjects**: Detailed legislative subject terms
4. **Update Database**: Store metadata in `bills.policy_area` and `bill_subjects`
5. **Track Updates**: Maintain `last_updated` timestamp for change detection

### Enhanced Daily Update Script

The `enhanced_daily_update.py` script now includes:

```python
def fetch_bill_subjects(self, congressgov_id: str) -> List[str]:
    """Fetch bill subjects from Congress.gov API."""
    subjects = []
    subjects_url = f"https://api.congress.gov/v3/bill/{congressgov_id}/subjects"
    headers = {'X-API-Key': self.congressgov_api_key}
    
    try:
        response = self.session.get(subjects_url, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if 'subjects' in data and 'legislativeSubjects' in data['subjects']:
                for subject in data['subjects']['legislativeSubjects']:
                    if 'name' in subject:
                        subjects.append(subject['name'])
    except Exception as e:
        logger.debug(f"Error fetching subjects: {e}")
    
    return subjects
```

## 📋 Metadata Fields Extracted

### Policy Areas

**Official CRS Classifications:**
- **Health**: Healthcare, pharmaceuticals, insurance
- **Education**: Schools, universities, student programs
- **Finance and Financial Sector**: Banking, securities, financial regulation
- **Energy**: Oil, gas, renewable energy, nuclear
- **Defense**: Military, national security, veterans
- **Transportation**: Infrastructure, highways, aviation
- **Agriculture**: Farming, rural development, food safety
- **Environment**: Climate, pollution, conservation

### Legislative Subjects

**Detailed CRS Terms:**
- **Budget deficits and national debt**
- **Congressional operations and organization**
- **Veterans benefits and health care**
- **Oil and gas resources**
- **School athletics**
- **Sex, gender, sexual orientation discrimination**
- **Legislative rules and procedure**

## 🔧 Backfill Capability

### Historical Metadata Population

For existing bills without metadata, use the backfill script:

```bash
# Backfill all bills for Congress 119
python scripts/backfill_bill_metadata.py --congress 119 --api-key YOUR_API_KEY

# Test with limited bills first
python scripts/backfill_bill_metadata.py --congress 119 --limit 10 --api-key YOUR_API_KEY
```

### Backfill Process

1. **Identify Missing Data**: Find bills without policy areas or subjects
2. **API Calls**: Fetch metadata from Congress.gov for each bill
3. **Database Updates**: Populate missing fields and create subject records
4. **Rate Limiting**: Respect API limits with intelligent delays

## 📊 Database Schema

### Bills Table

```sql
CREATE TABLE bills (
    bill_id VARCHAR(50) PRIMARY KEY,
    congress INT NOT NULL,
    chamber VARCHAR(10) NOT NULL,
    number INT NOT NULL,
    type VARCHAR(10) NOT NULL,
    title VARCHAR(1000),
    introduced_date DATE,
    sponsor_bioguide VARCHAR(20),
    policy_area VARCHAR(200),           -- NEW: CRS policy classification
    summary_short VARCHAR(2000),
    last_updated DATETIME,             -- NEW: Change tracking
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW()
);
```

### Bill Subjects Table

```sql
CREATE TABLE bill_subjects (
    id INT PRIMARY KEY AUTO_INCREMENT,
    bill_id VARCHAR(50) FOREIGN KEY REFERENCES bills(bill_id),
    subject_term VARCHAR(200) NOT NULL,  -- CRS legislative subject
    created_at DATETIME DEFAULT NOW()
);
```

## 🎯 Metadata Quality Assurance

### Validation Checks

**Policy Area Validation:**
- Must be valid CRS classification
- Cannot be empty for active bills
- Historical bills may have NULL values

**Subject Term Validation:**
- Must be valid CRS subject term
- Multiple subjects per bill allowed
- Terms are standardized and consistent

### Error Handling

**API Failures:**
- Rate limit detection and backoff
- Network timeout handling
- Graceful degradation for missing data

**Data Quality:**
- Duplicate subject prevention
- Policy area consistency checks
- Sponsor relationship validation

## 🚀 Advanced Analysis Enabled

### Policy Area Analysis

```sql
-- Bills by policy area
SELECT policy_area, COUNT(*) as bill_count
FROM bills 
WHERE policy_area IS NOT NULL
GROUP BY policy_area
ORDER BY bill_count DESC;
```

### Subject-Based Queries

```sql
-- Bills with specific subjects
SELECT b.bill_id, b.title, b.policy_area
FROM bills b
JOIN bill_subjects bs ON b.bill_id = bs.bill_id
WHERE bs.subject_term LIKE '%Budget%'
ORDER BY b.introduced_date DESC;
```

### Multi-Dimensional Analysis

```sql
-- Policy area + subject combinations
SELECT b.policy_area, bs.subject_term, COUNT(*) as count
FROM bills b
JOIN bill_subjects bs ON b.bill_id = bs.bill_id
GROUP BY b.policy_area, bs.subject_term
HAVING count > 5
ORDER BY count DESC;
```

## 🔄 Maintenance and Updates

### Regular Monitoring

**Daily Checks:**
- New bill discovery success rate
- Metadata extraction completion
- API rate limit status

**Weekly Reviews:**
- Data quality metrics
- Missing metadata analysis
- API performance trends

### Continuous Improvement

**Metadata Enhancement:**
- Additional subject categories
- Enhanced policy area granularity
- Cross-reference with external datasets

**Performance Optimization:**
- API call efficiency
- Database query optimization
- Caching strategies

## 📈 Success Metrics

### Extraction Coverage

- **Policy Areas**: >95% of active bills
- **Subjects**: >90% of bills with 3+ subjects
- **Freshness**: <24 hours from bill introduction

### Quality Indicators

- **Accuracy**: >98% policy area correctness
- **Completeness**: >90% subject coverage
- **Consistency**: Standardized terminology across all bills

---

*This metadata extraction system provides the foundation for advanced congressional voting pattern analysis and collusion detection. The automated daily updates ensure data freshness while the backfill capability maintains historical completeness.*
