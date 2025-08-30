

A data pipeline and analysis system for tracking congressional coalitions, bipartisan cooperation, and voting patterns in the US Congress.

## Project Overview

This system analyzes congressional data to:
- Detect evolving coalitions via vote agreement, cosponsorship, and amendments
- Characterize bill subjects/text associated with certain coalitions and outcomes
- Flag "unexpected" member votes (outliers)
- Track bipartisan cooperation and intra-party dynamics

## Data Sources

### Primary Sources (Authoritative)
- **Bills/Actions/Subjects**: GovInfo BILLSTATUS bulk (XML/JSON) - canonical source
- **Floor Roll-Call Votes**: 
  - House: Clerk XML/CSV feeds
  - Senate: LIS per-vote XML
- **Member IDs**: unitedstates/congress-legislators (BioGuide, ICPSR, LIS, FEC crosswalks)
- **Ideology Baseline**: Voteview DW-NOMINATE scores

### Convenience APIs
- **ProPublica Congress API**: Clean JSON for quick prototyping

## Database Schema

```sql
-- Core member data
members(
  member_id_bioguide PK, 
  icpsr, 
  lis_id, 
  first, 
  last, 
  party, 
  state, 
  district, 
  start_date, 
  end_date
)

-- Bill information
bills(
  bill_id PK, 
  congress, 
  chamber, 
  number, 
  type, 
  title, 
  introduced_date, 
  sponsor_bioguide, 
  policy_area, 
  summary_short
)

-- Bill subjects (CRS terms)
bill_subjects(bill_id, subject_term)

-- Cosponsorship data
cosponsors(bill_id, member_id_bioguide, date, is_original)

-- Bill actions
actions(bill_id, action_date, action_code, text, committee_code)

-- Amendment data
amendments(
  amendment_id PK, 
  bill_id, 
  sponsor_bioguide, 
  type, 
  purpose, 
  introduced_date
)

-- Roll call votes
rollcalls(
  rollcall_id PK, 
  congress, 
  chamber, 
  session, 
  rc_number, 
  date, 
  question, 
  bill_id NULLABLE
)

-- Individual votes
votes(
  rollcall_id, 
  member_id_bioguide, 
  vote_code ENUM('Yea','Nay','Present','Not Voting')
)
```

## Analytics Approach

### Coalition Detection
1. **Vote-Agreement Graph**: Member×member matrix with agreement rates over rolling windows
2. **Cosponsorship Graph**: Bipartite projection showing shared bill support
3. **Amendment Graph**: Amendment sponsorship patterns
4. **Multiplex Network**: Combine with weights α·vote + β·cosponsor + γ·amendment

### Topic Analysis
- Use CRS Policy Area + Legislative Subject Terms (human-curated)
- Augment with embeddings for sub-topic discovery
- HDBSCAN/UMAP clustering on bill text

### Outlier Detection
1. **Simple**: Party-line deviation (≥80% rule)
2. **Model-based**: Logistic regression with DW-NOMINATE + party features

## Project Structure

```
congressional-coalitions/
├── src/                    # Core Python modules
│   ├── etl/               # Data loaders
│   ├── analysis/          # Coalition detection & analysis
│   └── utils/             # Shared utilities
├── scripts/               # CLI tools and jobs
├── data/                  # Raw data and processed outputs
├── docs/                  # Documentation
└── tests/                 # Unit tests
```

## Quick Start

1. Install dependencies: `pip install -r requirements.txt`
2. Set up database: `scripts/setup_db.py`
3. Load initial data: `scripts/etl_bills.py --congress 119`
4. Run analysis: `scripts/analyze_coalitions.py --window 90d`

## Key Outputs

1. **Current Coalitions**: Per-chamber clusters with party mix and top subjects
2. **Bipartisan Hotspots**: Bills with high cross-party cosponsorship
3. **Outlier Tape**: Unexpected votes with explanations
4. **Coalition Stability**: Tracking changes over time

## Development Status

- [ ] Database schema setup
- [ ] GovInfo BILLSTATUS loader
- [ ] House/Senate vote loaders
- [ ] Coalition detection algorithms
- [ ] Outlier detection models
- [ ] Analysis dashboard
- [ ] Automated data pipeline

## Environment

- Python 3.11+
- MySQL/PostgreSQL
- Key packages: pandas, networkx, scikit-learn, requests


