# Voting Pattern Analysis Guide

## 🕵️ Advanced Congressional Collusion Detection

This guide covers sophisticated techniques for detecting coordination, collusion, and unusual voting patterns in congressional data using the rich metadata now automatically extracted by our system.

## 📊 Metadata Foundation

Our system automatically extracts:
- **Policy Areas**: Official CRS classifications (Health, Defense, Finance, etc.)
- **Legislative Subjects**: Detailed CRS subject terms (Budget deficits, Veterans benefits, etc.)
- **Geographic Data**: Member state/district information
- **Temporal Data**: Bill introduction and voting dates
- **Sponsor Networks**: Cosponsorship and amendment relationships

## 🎯 1. Policy Area-Based Collusion Detection

### Industry-Specific Coordination

**Query**: Members who vote together ONLY on specific policy areas
```sql
-- Members who vote together on "Health" bills
SELECT m1.first, m1.last, m1.party, m1.state,
       COUNT(DISTINCT v1.rollcall_id) as health_vote_agreement
FROM votes v1
JOIN votes v2 ON v1.rollcall_id = v2.rollcall_id 
JOIN bills b ON v1.rollcall_id = b.bill_id
JOIN members m1 ON v1.member_id_bioguide = m1.member_id_bioguide
JOIN members m2 ON v2.member_id_bioguide = m2.member_id_bioguide
WHERE b.policy_area = 'Health' 
  AND v1.vote_code = v2.vote_code
  AND m1.member_id_bioguide != m2.member_id_bioguide
GROUP BY m1.member_id_bioguide
HAVING health_vote_agreement > 10;
```

**What This Detects**:
- Healthcare industry lobbying coordination
- Pharmaceutical company influence patterns
- Insurance industry voting blocs

### Cross-Policy Anomalies

**Pattern**: Members who coordinate on one policy area but oppose each other on others
- **Example**: Members vote together on "Health" but oppose on "Finance"
- **Indication**: Issue-specific lobbying rather than general political alliance

## 🎯 2. Subject-Based Deep Dive Analysis

### Legislative Subject Coordination

**Query**: Bills with specific subjects - unusual voting coalitions
```sql
-- Bills with "Budget deficits" subject - analyze voting patterns
SELECT b.bill_id, b.title, b.policy_area,
       COUNT(DISTINCT v.member_id_bioguide) as total_voters,
       COUNT(CASE WHEN v.vote_code = 'Yea' THEN 1 END) as yea_votes,
       COUNT(CASE WHEN v.vote_code = 'Nay' THEN 1 END) as nay_votes
FROM bills b
JOIN bill_subjects bs ON b.bill_id = bs.bill_id
JOIN rollcalls r ON b.bill_id = r.bill_id
JOIN votes v ON r.rollcall_id = v.rollcall_id
WHERE bs.subject_term LIKE '%Budget deficit%'
GROUP BY b.bill_id;
```

**Key Subject Areas to Monitor**:
- **"Abortion"**: Cross-party voting coalitions
- **"Energy"**: Regional vs. national interest conflicts  
- **"Veterans"**: Military district coordination
- **"Agriculture"**: Rural state alliances
- **"Gun control"**: Partisan wedge issues

## 🎯 3. Geographic Coordination Detection

### Regional Voting Blocs

**Query**: States that vote together on specific policy areas
```sql
-- States coordinating on policy areas
SELECT m1.state, m2.state, b.policy_area,
       COUNT(DISTINCT v1.rollcall_id) as agreement_count
FROM votes v1
JOIN votes v2 ON v1.rollcall_id = v2.rollcall_id
JOIN members m1 ON v1.member_id_bioguide = m1.member_id_bioguide
JOIN members m2 ON v2.member_id_bioguide = m2.member_id_bioguide
JOIN bills b ON v1.rollcall_id = b.bill_id
WHERE v1.vote_code = v2.vote_code
  AND m1.state != m2.state
GROUP BY m1.state, m2.state, b.policy_area
HAVING agreement_count > 20;
```

**Expected Regional Patterns**:
- **Energy States**: TX, LA, OK on oil/gas issues
- **Coastal States**: CA, OR, WA on environmental issues
- **Financial States**: NY, NJ on banking regulations
- **Agricultural States**: IA, NE, KS on farm policy

