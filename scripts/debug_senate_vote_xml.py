#!/usr/bin/env python3
"""
Debug script to examine Senate vote XML structure.
"""

import requests
import xml.etree.ElementTree as ET

def debug_senate_vote_xml():
    """Debug the XML structure of a Senate vote."""
    
    # Test with a specific vote
    url = "https://www.senate.gov/legislative/LIS/roll_call_votes/vote1191/vote_119_1_00499.xml"
    
    print(f"Fetching: {url}")
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        content = response.text
        print(f"Content length: {len(content)}")
        print(f"First 1000 characters:")
        print(content[:1000])
        print("\n" + "="*50)
        
        # Try to parse XML
        try:
            root = ET.fromstring(content)
            print("XML parsed successfully!")
            
            # Print all top-level elements
            print("\nTop-level elements:")
            for elem in root:
                print(f"  {elem.tag}: {elem.text[:100] if elem.text else 'None'}")
            
            # Look for member elements
            print("\nLooking for member elements:")
            members = root.findall('.//member')
            print(f"Found {len(members)} member elements")
            
            if members:
                print("First member element:")
                first_member = members[0]
                for child in first_member:
                    print(f"  {child.tag}: {child.text}")
            
            # Look for bill/legislation elements
            print("\nLooking for bill/legislation elements:")
            bills = root.findall('.//bill')
            print(f"Found {len(bills)} bill elements")
            
            documents = root.findall('.//document')
            print(f"Found {len(documents)} document elements")
            
            if documents:
                print("First document element:")
                first_doc = documents[0]
                for child in first_doc:
                    print(f"  {child.tag}: {child.text}")
            
            # Look for vote information
            print("\nLooking for vote information:")
            vote_numbers = root.findall('.//vote_number')
            print(f"Found {len(vote_numbers)} vote_number elements")
            if vote_numbers:
                print(f"Vote number: {vote_numbers[0].text}")
            
            # Print all unique element tags
            print("\nAll unique element tags:")
            all_tags = set()
            for elem in root.iter():
                all_tags.add(elem.tag)
            
            for tag in sorted(all_tags):
                print(f"  {tag}")
                
        except ET.ParseError as e:
            print(f"XML parse error: {e}")
            print("Trying to extract information from text...")
            
            # Try regex extraction
            import re
            
            # Look for member IDs
            bioguide_matches = re.findall(r'<bioguide_id>([^<]+)</bioguide_id>', content)
            print(f"Found {len(bioguide_matches)} bioguide_id matches: {bioguide_matches[:5]}")
            
            # Look for vote numbers
            vote_matches = re.findall(r'<vote_number>(\d+)</vote_number>', content)
            print(f"Found {len(vote_matches)} vote_number matches: {vote_matches}")
            
            # Look for document types
            doc_type_matches = re.findall(r'<document_type>([^<]+)</document_type>', content)
            print(f"Found {len(doc_type_matches)} document_type matches: {doc_type_matches}")
            
            # Look for document numbers
            doc_num_matches = re.findall(r'<document_number>([^<]+)</document_number>', content)
            print(f"Found {len(doc_num_matches)} document_number matches: {doc_num_matches}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_senate_vote_xml()

