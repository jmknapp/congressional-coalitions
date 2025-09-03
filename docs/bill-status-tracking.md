# Bill Status Tracking and Enactment Detection

## 🎯 How to Determine if a Bill Has Been Passed and Enacted

This guide explains how to track bill status through the legislative process and determine when bills become law.

## 📊 Bill Status Tracking

### Legislative Process Overview

```
INTRODUCED → COMMITTEE → FLOOR VOTE → PASSED HOUSE → PASSED SENATE → PRESIDENT → ENACTED
    ↓           ↓           ↓           ↓           ↓           ↓         ↓
  Action    Action     Action     Action     Action     Action   Action
  Code      Code       Code       Code       Code       Code     Code
```

### Key Action Codes

#### House Actions
- **`INTRODUCED`** - Bill introduced in House
- **`REFERRED`** - Bill referred to committee
- **`REPORTED`** - Committee reported bill favorably
- **`PASSED_HOUSE`** - Bill passed House floor vote
- **`FAILED_HOUSE`** - Bill failed House floor vote

#### Senate Actions  
- **`RECEIVED_SENATE`** - Bill received from House
- **`PASSED_SENATE`** - Bill passed Senate floor vote
- **`FAILED_SENATE`** - Bill failed Senate floor vote

#### Final Actions
- **`ENACTED`** - Bill signed into law by President
- **`VETOED`** - Bill vetoed by President
- **`BECAME_LAW`** - Bill became law without signature (after 10 days)
- **`POCKET_VETO`** - Bill pocket vetoed (Congress adjourned)

## 🔍 SQL Queries for Bill Status

### 1. **Bills That Have Passed Both Chambers**

```sql
-- Bills that passed both House and Senate
SELECT DISTINCT b.bill_id, b.title, b.sponsor_bioguide,
       MAX(CASE WHEN a.action_code = 'PASSED_HOUSE' THEN a.action_date END) as house_pass_date,
       MAX(CASE WHEN a.action_code = 'PASSED_SENATE' THEN a.action_date END) as senate_pass_date
FROM bills b
JOIN actions a ON b.bill_id = a.bill_id
WHERE b.congress = 119
  AND a.action_code IN ('PASSED_HOUSE', 'PASSED_SENATE')
GROUP BY b.bill_id
HAVING house_pass_date IS NOT NULL 
   AND senate_pass_date IS NOT NULL
ORDER BY house_pass_date DESC;
```

### 2. **Bills Enacted Into Law**

```sql
-- Bills that became law
SELECT b.bill_id, b.title, b.sponsor_bioguide,
       MAX(CASE WHEN a.action_code = 'ENACTED' THEN a.action_date END) as enacted_date,
       MAX(CASE WHEN a.action_code = 'BECAME_LAW' THEN a.action_date END) as became_law_date
FROM bills b
JOIN actions a ON b.bill_id = a.bill_id
WHERE b.congress = 119
  AND a.action_code IN ('ENACTED', 'BECAME_LAW')
GROUP BY b.bill_id
HAVING enacted_date IS NOT NULL OR became_law_date IS NOT NULL
ORDER BY COALESCE(enacted_date, became_law_date) DESC;
```

### 3. **Complete Bill Status Summary**

```sql
-- Comprehensive bill status for all bills
SELECT b.bill_id, b.title, b.policy_area,
       MAX(CASE WHEN a.action_code = 'INTRODUCED' THEN a.action_date END) as introduced_date,
       MAX(CASE WHEN a.action_code = 'PASSED_HOUSE' THEN a.action_date END) as house_pass_date,
       MAX(CASE WHEN a.action_code = 'PASSED_SENATE' THEN a.action_date END) as senate_pass_date,
       MAX(CASE WHEN a.action_code = 'ENACTED' THEN a.action_date END) as enacted_date,
       MAX(CASE WHEN a.action_code = 'VETOED' THEN a.action_date END) as vetoed_date,
       CASE 
           WHEN MAX(CASE WHEN a.action_code = 'ENACTED' THEN 1 END) = 1 THEN 'ENACTED'
           WHEN MAX(CASE WHEN a.action_code = 'VETOED' THEN 1 END) = 1 THEN 'VETOED'
           WHEN MAX(CASE WHEN a.action_code = 'PASSED_SENATE' THEN 1 END) = 1 THEN 'PASSED_BOTH_CHAMBERS'
           WHEN MAX(CASE WHEN a.action_code = 'PASSED_HOUSE' THEN 1 END) = 1 THEN 'PASSED_HOUSE_ONLY'
           ELSE 'IN_PROGRESS'
       END as current_status
FROM bills b
LEFT JOIN actions a ON b.bill_id = a.bill_id
WHERE b.congress = 119
GROUP BY b.bill_id
ORDER BY introduced_date DESC;
```

