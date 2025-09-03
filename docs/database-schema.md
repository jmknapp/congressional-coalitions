# Database Schema

## 🗄️ Complete Database Structure and Relationships

This document describes the database schema for the Congressional Coalition Analysis system, including all tables, relationships, and data models.

## 📊 Database Overview

**Database Name**: `congressional_coalitions`  
**Engine**: MySQL 8.0+  
**Character Set**: UTF-8  
**Collation**: utf8mb4_unicode_ci

## 🏗️ Core Tables

### Members Table

**Purpose**: Store congressional member information and demographics.

```sql
CREATE TABLE members (
    member_id_bioguide VARCHAR(20) PRIMARY KEY,
    icpsr VARCHAR(20),
    lis_id VARCHAR(20),
    first VARCHAR(100),
    last VARCHAR(100),
    party VARCHAR(10),
    state VARCHAR(2),
    district INT,
    start_date DATE,
    end_date DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

**Key Fields**:
- `member_id_bioguide`: Primary identifier from Congress.gov
- `party`: Political party (D, R, I, etc.)
- `state`: Two-letter state code
- `district`: Congressional district number (House only)

**Indexes**:
```sql
CREATE INDEX idx_members_party ON members(party);
CREATE INDEX idx_members_state ON members(state);
CREATE INDEX idx_members_start_date ON members(start_date);
```

### Bills Table

**Purpose**: Store bill information and metadata.

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
    policy_area VARCHAR(200),
    summary_short VARCHAR(2000),
    last_updated DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (sponsor_bioguide) REFERENCES members(member_id_bioguide)
);
```

**Key Fields**:
- `bill_id`: Unique identifier (e.g., hr-1234-119)
- `policy_area`: CRS policy classification
- `last_updated`: Timestamp for change tracking

**Indexes**:
```sql
CREATE INDEX idx_bills_congress ON bills(congress);
CREATE INDEX idx_bills_chamber ON bills(chamber);
CREATE INDEX idx_bills_policy_area ON bills(policy_area);
CREATE INDEX idx_bills_introduced_date ON bills(introduced_date);
CREATE INDEX idx_bills_last_updated ON bills(last_updated);
```

### Bill Subjects Table

**Purpose**: Store detailed legislative subject classifications.

```sql
CREATE TABLE bill_subjects (
    id INT PRIMARY KEY AUTO_INCREMENT,
    bill_id VARCHAR(50) NOT NULL,
    subject_term VARCHAR(200) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON DELETE CASCADE
);
```

**Key Fields**:
- `subject_term`: CRS legislative subject term
- `bill_id`: Reference to parent bill

**Indexes**:
```sql
CREATE INDEX idx_bill_subjects_bill_id ON bill_subjects(bill_id);
CREATE INDEX idx_bill_subjects_subject_term ON bill_subjects(subject_term);
```

### Cosponsors Table

**Purpose**: Track bill cosponsorship relationships.

```sql
CREATE TABLE cosponsors (
    id INT PRIMARY KEY AUTO_INCREMENT,
    bill_id VARCHAR(50) NOT NULL,
    member_id_bioguide VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    is_original BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON DELETE CASCADE,
    FOREIGN KEY (member_id_bioguide) REFERENCES members(member_id_bioguide),
    UNIQUE KEY unique_cosponsor (bill_id, member_id_bioguide)
);
```

**Key Fields**:
- `is_original`: Whether member was original cosponsor
- `date`: When cosponsorship was added

**Indexes**:
```sql
CREATE INDEX idx_cosponsors_bill_id ON cosponsors(bill_id);
CREATE INDEX idx_cosponsors_member_id ON cosponsors(member_id_bioguide);
CREATE INDEX idx_cosponsors_date ON cosponsors(date);
```

### Actions Table

**Purpose**: Track bill legislative actions and status changes.

```sql
CREATE TABLE actions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    bill_id VARCHAR(50) NOT NULL,
    action_date DATE NOT NULL,
    action_code VARCHAR(50) NOT NULL,
    text VARCHAR(1000),
    committee_code VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON DELETE CASCADE
);
```

**Key Fields**:
- `action_code`: Legislative action type (INTRODUCED, REFERRED, etc.)
- `committee_code`: Committee handling the action