### Border State Coordination

**Detection**: Adjacent states voting identically on local issues
- **Example**: Texas and Louisiana on "Energy" bills
- **Indication**: Regional lobbying or shared economic interests

## 🎯 4. Temporal Pattern Analysis

### Election Cycle Manipulation

**Query**: Voting pattern changes near elections
```sql
-- Pre/post election voting pattern analysis
SELECT b.policy_area, 
       COUNT(CASE WHEN b.introduced_date < '2024-11-01' THEN 1 END) as pre_election,
       COUNT(CASE WHEN b.introduced_date >= '2024-11-01' THEN 1 END) as post_election,
       AVG(CASE WHEN b.introduced_date < '2024-11-01' THEN 
         (SELECT COUNT(*) FROM votes v JOIN rollcalls r ON v.rollcall_id = r.rollcall_id 
          WHERE r.bill_id = b.bill_id AND v.vote_code = 'Yea') END) as avg_pre_yea,
       AVG(CASE WHEN b.introduced_date >= '2024-11-01' THEN 
         (SELECT COUNT(*) FROM votes v JOIN rollcalls r ON v.rollcall_id = r.rollcall_id 
          WHERE r.bill_id = b.bill_id AND v.vote_code = 'Yea') END) as avg_post_yea
FROM bills b
WHERE b.congress = 119
GROUP BY b.policy_area;
```

**Patterns to Detect**:
- **Pre-election positioning**: Members voting differently before elections
- **Post-election changes**: Policy shifts after electoral pressure
- **Holiday/weekend voting**: Low-attention period manipulation

## 🎯 5. Multi-Dimensional Collusion Detection

### Complex Coordination Networks

**Query**: Members coordinating across multiple dimensions
```sql
-- Multi-dimensional coordination analysis
SELECT m1.first, m1.last, m1.party, m1.state,
       COUNT(DISTINCT b.policy_area) as policy_areas_coordinated,
       COUNT(DISTINCT bs.subject_term) as subjects_coordinated,
       COUNT(DISTINCT m2.state) as states_coordinated_with
FROM votes v1
JOIN votes v2 ON v1.rollcall_id = v2.rollcall_id
JOIN members m1 ON v1.member_id_bioguide = m1.member_id_bioguide
JOIN members m2 ON v2.member_id_bioguide = m2.member_id_bioguide
JOIN bills b ON v1.rollcall_id = b.bill_id
JOIN bill_subjects bs ON b.bill_id = bs.bill_id
WHERE v1.vote_code = v2.vote_code
  AND m1.member_id_bioguide != m2.member_id_bioguide
GROUP BY m1.member_id_bioguide
HAVING policy_areas_coordinated > 3 
   AND subjects_coordinated > 10
   AND states_coordinated_with > 5;
```

**What This Reveals**:
- **Super-coordinators**: Members who coordinate across many domains
- **Lobbying networks**: Industry-wide influence patterns
- **Shadow alliances**: Unofficial bipartisan coordination groups

## 🎯 6. Lobbying Impact Assessment

### Industry-Specific Voting Patterns

**Key Industries to Monitor**:

#### Finance and Financial Sector
```sql
-- Banking industry influence patterns
SELECT m.party, m.state,
       COUNT(CASE WHEN v.vote_code = 'Yea' THEN 1 END) as yea_votes,
       COUNT(CASE WHEN v.vote_code = 'Nay' THEN 1 END) as nay_votes
FROM votes v
JOIN members m ON v.member_id_bioguide = m.member_id_bioguide
JOIN bills b ON v.rollcall_id = b.bill_id
WHERE b.policy_area = 'Finance and Financial Sector'
GROUP BY m.party, m.state;
```

#### Energy Sector
```sql
-- Oil/gas vs. renewable energy coordination
SELECT m.state, m.party,
       COUNT(CASE WHEN v.vote_code = 'Yea' THEN 1 END) as yea_votes
FROM votes v
JOIN members m ON v.member_id_bioguide = m.member_id_bioguide
JOIN bills b ON v.rollcall_id = b.bill_id
JOIN bill_subjects bs ON b.bill_id = bs.bill_id
WHERE b.policy_area = 'Energy' 
  AND bs.subject_term LIKE '%Oil%'
GROUP BY m.state, m.party;
```