### 4. **Bills by Status Category**

```sql
-- Count bills by current status
SELECT 
    CASE 
        WHEN MAX(CASE WHEN a.action_code = 'ENACTED' THEN 1 END) = 1 THEN 'ENACTED'
        WHEN MAX(CASE WHEN a.action_code = 'VETOED' THEN 1 END) = 1 THEN 'VETOED'
        WHEN MAX(CASE WHEN a.action_code = 'PASSED_SENATE' THEN 1 END) = 1 THEN 'PASSED_BOTH_CHAMBERS'
        WHEN MAX(CASE WHEN a.action_code = 'PASSED_HOUSE' THEN 1 END) = 1 THEN 'PASSED_HOUSE_ONLY'
        ELSE 'IN_PROGRESS'
    END as bill_status,
    COUNT(*) as bill_count
FROM bills b
LEFT JOIN actions a ON b.bill_id = a.bill_id
WHERE b.congress = 119
GROUP BY bill_status
ORDER BY bill_count DESC;
```

## 🚀 Implementation in Python

### Bill Status Class

```python
from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict

class BillStatus(Enum):
    INTRODUCED = "INTRODUCED"
    IN_COMMITTEE = "IN_COMMITTEE"
    PASSED_HOUSE = "PASSED_HOUSE"
    PASSED_SENATE = "PASSED_SENATE"
    PASSED_BOTH = "PASSED_BOTH"
    ENACTED = "ENACTED"
    VETOED = "VETOED"
    FAILED = "FAILED"

class BillStatusTracker:
    def __init__(self, db_session):
        self.session = db_session
    
    def get_bill_status(self, bill_id: str) -> Dict:
        """Get comprehensive status for a specific bill."""
        
        # Get all actions for the bill
        actions_query = """
            SELECT action_code, action_date, text
            FROM actions 
            WHERE bill_id = :bill_id
            ORDER BY action_date ASC
        """
        
        actions = self.session.execute(text(actions_query), {'bill_id': bill_id}).fetchall()
        
        if not actions:
            return {'status': 'UNKNOWN', 'actions': []}
        
        # Determine current status
        status = self._determine_status(actions)
        
        return {
            'bill_id': bill_id,
            'status': status.value,
            'actions': [dict(action) for action in actions],
            'introduced_date': self._get_action_date(actions, 'INTRODUCED'),
            'house_pass_date': self._get_action_date(actions, 'PASSED_HOUSE'),
            'senate_pass_date': self._get_action_date(actions, 'PASSED_SENATE'),
            'enacted_date': self._get_action_date(actions, 'ENACTED'),
            'vetoed_date': self._get_action_date(actions, 'VETOED'),
            'is_law': status in [BillStatus.ENACTED],
            'passed_both_chambers': status in [BillStatus.PASSED_BOTH, BillStatus.ENACTED]
        }
    
    def _determine_status(self, actions: List) -> BillStatus:
        """Determine current bill status based on actions."""
        
        action_codes = [action.action_code for action in actions]
        
        if 'ENACTED' in action_codes:
            return BillStatus.ENACTED
        elif 'VETOED' in action_codes:
            return BillStatus.VETOED
        elif 'PASSED_HOUSE' in action_codes and 'PASSED_SENATE' in action_codes:
            return BillStatus.PASSED_BOTH
        elif 'PASSED_HOUSE' in action_codes:
            return BillStatus.PASSED_HOUSE
        elif 'PASSED_SENATE' in action_codes:
            return BillStatus.PASSED_SENATE
        elif 'INTRODUCED' in action_codes:
            return BillStatus.INTRODUCED
        else:
            return BillStatus.UNKNOWN
    
    def _get_action_date(self, actions: List, action_code: str) -> Optional[datetime]:
        """Get date for specific action code."""
        for action in actions:
            if action.action_code == action_code:
                return action.action_date
        return None
    
    def get_enacted_bills(self, congress: int) -> List[Dict]:
        """Get all bills enacted into law for a Congress."""
        
        query = """
            SELECT DISTINCT b.bill_id, b.title, b.sponsor_bioguide,
                   MAX(CASE WHEN a.action_code = 'ENACTED' THEN a.action_date END) as enacted_date
            FROM bills b
            JOIN actions a ON b.bill_id = a.bill_id
            WHERE b.congress = :congress
              AND a.action_code = 'ENACTED'
            GROUP BY b.bill_id
            ORDER BY enacted_date DESC
        """
        
        results = self.session.execute(text(query), {'congress': congress}).fetchall()
        return [dict(result) for result in results]
    
    def get_bills_passed_both_chambers(self, congress: int) -> List[Dict]:
        """Get bills that passed both House and Senate."""
        
        query = """
            SELECT DISTINCT b.bill_id, b.title, b.sponsor_bioguide,
                   MAX(CASE WHEN a.action_code = 'PASSED_HOUSE' THEN a.action_date END) as house_pass_date,
                   MAX(CASE WHEN a.action_code = 'PASSED_SENATE' THEN a.action_date END) as senate_pass_date
            FROM bills b
            JOIN actions a ON b.bill_id = a.bill_id
            WHERE b.congress = :congress
              AND a.action_code IN ('PASSED_HOUSE', 'PASSED_SENATE')
            GROUP BY b.bill_id
            HAVING house_pass_date IS NOT NULL 
               AND senate_pass_date IS NOT NULL
            ORDER BY house_pass_date DESC
        """
        
        results = self.session.execute(text(query), {'congress': congress}).fetchall()
        return [dict(result) for result in results]
```

