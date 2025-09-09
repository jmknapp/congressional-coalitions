# FEC CSV Data Processing

This system processes FEC candidate data from manually provided CSV files instead of using API calls.

## Setup

1. **Place your CSV file** in the `data/fec/` directory:
   ```bash
   mkdir -p data/fec
   # Copy your FEC candidate CSV file to data/fec/ (any name ending in .csv)
   # The system will automatically use the latest CSV file
   ```

2. **CSV File Format**
   
   The system is flexible and can handle various CSV formats. It looks for these column names (case-insensitive):
   
   **Required columns:**
   - `candidate_id` or `CAND_ID` or `Candidate ID`
   - `candidate_name` or `CAND_NAME` or `Candidate Name` or `name`
   
   **Optional columns:**
   - `party` or `CAND_PTY_AFFILIATION` or `Party`
   - `candidate_state` or `CAND_ST` or `State`
   - `candidate_district` or `CAND_DISTRICT` or `District`
   - `total_receipts` or `Total Receipts` or `receipts`
   - `total_disbursements` or `Total Disbursements` or `disbursements`
   - `cash_on_hand` or `Cash on Hand` or `cash_on_hand_end_period`
   - `debts_owed_by_committee` or `Debts Owed by Committee` or `debts_owed`
   - `incumbent_challenge_status` or `INCUMBENT_CHALLENGER_STATUS` or `Incumbent/Challenger Status`
   - `candidate_status` or `CAND_STATUS` or `Candidate Status`
   - `principal_committee_id` or `PRINCIPAL_COMMITTEE_ID` or `Principal Committee ID`
   - `principal_committee_name` or `PRINCIPAL_COMMITTEE_NAME` or `Principal Committee Name`
   - `election_year` or `CAND_ELECTION_YR` or `Election Year`

## Usage

### Method 1: Using the processing script
```bash
# Process the latest CSV file in data/fec/ (recommended)
python process_fec_csv.py

# Or process a specific CSV file
python process_fec_csv.py data/fec/candidates.csv
python process_fec_csv.py /path/to/your/fec_data.csv
```

### Method 2: Using the web interface
1. Start the Flask app: `python app.py`
2. Go to `/fec-candidates` page
3. Enable developer mode (Shift+Ctrl+D, password: `dev2024`)
4. Click "Download Latest Data" button

### Method 3: Using the service directly
```python
from src.etl.fec_service import FECDataService

# Process the latest CSV file in data/fec/ (recommended)
service = FECDataService()
stats = service.download_and_store_candidates(force_update=True)
print(f"Processed {stats['total_processed']} candidates")

# Or specify a custom CSV file
service = FECDataService('/path/to/your/candidates.csv')
stats = service.download_and_store_candidates(force_update=True)
```

## Getting FEC Data

### Option 1: FEC Website Export
1. Go to https://www.fec.gov/data/candidates/house/?election_year=2026&election_full=True
2. Click "Export" button
3. Select "CSV" format
4. Download the file
5. Save in `data/fec/` directory (any name ending in .csv)

### Option 2: FEC Bulk Data
1. Go to https://www.fec.gov/data/browse-data/?tab=bulk-data
2. Download the candidate master file for the appropriate year
3. Extract the CSV from the ZIP file
4. Save in `data/fec/` directory (any name ending in .csv)

## File Structure

```
congressional-coalitions/
├── data/
│   └── fec/
│       ├── candidates_2026.csv     # Your FEC candidate data (any .csv file)
│       ├── fec_export.csv          # Multiple CSV files supported
│       └── latest_data.csv         # System uses the newest file
├── src/etl/
│   ├── fec_csv_processor.py        # CSV processing logic
│   └── fec_service.py              # Main service (updated for CSV)
├── process_fec_csv.py              # Standalone processing script
└── FEC_CSV_README.md               # This file
```

## Benefits of CSV Approach

1. **No API rate limits** - Process as many candidates as needed
2. **Includes financial data** - All data in one file
3. **Faster processing** - No network delays
4. **Reliable** - No dependency on FEC API availability
5. **Flexible** - Works with various CSV formats

## Troubleshooting

### CSV file not found
```
Error: No CSV files found in /path/to/data/fec
```
**Solution:** Make sure you have at least one CSV file in the `data/fec/` directory.

### Column not found warnings
```
WARNING: Column 'total_receipts' not found, using default value 0.0
```
**Solution:** Check your CSV column names. The system will use default values for missing columns.

### Database connection errors
```
Error: Database connection failed
```
**Solution:** Make sure your database is running and the connection settings are correct in `config.yaml`.

## Updating Data

To update the candidate data:
1. Download a new CSV file from FEC
2. Save it in `data/fec/` directory (any name ending in .csv)
3. Run the processing script: `python process_fec_csv.py`

The system will automatically use the latest CSV file and detect new candidates and update existing ones.