## 🎯 7. Procedural Manipulation Detection

### Amendment Strategy Patterns

**Query**: Bills with coordinated amendment patterns
```sql
-- Amendment coordination analysis
SELECT b.bill_id, b.title, b.policy_area,
       COUNT(DISTINCT a.amendment_id) as amendment_count,
       COUNT(DISTINCT a.sponsor_bioguide) as unique_sponsors
FROM bills b
JOIN amendments a ON b.bill_id = a.bill_id
WHERE b.congress = 119
GROUP BY b.bill_id
HAVING amendment_count > 5 AND unique_sponsors > 3;
```

**Patterns to Detect**:
- **"Poison pill" amendments**: Coordinated amendments to kill bills
- **Amendment flooding**: Multiple amendments to confuse voting
- **Strategic timing**: Amendments introduced at specific times

### Vote Timing Coordination

**Query**: Members who consistently vote late or abstain
```sql
-- Strategic voting timing analysis
SELECT m.first, m.last, m.party,
       COUNT(CASE WHEN v.vote_code = 'Present' THEN 1 END) as present_votes,
       COUNT(CASE WHEN v.vote_code = 'Not Voting' THEN 1 END) as abstentions,
       COUNT(CASE WHEN v.vote_code IN ('Yea', 'Nay') THEN 1 END) as clear_votes
FROM votes v
JOIN members m ON v.member_id_bioguide = m.member_id_bioguide
GROUP BY m.member_id_bioguide
HAVING present_votes > 10 OR abstentions > 20;
```

## 🔍 Real-World Detection Examples

### Example 1: Healthcare Industry Coordination
**Scenario**: Members who vote together on "Health" policy + "Pharmaceutical" subjects, but oppose each other on "Finance" + "Banking" subjects
**Indication**: Healthcare industry lobbying vs. banking industry influence
**SQL Query**: Multi-policy area coordination analysis

### Example 2: Regional Energy Coordination
**Scenario**: Texas, Louisiana, Oklahoma members voting identically on "Energy" bills with "Oil and gas" subjects, while California, Oregon, Washington vote opposite
**Indication**: Clear regional energy policy coordination
**SQL Query**: Geographic + policy area + subject analysis

### Example 3: Cross-Party Issue Coalitions
**Scenario**: Republicans and Democrats who vote together on "Veterans" issues but oppose each other on "Abortion" or "Gun control"
**Indication**: "Wedge issue" manipulation and strategic voting
**SQL Query**: Party + subject area coordination analysis

## 🚀 Implementation Roadmap

### Phase 1: Basic Pattern Detection (Current)
- ✅ Policy area clustering
- ✅ Subject-based analysis
- ✅ Basic geographic coordination

### Phase 2: Advanced Coordination (Next)
- 🔄 Temporal pattern detection
- 🔄 Multi-dimensional networks
- 🔄 Procedural manipulation

### Phase 3: Real-Time Monitoring (Future)
- 🔄 Live anomaly detection
- 🔄 Predictive coordination alerts
- 🔄 Automated reporting

### Phase 4: Machine Learning Enhancement (Future)
- 🔄 ML-based pattern recognition
- 🔄 Anomaly scoring algorithms
- 🔄 Coordination probability models

## 📊 Analysis Dashboard Features

### Current Capabilities
- **Bill browsing** with policy areas and subjects
- **Member profiles** with voting history
- **Roll call analysis** with vote breakdowns
- **Sponsor networks** with clickable links

### Planned Enhancements
- **Collusion detection** alerts
- **Pattern visualization** charts
- **Coordination network** graphs
- **Anomaly scoring** displays

## 🎯 Key Success Metrics

### Detection Accuracy
- **False positive rate**: < 5%
- **Pattern coverage**: > 80% of coordination types
- **Response time**: < 24 hours for new patterns

### System Performance
- **Data freshness**: < 24 hours old
- **Query response**: < 5 seconds
- **Uptime**: > 99.5%

---

*This guide covers the advanced voting pattern analysis capabilities enabled by our automated metadata extraction system. For implementation details, see the API Reference and Database Schema documentation.*