**Indexes**:
```sql
CREATE INDEX idx_actions_bill_id ON actions(bill_id);
CREATE INDEX idx_actions_action_date ON actions(action_date);
CREATE INDEX idx_actions_action_code ON actions(action_code);
```

### Rollcalls Table

**Purpose**: Store roll call vote information.

```sql
CREATE TABLE rollcalls (
    rollcall_id VARCHAR(50) PRIMARY KEY,
    congress INT NOT NULL,
    chamber VARCHAR(10) NOT NULL,
    session INT NOT NULL,
    rc_number INT NOT NULL,
    date DATE NOT NULL,
    question VARCHAR(500),
    bill_id VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bill_id) REFERENCES bills(bill_id)
);
```

**Key Fields**:
- `rollcall_id`: Unique roll call identifier
- `bill_id`: Associated bill (nullable for procedural votes)

**Indexes**:
```sql
CREATE INDEX idx_rollcalls_congress ON rollcalls(congress);
CREATE INDEX idx_rollcalls_chamber ON rollcalls(chamber);
CREATE INDEX idx_rollcalls_date ON rollcalls(date);
CREATE INDEX idx_rollcalls_bill_id ON rollcalls(bill_id);
```

### Votes Table

**Purpose**: Store individual member votes on roll calls.

```sql
CREATE TABLE votes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    rollcall_id VARCHAR(50) NOT NULL,
    member_id_bioguide VARCHAR(20) NOT NULL,
    vote_code ENUM('Yea', 'Nay', 'Present', 'Not Voting') NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rollcall_id) REFERENCES rollcalls(rollcall_id) ON DELETE CASCADE,
    FOREIGN KEY (member_id_bioguide) REFERENCES members(member_id_bioguide),
    UNIQUE KEY unique_vote (rollcall_id, member_id_bioguide)
);
```

**Key Fields**:
- `vote_code`: Member's voting decision
- `rollcall_id`: Reference to roll call

**Indexes**:
```sql
CREATE INDEX idx_votes_rollcall_id ON votes(rollcall_id);
CREATE INDEX idx_votes_member_id ON votes(member_id_bioguide);
CREATE INDEX idx_votes_vote_code ON votes(vote_code);
```

### Amendments Table

**Purpose**: Track bill amendments and their sponsors.

```sql
CREATE TABLE amendments (
    amendment_id VARCHAR(50) PRIMARY KEY,
    bill_id VARCHAR(50) NOT NULL,
    sponsor_bioguide VARCHAR(20),
    type VARCHAR(50),
    purpose VARCHAR(1000),
    introduced_date DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON DELETE CASCADE,
    FOREIGN KEY (sponsor_bioguide) REFERENCES members(member_id_bioguide)
);
```

**Key Fields**:
- `amendment_id`: Unique amendment identifier
- `type`: Amendment type (substitute, perfecting, etc.)

**Indexes**:
```sql
CREATE INDEX idx_amendments_bill_id ON amendments(bill_id);
CREATE INDEX idx_amendments_sponsor ON amendments(sponsor_bioguide);
CREATE INDEX idx_amendments_introduced_date ON amendments(introduced_date);
```

## 🔗 Table Relationships

### Entity Relationship Diagram

```
members (1) ←→ (N) bills
  ↑                    ↑
  |                    |
  |                    |
votes (N) ←→ (1) rollcalls
  ↑                    ↑
  |                    |
  |                    |
bill_subjects (N) ←→ (1) bills
  ↑                    ↑
  |                    |
  |                    |
cosponsors (N) ←→ (1) bills
  ↑                    ↑
  |                    |
  |                    |
amendments (N) ←→ (1) bills
  ↑                    ↑
  |                    |
  |                    |
actions (N) ←→ (1) bills
```

### Foreign Key Constraints

