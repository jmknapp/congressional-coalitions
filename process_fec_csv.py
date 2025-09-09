#!/usr/bin/env python3
"""
Script to process FEC candidate CSV files.
Usage: python process_fec_csv.py <csv_file_path>
"""

import os
import sys
import logging
from src.etl.fec_csv_processor import FECCSVProcessor

def main():
    if len(sys.argv) > 2:
        print("Usage: python process_fec_csv.py [csv_file_path]")
        print("Example: python process_fec_csv.py data/fec/candidates.csv")
        print("If no file specified, will use the latest CSV file in data/fec/")
        sys.exit(1)
    
    if len(sys.argv) == 2:
        csv_file_path = sys.argv[1]
        if not os.path.exists(csv_file_path):
            print(f"Error: CSV file not found: {csv_file_path}")
            sys.exit(1)
    else:
        # Use the latest CSV file in data/fec directory
        try:
            from src.etl.fec_service import FECDataService
            service = FECDataService()
            csv_file_path = service.csv_file_path
            print(f"Using latest CSV file: {csv_file_path}")
        except FileNotFoundError as e:
            print(f"Error: {e}")
            print("Please place a CSV file in the data/fec/ directory or specify a file path.")
            sys.exit(1)
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    try:
        print(f"Processing FEC CSV file: {csv_file_path}")
        processor = FECCSVProcessor(csv_file_path)
        stats = processor.process_csv_file(force_update=True)
        
        print(f"\n✓ CSV processing completed successfully!")
        print(f"  Total processed: {stats['total_processed']}")
        print(f"  New candidates: {stats['new_candidates']}")
        print(f"  Updated candidates: {stats['updated_candidates']}")
        print(f"  Errors: {stats['errors']}")
        print(f"  Duration: {(stats['end_time'] - stats['start_time']).total_seconds():.2f} seconds")
        
    except Exception as e:
        print(f"✗ Error processing CSV file: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
