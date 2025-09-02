#!/usr/bin/env python3
"""
Scrape Blue Dog Coalition membership from their official website and other sources.
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

def scrape_blue_dog_website():
    """Scrape the Blue Dog Coalition website for current membership."""
    
    # Try multiple Blue Dog Coalition sources
    urls = [
        "https://bluedogcaucus.house.gov/members",
        "https://bluedogcaucus.house.gov/",
        "https://bluedogcaucus.house.gov/about"
    ]
    
    for url in urls:
        try:
            print(f"🔍 Scraping Blue Dog Coalition website: {url}")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for member information
            members = []
            
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
    
    print("❌ All Blue Dog Coalition websites failed")
    return []

def get_known_blue_dog_members():
    """Get a manually curated list of known Blue Dog Coalition members as backup."""
    
    # This is a manually maintained list based on public information
    # You can update this list as you find new information
    known_members = [
        "Jared Golden",
        "Henry Cuellar", 
        "Ed Case",
        "Jim Costa",
        "Lou Correa",
        "Jim Cooper",
        "Kurt Schrader",
        "Stephanie Murphy",
        "Tom O'Halleran",
        "Collin Peterson",
        "Sanford Bishop",
        "Jim Clyburn",
        "Emanuel Cleaver",
        "David Scott",
        "Terri Sewell",
        "Cheri Bustos",
        "Ron Kind",
        "Josh Gottheimer",
        "Tom Suozzi",
        "Anthony Brindisi",
        "Max Rose",
        "Abigail Spanberger",
        "Elaine Luria",
        "Ben McAdams",
        "Xochitl Torres Small",
        "Kendra Horn",
        "Joe Cunningham",
        "Mikie Sherrill",
        "Andy Kim",
        "Jeff Van Drew",
        "Tom Malinowski",
        "Harley Rouda",
        "Gil Cisneros",
        "Katie Hill",
        "TJ Cox"
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
                    if name == "Jared Golden":
                        member = session.query(Member).filter(
                            Member.first == "Jared",
                            Member.last == "Golden"
                        ).first()
                    elif name == "Henry Cuellar":
                        member = session.query(Member).filter(
                            Member.first == "Henry",
                            Member.last == "Cuellar"
                        ).first()
                    elif name == "Ed Case":
                        member = session.query(Member).filter(
                            Member.first == "Ed",
                            Member.last == "Case"
                        ).first()
                    elif name == "Jim Costa":
                        member = session.query(Member).filter(
                            Member.first == "Jim",
                            Member.last == "Costa"
                        ).first()
                    elif name == "Lou Correa":
                        member = session.query(Member).filter(
                            Member.first == "Lou",
                            Member.last == "Correa"
                        ).first()
                    elif name == "Jim Cooper":
                        member = session.query(Member).filter(
                            Member.first == "Jim",
                            Member.last == "Cooper"
                        ).first()
                    elif name == "Kurt Schrader":
                        member = session.query(Member).filter(
                            Member.first == "Kurt",
                            Member.last == "Schrader"
                        ).first()
                    elif name == "Stephanie Murphy":
                        member = session.query(Member).filter(
                            Member.first == "Stephanie",
                            Member.last == "Murphy"
                        ).first()
                    elif name == "Tom O'Halleran":
                        member = session.query(Member).filter(
                            Member.first == "Tom",
                            Member.last == "O'Halleran"
                        ).first()
                    elif name == "Collin Peterson":
                        member = session.query(Member).filter(
                            Member.first == "Collin",
                            Member.last == "Peterson"
                        ).first()
                    elif name == "Sanford Bishop":
                        member = session.query(Member).filter(
                            Member.first == "Sanford",
                            Member.last == "Bishop"
                        ).first()
                    elif name == "Jim Clyburn":
                        member = session.query(Member).filter(
                            Member.first == "Jim",
                            Member.last == "Clyburn"
                        ).first()
                    elif name == "Emanuel Cleaver":
                        member = session.query(Member).filter(
                            Member.first == "Emanuel",
                            Member.last == "Cleaver"
                        ).first()
                    elif name == "David Scott":
                        member = session.query(Member).filter(
                            Member.first == "David",
                            Member.last == "Scott"
                        ).first()
                    elif name == "Terri Sewell":
                        member = session.query(Member).filter(
                            Member.first == "Terri",
                            Member.last == "Sewell"
                        ).first()
                    elif name == "Cheri Bustos":
                        member = session.query(Member).filter(
                            Member.first == "Cheri",
                            Member.last == "Bustos"
                        ).first()
                    elif name == "Ron Kind":
                        member = session.query(Member).filter(
                            Member.first == "Ron",
                            Member.last == "Kind"
                        ).first()
                    elif name == "Josh Gottheimer":
                        member = session.query(Member).filter(
                            Member.first == "Josh",
                            Member.last == "Gottheimer"
                        ).first()
                    elif name == "Tom Suozzi":
                        member = session.query(Member).filter(
                            Member.first == "Tom",
                            Member.last == "Suozzi"
                        ).first()
                    elif name == "Anthony Brindisi":
                        member = session.query(Member).filter(
                            Member.first == "Anthony",
                            Member.last == "Brindisi"
                        ).first()
                    elif name == "Max Rose":
                        member = session.query(Member).filter(
                            Member.first == "Max",
                            Member.last == "Rose"
                        ).first()
                    elif name == "Abigail Spanberger":
                        member = session.query(Member).filter(
                            Member.first == "Abigail",
                            Member.last == "Spanberger"
                        ).first()
                    elif name == "Elaine Luria":
                        member = session.query(Member).filter(
                            Member.first == "Elaine",
                            Member.last == "Luria"
                        ).first()
                    elif name == "Ben McAdams":
                        member = session.query(Member).filter(
                            Member.first == "Ben",
                            Member.last == "McAdams"
                        ).first()
                    elif name == "Xochitl Torres Small":
                        member = session.query(Member).filter(
                            Member.first == "Xochitl",
                            Member.last == "Torres Small"
                        ).first()
                    elif name == "Kendra Horn":
                        member = session.query(Member).filter(
                            Member.first == "Kendra",
                            Member.last == "Horn"
                        ).first()
                    elif name == "Joe Cunningham":
                        member = session.query(Member).filter(
                            Member.first == "Joe",
                            Member.last == "Cunningham"
                        ).first()
                    elif name == "Mikie Sherrill":
                        member = session.query(Member).filter(
                            Member.first == "Mikie",
                            Member.last == "Sherrill"
                        ).first()
                    elif name == "Andy Kim":
                        member = session.query(Member).filter(
                            Member.first == "Andy",
                            Member.last == "Kim"
                        ).first()
                    elif name == "Jeff Van Drew":
                        member = session.query(Member).filter(
                            Member.first == "Jeff",
                            Member.last == "Van Drew"
                        ).first()
                    elif name == "Tom Malinowski":
                        member = session.query(Member).filter(
                            Member.first == "Tom",
                            Member.last == "Malinowski"
                        ).first()
                    elif name == "Harley Rouda":
                        member = session.query(Member).filter(
                            Member.first == "Harley",
                            Member.last == "Rouda"
                        ).first()
                    elif name == "Gil Cisneros":
                        member = session.query(Member).filter(
                            Member.first == "Gil",
                            Member.last == "Cisneros"
                        ).first()
                    elif name == "Katie Hill":
                        member = session.query(Member).filter(
                            Member.first == "Katie",
                            Member.last == "Hill"
                        ).first()
                    elif name == "TJ Cox":
                        member = session.query(Member).filter(
                            Member.first == "TJ",
                            Member.last == "Cox"
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

def save_blue_dog_data(members, source='website_scrape'):
    """Save Blue Dog Coalition membership data to a JSON file."""
    
    data = {
        'caucus': 'Blue Dog Coalition',
        'source': source,
        'last_updated': datetime.now().isoformat(),
        'total_members': len(members),
        'members': members
    }
    
    filename = 'cache/blue_dog_coalition_members.json'
    os.makedirs('cache', exist_ok=True)
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"💾 Saved Blue Dog Coalition data to {filename}")
    return filename

def main():
    """Main function to scrape and process Blue Dog Coalition membership."""
    
    print("�� BLUE DOG COALITION MEMBERSHIP SCRAPER")
    print("=" * 50)
    
    # Try to scrape the website first
    scraped_members = scrape_blue_dog_website()
    
    if scraped_members:
        print(f"✅ Successfully scraped {len(scraped_members)} members from website")
        source = 'website_scrape'
        members_to_process = scraped_members
    else:
        print("⚠️  Website scraping failed, using known member list")
        scraped_members = get_known_blue_dog_members()
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
    
    # Save data
    filename = save_blue_dog_data(matched_members, source)
    
    # Summary
    print(f"\n�� BLUE DOG COALITION SUMMARY:")
    print(f"   Total members: {len(matched_members)}")
    print(f"   Source: {source}")
    print(f"   Data saved to: {filename}")
    
    if matched_members:
        print(f"\n👥 Sample matched members:")
        for member in matched_members[:5]:
            print(f"   - {member['name']} ({member['state']}-{member['district']})")
        if len(matched_members) > 5:
            print(f"   ... and {len(matched_members) - 5} more")
    
    print("\n✅ Blue Dog Coalition data collection completed!")

if __name__ == "__main__":
    main()