```sql
-- Bills reference members (sponsors)
ALTER TABLE bills 
ADD CONSTRAINT fk_bills_sponsor 
FOREIGN KEY (sponsor_bioguide) REFERENCES members(member_id_bioguide);

-- Cosponsors reference bills and members
ALTER TABLE cosponsors 
ADD CONSTRAINT fk_cosponsors_bill 
FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON DELETE CASCADE;

ALTER TABLE cosponsors 
ADD CONSTRAINT fk_cosponsors_member 
FOREIGN KEY (member_id_bioguide) REFERENCES members(member_id_bioguide);

-- Votes reference rollcalls and members
ALTER TABLE votes 
ADD CONSTRAINT fk_votes_rollcall 
FOREIGN KEY (rollcall_id) REFERENCES rollcalls(rollcall_id) ON DELETE CASCADE;

ALTER TABLE votes 
ADD CONSTRAINT fk_votes_member 
FOREIGN KEY (member_id_bioguide) REFERENCES members(member_id_bioguide);
```

## 📊 Data Types and Constraints

### String Fields

- **Short Text**: VARCHAR(50) for IDs, codes
- **Medium Text**: VARCHAR(200) for names, subjects
- **Long Text**: VARCHAR(1000) for titles, descriptions
- **Very Long Text**: VARCHAR(2000) for summaries

### Date Fields

- **Dates**: DATE for calendar dates
- **Timestamps**: DATETIME for precise timing
- **Auto-timestamps**: CURRENT_TIMESTAMP for creation/update tracking

### Enumerated Fields

- **Vote Codes**: ENUM('Yea', 'Nay', 'Present', 'Not Voting')
- **Chambers**: VARCHAR(10) with validation
- **Parties**: VARCHAR(10) for political affiliations

## 🔍 Query Optimization

### Common Query Patterns

**Bill Discovery by Policy Area**:
```sql
SELECT b.*, m.first, m.last, m.party, m.state
FROM bills b
JOIN members m ON b.sponsor_bioguide = m.member_id_bioguide
WHERE b.policy_area = 'Health'
  AND b.congress = 119
ORDER BY b.introduced_date DESC;
```

**Voting Pattern Analysis**:
```sql
SELECT m.first, m.last, m.party, m.state,
       COUNT(CASE WHEN v.vote_code = 'Yea' THEN 1 END) as yea_votes,
       COUNT(CASE WHEN v.vote_code = 'Nay' THEN 1 END) as nay_votes
FROM members m
JOIN votes v ON m.member_id_bioguide = v.member_id_bioguide
JOIN rollcalls r ON v.rollcall_id = r.rollcall_id
WHERE r.congress = 119
GROUP BY m.member_id_bioguide;
```

**Subject-Based Bill Analysis**:
```sql
SELECT b.bill_id, b.title, b.policy_area,
       GROUP_CONCAT(bs.subject_term SEPARATOR ', ') as subjects
FROM bills b
JOIN bill_subjects bs ON b.bill_id = bs.bill_id
WHERE bs.subject_term LIKE '%Budget%'
GROUP BY b.bill_id;
```

### Performance Indexes

**Composite Indexes for Complex Queries**:
```sql
-- Bills by congress, chamber, and date
CREATE INDEX idx_bills_congress_chamber_date 
ON bills(congress, chamber, introduced_date);

-- Votes by rollcall and member
CREATE INDEX idx_votes_rollcall_member 
ON votes(rollcall_id, member_id_bioguide);

-- Cosponsors by bill and date
CREATE INDEX idx_cosponsors_bill_date 
ON cosponsors(bill_id, date);
```

## 🗃️ Data Maintenance

### Archival Strategy

**Active Data**: Current Congress (119th)
**Recent Data**: Previous 2 Congresses (117th, 118th)
**Historical Data**: Archived to separate tables

### Cleanup Procedures

**Orphaned Records**: Automated cleanup of broken references
**Duplicate Prevention**: Unique constraints and validation
**Data Integrity**: Regular foreign key constraint checks

## 📈 Monitoring and Metrics

### Key Performance Indicators

- **Query Response Time**: < 5 seconds for complex queries
- **Data Freshness**: < 24 hours for new bills
- **Storage Growth**: Monitor table sizes and growth rates
- **Index Usage**: Track index efficiency and usage patterns

### Maintenance Tasks

**Daily**:
- Check for new bills and metadata
- Validate data integrity
- Monitor query performance

**Weekly**:
- Analyze slow query logs
- Update table statistics
- Review index usage

**Monthly**:
- Archive old data
- Optimize table structures
- Review and update constraints

---

*This database schema provides the foundation for comprehensive congressional data analysis and voting pattern detection. The normalized structure ensures data integrity while the indexed design enables fast query performance.*
