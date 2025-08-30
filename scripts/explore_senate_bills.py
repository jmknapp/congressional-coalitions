#!/usr/bin/env python3
import requests
import sys
import xml.etree.ElementTree as ET

def explore_senate_bill_sources():
    """Explore different Senate.gov data sources for bills."""
    
    # List of potential Senate.gov bill endpoints to try
    endpoints = [
        # Senate.gov legislation pages
        "https://www.senate.gov/legislative/LIS/legislation.htm",
        "https://www.senate.gov/legislative/LIS/legislation/",
        "https://www.senate.gov/legislative/LIS/legislation/bills.htm",
        
        # Senate.gov LIS (Legislative Information System) endpoints
        "https://www.senate.gov/legislative/LIS/",
        "https://www.senate.gov/legislative/LIS/bills/",
        "https://www.senate.gov/legislative/LIS/bills/bills.htm",
        
        # Try to find bill lists or indexes
        "https://www.senate.gov/legislative/LIS/legislation/bill_list.htm",
        "https://www.senate.gov/legislative/LIS/legislation/bill_index.htm",
        
        # Try Congress.gov style endpoints (Senate.gov might have similar)
        "https://www.senate.gov/legislative/LIS/legislation/bills_119.htm",
        "https://www.senate.gov/legislative/LIS/legislation/bills_119_1.htm",
        "https://www.senate.gov/legislative/LIS/legislation/bills_119_2.htm",
        
        # Try XML endpoints for bills
        "https://www.senate.gov/legislative/LIS/legislation/bills_119.xml",
        "https://www.senate.gov/legislative/LIS/legislation/bills_119_1.xml",
        "https://www.senate.gov/legislative/LIS/legislation/bills_119_2.xml",
        
        # Try different bill type endpoints
        "https://www.senate.gov/legislative/LIS/legislation/bills_s.htm",
        "https://www.senate.gov/legislative/LIS/legislation/bills_sjres.htm",
        "https://www.senate.gov/legislative/LIS/legislation/bills_sconres.htm",
        "https://www.senate.gov/legislative/LIS/legislation/bills_sres.htm",
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
                
                # Look for bill-related content
                if 'bill' in content.lower():
                    print("*** CONTAINS BILL DATA ***")
                elif 'legislation' in content.lower():
                    print("*** CONTAINS LEGISLATION DATA ***")
                elif 's.' in content.lower() or 's ' in content.lower():
                    print("*** CONTAINS SENATE BILL REFERENCES ***")
                elif '<html' in content.lower():
                    print("*** HTML PAGE ***")
                else:
                    print("*** UNKNOWN CONTENT ***")
                    
                # Look for links to bill data
                if 'href=' in content:
                    import re
                    links = re.findall(r'href="([^"]*)"', content)
                    bill_links = [link for link in links if 'bill' in link.lower()]
                    if bill_links:
                        print(f"*** FOUND BILL LINKS: {bill_links[:5]} ***")
            else:
                print(f"Failed with status {response.status_code}")
                
        except Exception as e:
            print(f"Error: {e}")

def test_senate_bill_xml():
    """Test if Senate.gov has XML bill data like they do for votes."""
    
    # Try to find bill XML endpoints similar to vote XML
    bill_endpoints = [
        "https://www.senate.gov/legislative/LIS/legislation/bills_119_1.xml",
        "https://www.senate.gov/legislative/LIS/legislation/bills_119_2.xml",
        "https://www.senate.gov/legislative/LIS/legislation/bills_119.xml",
        "https://www.senate.gov/legislative/LIS/legislation/bills_s_119.xml",
        "https://www.senate.gov/legislative/LIS/legislation/bills_sjres_119.xml",
    ]
    
    for url in bill_endpoints:
        print(f"\nTesting bill XML: {url}")
        try:
            response = requests.get(url, timeout=30)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                content = response.text[:500]
                print(f"First 500 chars: {content}")
                
                # Try to parse as XML
                try:
                    root = ET.fromstring(response.text)
                    print("*** VALID XML ***")
                    
                    # Look for bill elements
                    bills = root.findall('.//bill')
                    if bills:
                        print(f"*** FOUND {len(bills)} BILL ELEMENTS ***")
                        for i, bill in enumerate(bills[:3]):  # Show first 3
                            print(f"  Bill {i+1}: {ET.tostring(bill, encoding='unicode')[:200]}")
                    
                    # Look for other bill-related elements
                    for tag in ['legislation', 'senate_bill', 's_bill', 'document']:
                        elements = root.findall(f'.//{tag}')
                        if elements:
                            print(f"*** FOUND {len(elements)} {tag.upper()} ELEMENTS ***")
                            
                except ET.ParseError as e:
                    print(f"*** XML PARSE ERROR: {e} ***")
                    
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    print("Exploring Senate.gov bill sources...")
    explore_senate_bill_sources()
    
    print("\n" + "="*50)
    print("Testing Senate.gov bill XML endpoints...")
    test_senate_bill_xml()
