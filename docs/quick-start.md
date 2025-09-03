# Quick Start Guide

## 🚀 Get Up and Running in Minutes

This guide provides quick examples and common patterns to get you started with congressional voting pattern analysis.

## ⚡ Quick Setup

### 1. Access the System

**Web Dashboard**: Visit `http://localhost:5000` (or your domain)
**Documentation**: Visit `http://localhost:5000/docs`
**API Endpoints**: Use `http://localhost:5000/api/*`

### 2. Basic Data Exploration

**View All Bills**:
```bash
curl http://localhost:5000/api/bills | jq '.[0:3]'
```

**Get System Summary**:
```bash
curl http://localhost:5000/api/summary
```

**Browse Members**:
```bash
curl http://localhost:5000/api/members | jq '.[0:3]'
```

## 🔍 Common Analysis Patterns

### Policy Area Analysis

**Find All Health Bills**:
```sql
SELECT bill_id, title, sponsor_bioguide, introduced_date
FROM bills 
WHERE policy_area = 'Health' 
  AND congress = 119
ORDER BY introduced_date DESC;
```

**Bills by Policy Area Count**:
```sql
SELECT policy_area, COUNT(*) as bill_count
FROM bills 
WHERE congress = 119
GROUP BY policy_area 
ORDER BY bill_count DESC;
```

### Subject-Based Queries

**Bills with Budget-Related Subjects**:
```sql
SELECT b.bill_id, b.title, b.policy_area, bs.subject_term
FROM bills b
JOIN bill_subjects bs ON b.bill_id = bs.bill_id
WHERE bs.subject_term LIKE '%Budget%'
  AND b.congress = 119
ORDER BY b.introduced_date DESC;
```

**Subject Term Frequency**:
```sql
SELECT subject_term, COUNT(*) as frequency
FROM bill_subjects bs
JOIN bills b ON bs.bill_id = b.bill_id
WHERE b.congress = 119
GROUP BY subject_term
ORDER BY frequency DESC
LIMIT 20;
```

### Voting Pattern Detection

**Members Who Vote Together on Health Bills**:
```sql
SELECT m1.first, m1.last, m1.party, m1.state,
       m2.first as partner_first, m2.last as partner_last, m2.party as partner_party,
       COUNT(DISTINCT v1.rollcall_id) as agreement_count
FROM votes v1
JOIN votes v2 ON v1.rollcall_id = v2.rollcall_id
JOIN members m1 ON v1.member_id_bioguide = m1.member_id_bioguide
JOIN members m2 ON v2.member_id_bioguide = m2.member_id_bioguide
JOIN rollcalls r ON v1.rollcall_id = r.rollcall_id
JOIN bills b ON r.bill_id = b.bill_id
WHERE b.policy_area = 'Health' 
  AND v1.vote_code = v2.vote_code
  AND m1.member_id_bioguide != m2.member_id_bioguide
  AND b.congress = 119
GROUP BY m1.member_id_bioguide, m2.member_id_bioguide
HAVING agreement_count > 5
ORDER BY agreement_count DESC;
```

**Cross-Party Voting Anomalies**:
```sql
SELECT m1.first, m1.last, m1.party, m1.state,
       m2.first as partner_first, m2.last as partner_last, m2.party as partner_party,
       COUNT(DISTINCT v1.rollcall_id) as agreement_count
FROM votes v1
JOIN votes v2 ON v1.rollcall_id = v2.rollcall_id
JOIN members m1 ON v1.member_id_bioguide = m1.member_id_bioguide
JOIN members m2 ON v2.member_id_bioguide = m2.member_id_bioguide
WHERE v1.vote_code = v2.vote_code
  AND m1.party != m2.party
  AND m1.member_id_bioguide != m2.member_id_bioguide
GROUP BY m1.member_id_bioguide, m2.member_id_bioguide
HAVING agreement_count > 10
ORDER BY agreement_count DESC;
```

## 📊 Data Visualization Examples

### JavaScript Dashboard Integration