### API Endpoint Implementation

```python
@app.route('/api/bill/<bill_id>/status')
def get_bill_status(bill_id):
    """Get comprehensive status for a specific bill."""
    try:
        tracker = BillStatusTracker(get_db_session())
        status = tracker.get_bill_status(bill_id)
        
        if status['status'] == 'UNKNOWN':
            return jsonify({'error': 'Bill not found'}), 404
            
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bills/enacted/<int:congress>')
def get_enacted_bills(congress):
    """Get all bills enacted into law for a Congress."""
    try:
        tracker = BillStatusTracker(get_db_session())
        bills = tracker.get_enacted_bills(congress)
        return jsonify(bills)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bills/passed-both/<int:congress>')
def get_bills_passed_both(congress):
    """Get bills that passed both chambers for a Congress."""
    try:
        tracker = BillStatusTracker(get_db_session())
        bills = tracker.get_bills_passed_both_chambers(congress)
        return jsonify(bills)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

## 📊 Dashboard Integration

### JavaScript Status Display

```javascript
async function displayBillStatus(billId) {
    try {
        const response = await fetch(`/api/bill/${billId}/status`);
        const status = await response.json();
        
        const statusElement = document.getElementById('bill-status');
        statusElement.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h5>Bill Status: ${status.status}</h5>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <p><strong>Introduced:</strong> ${status.introduced_date || 'N/A'}</p>
                            <p><strong>House Passed:</strong> ${status.house_pass_date || 'N/A'}</p>
                            <p><strong>Senate Passed:</strong> ${status.senate_pass_date || 'N/A'}</p>
                        </div>
                        <div class="col-md-6">
                            <p><strong>Enacted:</strong> ${status.enacted_date || 'N/A'}</p>
                            <p><strong>Vetoed:</strong> ${status.vetoed_date || 'N/A'}</p>
                            <p><strong>Is Law:</strong> ${status.is_law ? 'Yes' : 'No'}</p>
                        </div>
                    </div>
                    <div class="alert ${status.is_law ? 'alert-success' : 'alert-info'}">
                        <strong>Current Status:</strong> ${status.status}
                    </div>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Error fetching bill status:', error);
    }
}
```

## 🔄 Data Population

### Action Code Mapping

To properly track bill status, ensure these action codes are populated:

```python
# Common action codes from Congress.gov
ACTION_CODE_MAPPING = {
    'INTRODUCED': 'INTRODUCED',
    'REFERRED': 'REFERRED',
    'REPORTED': 'REPORTED',
    'PASSED': 'PASSED_HOUSE',  # Context determines chamber
    'ENACTED': 'ENACTED',
    'VETOED': 'VETOED',
    'BECAME_LAW': 'BECAME_LAW'
}
```

### Enhanced Daily Update

Modify the `enhanced_daily_update.py` script to also fetch and update action data:

```python
def fetch_bill_actions(self, congressgov_id: str) -> List[Dict]:
    """Fetch bill actions from Congress.gov API."""
    actions = []
    actions_url = f"https://api.congress.gov/v3/bill/{congressgov_id}/actions"
    headers = {'X-API-Key': self.congressgov_api_key}
    
    try:
        response = self.session.get(actions_url, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if 'actions' in data:
                for action in data['actions']:
                    actions.append({
                        'action_date': action.get('actionDate'),
                        'action_code': self._map_action_code(action.get('text', '')),
                        'text': action.get('text', ''),
                        'committee_code': action.get('committee', {}).get('systemCode', '')
                    })
    except Exception as e:
        logger.debug(f"Error fetching actions for {congressgov_id}: {e}")
    
    return actions

def _map_action_code(self, action_text: str) -> str:
    """Map action text to standardized action codes."""
    text = action_text.upper()
    
    if 'PASSED' in text and 'HOUSE' in text:
        return 'PASSED_HOUSE'
    elif 'PASSED' in text and 'SENATE' in text:
        return 'PASSED_SENATE'
    elif 'ENACTED' in text:
        return 'ENACTED'
    elif 'VETOED' in text:
        return 'VETOED'
    elif 'INTRODUCED' in text:
        return 'INTRODUCED'
    elif 'REFERRED' in text:
        return 'REFERRED'
    else:
        return 'OTHER'
```

## 📈 Status Analytics

### Success Rate Analysis

```sql
-- Bill success rate by policy area
SELECT b.policy_area,
       COUNT(*) as total_bills,
       COUNT(CASE WHEN a.action_code = 'ENACTED' THEN 1 END) as enacted_bills,
       ROUND(COUNT(CASE WHEN a.action_code = 'ENACTED' THEN 1 END) * 100.0 / COUNT(*), 2) as success_rate
FROM bills b
LEFT JOIN actions a ON b.bill_id = a.bill_id AND a.action_code = 'ENACTED'
WHERE b.congress = 119
  AND b.policy_area IS NOT NULL
GROUP BY b.policy_area
HAVING total_bills > 5
ORDER BY success_rate DESC;
```

### Timeline Analysis

```sql
-- Average time from introduction to enactment
SELECT b.policy_area,
       AVG(DATEDIFF(
           MAX(CASE WHEN a.action_code = 'ENACTED' THEN a.action_date END),
           MAX(CASE WHEN a.action_code = 'INTRODUCED' THEN a.action_date END)
       )) as avg_days_to_enactment
FROM bills b
JOIN actions a ON b.bill_id = a.bill_id
WHERE b.congress = 119
  AND a.action_code IN ('INTRODUCED', 'ENACTED')
GROUP BY b.bill_id, b.policy_area
HAVING avg_days_to_enactment IS NOT NULL
ORDER BY avg_days_to_enactment;
```

---

*This comprehensive bill status tracking system provides complete visibility into the legislative process and enables accurate determination of which bills have been passed and enacted into law.*
