#!/usr/bin/env python3
"""
Scrape Freedom Caucus membership from their official website.
"""

import requests
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import get_db_session
from scripts.setup_db import Member

def scrape_freedom_caucus_website():
    """Scrape Freedom Caucus membership from alternative sources."""
    
    # Try multiple sources since the official website is dead
    urls = [
        "https://ballotpedia.org/Freedom_Caucus",
        "https://en.wikipedia.org/wiki/Freedom_Caucus",
        "https://www.congress.gov/search?q=%7B%22congress%22%3A%5B%22119%22%5D%2C%22chamber%22%3A%5B%22House%22%5D%7D"
    ]
    
    for url in urls:
        try:
            print(f"🔍 Scraping Freedom Caucus source: {url}")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for member information
        members = []
        
        # Try different selectors that might contain member info
        # The Freedom Caucus site might use various HTML structures
        
        # Method 1: Look for member cards or lists
        member_elements = soup.find_all(['div', 'li', 'p'], class_=re.compile(r'member|rep|representative', re.I))
        
        if not member_elements:
            # Method 2: Look for any text that might contain member names
            member_elements = soup.find_all(text=re.compile(r'Rep\.|Representative|Congressman|Congresswoman'))
        
        if not member_elements:
            # Method 3: Look for common patterns in the HTML
            member_elements = soup.find_all(text=re.compile(r'[A-Z][a-z]+ [A-Z][a-z]+'))
        
        print(f"Found {len(member_elements)} potential member elements")
        
        # Extract member names from the elements
        for element in member_elements:
            if hasattr(element, 'get_text'):
                text = element.get_text().strip()
            else:
                text = str(element).strip()
            
            # Look for patterns like "Rep. John Smith" or "John Smith"
            name_match = re.search(r'(?:Rep\.|Representative|Congressman|Congresswoman)?\s*([A-Z][a-z]+ [A-Z][a-z]+)', text)
            if name_match:
                full_name = name_match.group(1).strip()
                if len(full_name.split()) == 2:  # First and last name only
                    members.append(full_name)
        
        # Remove duplicates and clean up
        members = list(set(members))
        members.sort()
        
        if members:
            print(f"✅ Extracted {len(members)} unique member names from {url}")
            return members
            
    except requests.RequestException as e:
        print(f"❌ Error scraping {url}: {e}")
        continue
    except Exception as e:
        print(f"❌ Unexpected error with {url}: {e}")
        continue
    
    print("❌ All Freedom Caucus sources failed")
    return []

def get_known_freedom_caucus_members():
    """Get a manually curated list of known Freedom Caucus members as backup."""
    
    # This is a manually maintained list based on public information
    # You can update this list as you find new information
    known_members = [
        "Andy Biggs",
        "Lauren Boebert", 
        "Ken Buck",
        "Tim Burchett",
        "Michael Cloud",
        "Andrew Clyde",
        "Scott DesJarlais",
        "Byron Donalds",
        "Russ Fulcher",
        "Paul Gosar",
        "Marjorie Greene",
        "H. Morgan Griffith",
        "Andy Harris",
        "Clay Higgins",
        "Diana Harshbarger",
        "Wesley Hunt",
        "Ronny Jackson",
        "Jim Jordan",
        "Thomas Massie",
        "Mary Miller",
        "Barry Moore",
        "Ralph Norman",
        "Scott Perry",
        "Chip Roy",
        "Matt Rosendale",
        "Keith Self",
        "Victoria Spartz",
        "William Gregory Steube",
        "Beth Van Duyne",
        "Randy Weber"
    ]
    
    return known_members

def match_members_to_database(member_names):
    """Match scraped names to database members."""
    
    with get_db_session() as session:
        matched_members = []
        unmatched_names = []
        
        for name in member_names:
            # Split into first and last name
            name_parts = name.split()
            if len(name_parts) >= 2:
                first_name = name_parts[0]
                last_name = name_parts[-1]
                
                # Try to find in database with exact match first
                member = session.query(Member).filter(
                    Member.first == first_name,
                    Member.last == last_name
                ).first()
                
                # If not found, try more flexible matching for special cases
                if not member:
                    if name == "H. Morgan Griffith":
                        member = session.query(Member).filter(
                            Member.first == "H.",
                            Member.last == "Griffith"
                        ).first()
                    elif name == "William Gregory Steube":
                        member = session.query(Member).filter(
                            Member.first == "W.",
                            Member.last == "Steube"
                        ).first()
                    elif name == "Beth Van Duyne":
                        member = session.query(Member).filter(
                            Member.first == "Beth",
                            Member.last == "Van Duyne"
                        ).first()
                
                if member:
                    matched_members.append({
                        'bioguide_id': member.member_id_bioguide,
                        'name': f"{member.first} {member.last}",
                        'state': member.state,
                        'district': member.district,
                        'party': member.party
                    })
                else:
                    unmatched_names.append(name)
        
        return matched_members, unmatched_names

def save_freedom_caucus_data(members, source='website_scrape'):
    """Save Freedom Caucus membership data to a JSON file."""
    
    data = {
        'caucus': 'Freedom Caucus',
        'source': source,
        'last_updated': datetime.now().isoformat(),
        'total_members': len(members),
        'members': members
    }
    
    filename = 'cache/freedom_caucus_members.json'
    os.makedirs('cache', exist_ok=True)
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"💾 Saved Freedom Caucus data to {filename}")
    return filename

def main():
    """Main function to scrape and process Freedom Caucus membership."""
    
    print("🔍 FREEDOM CAUCUS MEMBERSHIP SCRAPER")
    print("=" * 50)
    
    # Try to scrape the website first
    scraped_members = scrape_freedom_caucus_website()
    
    if scraped_members:
        print(f"✅ Successfully scraped {len(scraped_members)} members from website")
        source = 'website_scrape'
        members_to_process = scraped_members
    else:
        print("⚠️  Website scraping failed, using known member list")
        scraped_members = get_known_freedom_caucus_members()
        source = 'manual_list'
        members_to_process = scraped_members
    
    # Match to database
    print(f"\n🔍 Matching {len(members_to_process)} members to database...")
    matched_members, unmatched_names = match_members_to_database(members_to_process)
    
    print(f"✅ Matched {len(matched_members)} members to database")
    if unmatched_names:
        print(f"⚠️  {len(unmatched_names)} names couldn't be matched:")
        for name in unmatched_names[:10]:  # Show first 10
            print(f"   - {name}")
        if len(unmatched_names) > 10:
            print(f"   ... and {len(unmatched_names) - 10} more")
    
    # Save the data
    if matched_members:
        filename = save_freedom_caucus_data(matched_members, source)
        
        print(f"\n📊 FREEDOM CAUCUS SUMMARY:")
        print(f"   Total members: {len(matched_members)}")
        print(f"   Source: {source}")
        print(f"   Data saved to: {filename}")
        
        # Show some matched members
        print(f"\n👥 Sample matched members:")
        for member in matched_members[:5]:
            print(f"   - {member['name']} ({member['state']}-{member['district']})")
        if len(matched_members) > 5:
            print(f"   ... and {len(matched_members) - 5} more")
    else:
        print("❌ No members could be matched to database")

if __name__ == "__main__":
    main()
