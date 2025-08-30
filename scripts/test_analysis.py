#!/usr/bin/env python3
"""
Test script to debug analysis errors.
"""

import os
import sys
import traceback

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def test_analysis_imports():
    """Test if all analysis imports work."""
    try:
        print("Testing imports...")
        
        from src.analysis.coalition_detector import CoalitionDetector
        print("✓ CoalitionDetector imported successfully")
        
        from src.analysis.outlier_detector import OutlierDetector
        print("✓ OutlierDetector imported successfully")
        
        from scripts.analyze_coalitions import run_complete_analysis
        print("✓ run_complete_analysis imported successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ Import error: {e}")
        traceback.print_exc()
        return False

def test_analysis_function():
    """Test the analysis function with House data."""
    try:
        print("\nTesting analysis function...")
        
        from scripts.analyze_coalitions import run_complete_analysis
        
        # Test with House data only
        results = run_complete_analysis(congress=119, chamber='house', window_days=90)
        
        print("✓ Analysis completed successfully")
        print(f"Results keys: {list(results.keys())}")
        
        if 'summary' in results:
            print(f"Summary: {results['summary']}")
        
        return True
        
    except Exception as e:
        print(f"✗ Analysis error: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("Testing Congressional Coalition Analysis...")
    
    # Test imports
    if not test_analysis_imports():
        return
    
    # Test analysis function
    if not test_analysis_function():
        return
    
    print("\n✓ All tests passed!")

if __name__ == "__main__":
    main()
