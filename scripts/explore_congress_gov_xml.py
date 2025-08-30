#!/usr/bin/env python3
import requests
import sys
import xml.etree.ElementTree as ET

def explore_congress_gov_xml():
    """Explore Congress.gov XML endpoints for bills."""
    
    # Test the specific bill you mentioned
    bill_id = "2256"
    congress = "119"
    
    # List of potential Congress.gov XML endpoints to try
    endpoints = [
        # Direct XML endpoints for the specific bill
        f"https://www.congress.gov/bill/{congress}th-congress/senate-bill/{bill_id}?format=xml",
        f"https://www.congress.gov/bill/{congress}th-congress/senate-bill/{bill_id}.xml",
        f"https://www.congress.gov/bill/{congress}th-congress/senate-bill/{bill_id}/text?format=xml",
        f"https://www.congress.gov/bill/{congress}th-congress/senate-bill/{bill_id}/summary?format=xml",
        
        # Congress.gov API endpoints (if they exist)
        f"https://www.congress.gov/api/bill/{congress}/s/{bill_id}",
        f"https://www.congress.gov/api/bill/{congress}/s/{bill_id}.xml",
        
        # RSS feeds (might contain bill info)
        f"https://www.congress.gov/bill/{congress}th-congress/senate-bill/{bill_id}?rss=1",
        f"https://www.congress.gov/bill/{congress}th-congress/senate-bill/{bill_id}.rss",
        
        # Try different formats
        f"https://www.congress.gov/bill/{congress}th-congress/senate-bill/{bill_id}?format=json",
        f"https://www.congress.gov/bill/{congress}th-congress/senate-bill/{bill_id}.json",
        
        # Bulk data endpoints
        "https://www.congress.gov/bulkdata/BILLSTATUS/119/s/BILLSTATUS-119s2256.xml",
        "https://www.congress.gov/bulkdata/BILLSTATUS/119/s/BILLSTATUS-119-s-2256.xml",
        
        # Alternative URL patterns
        f"https://www.congress.gov/bill/{congress}th-congress/senate-bill/{bill_id}/data.xml",
        f"https://www.congress.gov/bill/{congress}th-congress/senate-bill/{bill_id}/xml",
    ]
    
    for url in endpoints:
        print(f"\nTesting: {url}")
        try:
            response = requests.get(url, timeout=30)
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
            
            if response.status_code == 200:
                content = response.text[:1000]
                print(f"First 1000 chars: {content}")
                
                # Check if it's XML
                if '<?xml' in content or '<bill' in content.lower():
                    print("*** CONTAINS XML DATA ***")
                    try:
                        root = ET.fromstring(response.text)
                        print("*** VALID XML ***")
                        
                        # Look for bill elements
                        bills = root.findall('.//bill')
                        if bills:
                            print(f"*** FOUND {len(bills)} BILL ELEMENTS ***")
                        
                        # Look for other bill-related elements
                        for tag in ['legislation', 'senate_bill', 's_bill', 'document', 'title', 'sponsor']:
                            elements = root.findall(f'.//{tag}')
                            if elements:
                                print(f"*** FOUND {len(elements)} {tag.upper()} ELEMENTS ***")
                                
                    except ET.ParseError as e:
                        print(f"*** XML PARSE ERROR: {e} ***")
                        
                elif 'json' in response.headers.get('content-type', '').lower():
                    print("*** CONTAINS JSON DATA ***")
                elif 'html' in response.headers.get('content-type', '').lower():
                    print("*** HTML PAGE ***")
                else:
                    print("*** UNKNOWN CONTENT ***")
            else:
                print(f"Failed with status {response.status_code}")
                
        except Exception as e:
            print(f"Error: {e}")

def explore_congress_gov_bulk_data():
    """Explore Congress.gov bulk data endpoints."""
    
    # Test bulk data endpoints for Senate bills
    bulk_endpoints = [
        # GovInfo-style bulk data (Congress.gov might redirect to GovInfo)
        "https://www.congress.gov/bulkdata/BILLSTATUS/119/s/",
        "https://www.congress.gov/bulkdata/BILLSTATUS/119/s/BILLSTATUS-119s2256.xml",
        
        # Try different patterns
        "https://www.congress.gov/bulkdata/BILLSTATUS/119/s/BILLSTATUS-119-s-2256.xml",
        "https://www.congress.gov/bulkdata/BILLSTATUS/119/s/BILLSTATUS-119s2256.json",
        
        # Congress.gov might have its own bulk data structure
        "https://www.congress.gov/bulkdata/bills/119/s/",
        "https://www.congress.gov/bulkdata/bills/119/s/s2256.xml",
        
        # Try RSS feeds for Senate bills
        "https://www.congress.gov/rss/bills/senate.xml",
        "https://www.congress.gov/rss/bills/119/senate.xml",
    ]
    
    for url in bulk_endpoints:
        print(f"\nTesting bulk data: {url}")
        try:
            response = requests.get(url, timeout=30)
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
            
            if response.status_code == 200:
                content = response.text[:500]
                print(f"First 500 chars: {content}")
                
                if '<?xml' in content:
                    print("*** CONTAINS XML DATA ***")
                elif 'json' in response.headers.get('content-type', '').lower():
                    print("*** CONTAINS JSON DATA ***")
                elif 'html' in response.headers.get('content-type', '').lower():
                    print("*** HTML PAGE ***")
                else:
                    print("*** UNKNOWN CONTENT ***")
            else:
                print(f"Failed with status {response.status_code}")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    print("Exploring Congress.gov XML endpoints for Senate Bill 2256...")
    explore_congress_gov_xml()
    
    print("\n" + "="*50)
    print("Exploring Congress.gov bulk data endpoints...")
    explore_congress_gov_bulk_data()