**Load Bills with Policy Areas**:
```javascript
async function loadBillsByPolicy() {
    const response = await fetch('/api/bills');
    const bills = await response.json();
    
    // Group by policy area
    const policyGroups = bills.reduce((groups, bill) => {
        const area = bill.policy_area || 'Unclassified';
        if (!groups[area]) groups[area] = [];
        groups[area].push(bill);
        return groups;
    }, {});
    
    // Display counts
    Object.entries(policyGroups).forEach(([area, bills]) => {
        console.log(`${area}: ${bills.length} bills`);
    });
}
```

**Voting Pattern Analysis**:
```javascript
async function analyzeVotingPatterns() {
    // Get bills by policy area
    const billsResponse = await fetch('/api/bills');
    const bills = await billsResponse.json();
    
    // Focus on specific policy areas
    const healthBills = bills.filter(b => b.policy_area === 'Health');
    const financeBills = bills.filter(b => b.policy_area === 'Finance and Financial Sector');
    
    console.log(`Health bills: ${healthBills.length}`);
    console.log(`Finance bills: ${financeBills.length}`);
    
    // Analyze sponsor patterns
    const healthSponsors = [...new Set(healthBills.map(b => b.sponsor_bioguide))];
    const financeSponsors = [...new Set(financeBills.map(b => b.sponsor_bioguide))];
    
    // Find sponsors active in both areas
    const crossAreaSponsors = healthSponsors.filter(id => financeSponsors.includes(id));
    console.log(`Cross-area sponsors: ${crossAreaSponsors.length}`);
}
```

## 🐍 Python Analysis Examples

### Basic Data Loading

```python
import requests
import pandas as pd
from collections import defaultdict

# Load bills data
response = requests.get('http://localhost:5000/api/bills')
bills = response.json()

# Convert to DataFrame
df_bills = pd.DataFrame(bills)

# Basic analysis
print(f"Total bills: {len(df_bills)}")
print(f"Policy areas: {df_bills['policy_area'].nunique()}")
print(f"Bills with subjects: {df_bills['bill_id'].nunique()}")
```

### Policy Area Analysis

```python
# Policy area distribution
policy_counts = df_bills['policy_area'].value_counts()
print("Top policy areas:")
print(policy_counts.head(10))

# Bills by policy area and party
policy_party = df_bills.groupby(['policy_area', 'sponsor_party']).size().unstack(fill_value=0)
print("\nBills by policy area and party:")
print(policy_party)
```

### Subject Term Analysis

```python
# Load subjects data
subjects_response = requests.get('http://localhost:5000/api/subjects')
subjects = subjects_response.json()

# Create subject frequency analysis
subject_counts = defaultdict(int)
for subject in subjects:
    subject_counts[subject['subject_term']] += 1

# Top subjects
top_subjects = sorted(subject_counts.items(), key=lambda x: x[1], reverse=True)[:20]
print("Top 20 subject terms:")
for subject, count in top_subjects:
    print(f"  {subject}: {count}")
```

### Voting Pattern Detection

```python
# Load voting data
votes_response = requests.get('http://localhost:5000/api/votes')
votes = votes_response.json()

# Create voting matrix
voting_matrix = defaultdict(lambda: defaultdict(int))
for vote in votes:
    member = vote['member_id_bioguide']
    rollcall = vote['rollcall_id']
    decision = vote['vote_code']
    voting_matrix[member][rollcall] = decision

# Find voting agreements
def calculate_agreement(member1, member2):
    common_votes = 0
    agreements = 0
    
    for rollcall in voting_matrix[member1]:
        if rollcall in voting_matrix[member2]:
            common_votes += 1
            if voting_matrix[member1][rollcall] == voting_matrix[member2][rollcall]:
                agreements += 1
    
    return agreements / common_votes if common_votes > 0 else 0

# Example: Check agreement between two members
member1 = "S000123"  # Replace with actual member ID
member2 = "S000456"  # Replace with actual member ID
agreement = calculate_agreement(member1, member2)
print(f"Voting agreement between {member1} and {member2}: {agreement:.2%}")
```

## 🔍 Advanced Analysis Patterns

### Multi-Dimensional Coordination

**Members Coordinating Across Multiple Policy Areas**:
```sql
SELECT m.first, m.last, m.party, m.state,
       COUNT(DISTINCT b.policy_area) as policy_areas_active,
       COUNT(DISTINCT bs.subject_term) as subjects_active
FROM members m
JOIN bills b ON m.member_id_bioguide = b.sponsor_bioguide
JOIN bill_subjects bs ON b.bill_id = bs.bill_id
WHERE b.congress = 119
GROUP BY m.member_id_bioguide
HAVING policy_areas_active > 2 AND subjects_active > 5
ORDER BY policy_areas_active DESC, subjects_active DESC;
```

**Geographic Voting Patterns**:
```sql
SELECT m1.state, m2.state, b.policy_area,
       COUNT(DISTINCT v1.rollcall_id) as agreement_count
FROM votes v1
JOIN votes v2 ON v1.rollcall_id = v2.rollcall_id
JOIN members m1 ON v1.member_id_bioguide = m1.member_id_bioguide
JOIN members m2 ON v2.member_id_bioguide = m2.member_id_bioguide
JOIN rollcalls r ON v1.rollcall_id = r.rollcall_id
JOIN bills b ON r.bill_id = b.bill_id
WHERE v1.vote_code = v2.vote_code
  AND m1.state != m2.state
  AND b.congress = 119
GROUP BY m1.state, m2.state, b.policy_area
HAVING agreement_count > 15
ORDER BY agreement_count DESC;
```

### Temporal Analysis

**Election Cycle Effects**:
```sql
SELECT 
    CASE 
        WHEN b.introduced_date < '2024-11-01' THEN 'Pre-election'
        ELSE 'Post-election'
    END as election_period,
    b.policy_area,
    COUNT(*) as bill_count,
    AVG(CASE WHEN v.vote_code = 'Yea' THEN 1 ELSE 0 END) as avg_yea_rate
FROM bills b
LEFT JOIN rollcalls r ON b.bill_id = r.bill_id
LEFT JOIN votes v ON r.rollcall_id = v.rollcall_id
WHERE b.congress = 119
  AND b.introduced_date >= '2024-01-01'
GROUP BY election_period, b.policy_area
ORDER BY election_period, bill_count DESC;
```

## 🚨 Common Pitfalls

### Data Quality Issues

**Missing Policy Areas**:
```sql
-- Check for bills without policy areas
SELECT COUNT(*) as missing_policy_areas
FROM bills 
WHERE policy_area IS NULL OR policy_area = '';

-- Bills with missing metadata
SELECT bill_id, title, introduced_date
FROM bills 
WHERE policy_area IS NULL 
  AND congress = 119
ORDER BY introduced_date DESC;
```

**Incomplete Subject Coverage**:
```sql
-- Bills with few subjects
SELECT b.bill_id, b.title, COUNT(bs.subject_term) as subject_count
FROM bills b
LEFT JOIN bill_subjects bs ON b.bill_id = bs.bill_id
WHERE b.congress = 119
GROUP BY b.bill_id
HAVING subject_count < 3
ORDER BY subject_count ASC;
```

### Performance Considerations

**Optimize Large Queries**:
```sql
-- Use LIMIT for testing
SELECT * FROM bills WHERE policy_area = 'Health' LIMIT 100;

-- Add date filters to reduce scope
SELECT * FROM bills 
WHERE policy_area = 'Health' 
  AND introduced_date >= '2024-01-01'
LIMIT 100;
```

## 📚 Next Steps

### Deep Dive Topics

1. **Advanced SQL Queries**: Complex JOINs and subqueries
2. **Statistical Analysis**: Correlation and significance testing
3. **Network Analysis**: Graph-based coordination detection
4. **Machine Learning**: Pattern recognition and prediction

### Resources

- **Voting Pattern Analysis**: `/docs/voting-pattern-analysis.md`
- **API Reference**: `/docs/api-reference.md`
- **Database Schema**: `/docs/database-schema.md`
- **Deployment Guide**: `/docs/deployment.md`

### Community

- **GitHub Issues**: Report bugs and request features
- **Discussions**: Share analysis techniques and findings
- **Contributions**: Submit improvements and new analysis patterns

---

*This quick start guide provides the essential patterns and examples to begin congressional voting pattern analysis. For comprehensive coverage, explore the full documentation suite.*
