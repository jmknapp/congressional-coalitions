#!/usr/bin/env python3
"""
Scrape Progressive Caucus membership from their official website and other sources.
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

def scrape_progressive_caucus_website():
    """Scrape the Progressive Caucus website for current membership."""
    
    # Try multiple Progressive Caucus sources
    urls = [
        "https://cpc-grijalva.house.gov/members",
        "https://progressives.house.gov/members",
        "https://cpc-grijalva.house.gov/"
    ]
    
    for url in urls:
        try:
            print(f"🔍 Scraping Progressive Caucus website: {url}")
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
    
    print("❌ All Progressive Caucus websites failed")
    return []

def get_known_progressive_caucus_members():
    """Get a manually curated list of known Progressive Caucus members as backup."""
    
    # This is a manually maintained list based on public information
    # You can update this list as you find new information
    known_members = [
        "Alexandria Ocasio-Cortez",
        "Ilhan Omar", 
        "Rashida Tlaib",
        "Ayanna Pressley",
        "Jamaal Bowman",
        "Cori Bush",
        "Pramila Jayapal",
        "Ro Khanna",
        "Barbara Lee",
        "Mark Pocan",
        "Katie Porter",
        "Jan Schakowsky",
        "Adam Schiff",
        "Maxine Waters",
        "Bonnie Watson Coleman",
        "Jared Huffman",
        "Raul Grijalva",
        "Earl Blumenauer",
        "Jim McGovern",
        "Chellie Pingree",
        "Lloyd Doggett",
        "Danny Davis",
        "Bobby Rush",
        "Danny K. Davis",
        "John Lewis",
        "Al Green",
        "Sheila Jackson Lee",
        "Marcia Fudge",
        "Joyce Beatty",
        "Tim Ryan",
        "Debbie Dingell",
        "Dan Kildee",
        "Betty McCollum",
        "Keith Ellison",
        "Nydia Velazquez",
        "Jerry Nadler",
        "Carolyn Maloney",
        "Grace Meng",
        "Hakeem Jeffries",
        "Yvette Clarke",
        "Gregory Meeks",
        "Adriano Espaillat",
        "Jose Serrano",
        "Nita Lowey",
        "Eliot Engel",
        "Sean Patrick Maloney",
        "Antonio Delgado",
        "Paul Tonko",
        "Joe Morelle",
        "Brian Higgins",
        "Suzan DelBene",
        "Derek Kilmer",
        "Pramila Jayapal",
        "Suzanne Bonamici",
        "Earl Blumenauer",
        "Peter DeFazio",
        "Kurt Schrader",
        "John Garamendi",
        "Jared Huffman",
        "Mike Thompson",
        "Doris Matsui",
        "Ami Bera",
        "Mark DeSaulnier",
        "Eric Swalwell",
        "Ro Khanna",
        "Anna Eshoo",
        "Zoe Lofgren",
        "Jimmy Panetta",
        "Salud Carbajal",
        "Ted Lieu",
        "Nanette Barragán",
        "Linda Sánchez",
        "Lucille Roybal-Allard",
        "Judy Chu",
        "Adam Schiff",
        "Brad Sherman",
        "Tony Cárdenas",
        "Raul Ruiz",
        "Mark Takano",
        "Pete Aguilar",
        "Norma Torres",
        "Jim Costa",
        "Josh Harder",
        "TJ Cox",
        "Katie Porter",
        "Harley Rouda",
        "Gil Cisneros",
        "Katie Hill",
        "Julia Brownley",
        "Jared Huffman",
        "Mike Thompson",
        "Doris Matsui",
        "Ami Bera",
        "Mark DeSaulnier",
        "Eric Swalwell",
        "Ro Khanna",
        "Anna Eshoo",
        "Zoe Lofgren",
        "Jimmy Panetta",
        "Salud Carbajal",
        "Ted Lieu",
        "Nanette Barragán",
        "Linda Sánchez",
        "Lucille Roybal-Allard",
        "Judy Chu",
        "Adam Schiff",
        "Brad Sherman",
        "Tony Cárdenas",
        "Raul Ruiz",
        "Mark Takano",
        "Pete Aguilar",
        "Norma Torres",
        "Jim Costa",
        "Josh Harder",
        "TJ Cox",
        "Katie Porter",
        "Harley Rouda",
        "Gil Cisneros",
        "Katie Hill",
        "Julia Brownley"
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
                    if name == "Alexandria Ocasio-Cortez":
                        member = session.query(Member).filter(
                            Member.first == "Alexandria",
                            Member.last == "Ocasio-Cortez"
                        ).first()
                    elif name == "Ilhan Omar":
                        member = session.query(Member).filter(
                            Member.first == "Ilhan",
                            Member.last == "Omar"
                        ).first()
                    elif name == "Rashida Tlaib":
                        member = session.query(Member).filter(
                            Member.first == "Rashida",
                            Member.last == "Tlaib"
                        ).first()
                    elif name == "Ayanna Pressley":
                        member = session.query(Member).filter(
                            Member.first == "Ayanna",
                            Member.last == "Pressley"
                        ).first()
                    elif name == "Jamaal Bowman":
                        member = session.query(Member).filter(
                            Member.first == "Jamaal",
                            Member.last == "Bowman"
                        ).first()
                    elif name == "Cori Bush":
                        member = session.query(Member).filter(
                            Member.first == "Cori",
                            Member.last == "Bush"
                        ).first()
                    elif name == "Pramila Jayapal":
                        member = session.query(Member).filter(
                            Member.first == "Pramila",
                            Member.last == "Jayapal"
                        ).first()
                    elif name == "Ro Khanna":
                        member = session.query(Member).filter(
                            Member.first == "Ro",
                            Member.last == "Khanna"
                        ).first()
                    elif name == "Barbara Lee":
                        member = session.query(Member).filter(
                            Member.first == "Barbara",
                            Member.last == "Lee"
                        ).first()
                    elif name == "Mark Pocan":
                        member = session.query(Member).filter(
                            Member.first == "Mark",
                            Member.last == "Pocan"
                        ).first()
                    elif name == "Katie Porter":
                        member = session.query(Member).filter(
                            Member.first == "Katie",
                            Member.last == "Porter"
                        ).first()
                    elif name == "Jan Schakowsky":
                        member = session.query(Member).filter(
                            Member.first == "Jan",
                            Member.last == "Schakowsky"
                        ).first()
                    elif name == "Adam Schiff":
                        member = session.query(Member).filter(
                            Member.first == "Adam",
                            Member.last == "Schiff"
                        ).first()
                    elif name == "Maxine Waters":
                        member = session.query(Member).filter(
                            Member.first == "Maxine",
                            Member.last == "Waters"
                        ).first()
                    elif name == "Bonnie Watson Coleman":
                        member = session.query(Member).filter(
                            Member.first == "Bonnie",
                            Member.last == "Watson Coleman"
                        ).first()
                    elif name == "Jared Huffman":
                        member = session.query(Member).filter(
                            Member.first == "Jared",
                            Member.last == "Huffman"
                        ).first()
                    elif name == "Raul Grijalva":
                        member = session.query(Member).filter(
                            Member.first == "Raul",
                            Member.last == "Grijalva"
                        ).first()
                    elif name == "Earl Blumenauer":
                        member = session.query(Member).filter(
                            Member.first == "Earl",
                            Member.last == "Blumenauer"
                        ).first()
                    elif name == "Jim McGovern":
                        member = session.query(Member).filter(
                            Member.first == "Jim",
                            Member.last == "McGovern"
                        ).first()
                    elif name == "Chellie Pingree":
                        member = session.query(Member).filter(
                            Member.first == "Chellie",
                            Member.last == "Pingree"
                        ).first()
                    elif name == "Lloyd Doggett":
                        member = session.query(Member).filter(
                            Member.first == "Lloyd",
                            Member.last == "Doggett"
                        ).first()
                    elif name == "Danny Davis":
                        member = session.query(Member).filter(
                            Member.first == "Danny",
                            Member.last == "Davis"
                        ).first()
                    elif name == "Bobby Rush":
                        member = session.query(Member).filter(
                            Member.first == "Bobby",
                            Member.last == "Rush"
                        ).first()
                    elif name == "Danny K. Davis":
                        member = session.query(Member).filter(
                            Member.first == "Danny",
                            Member.last == "Davis"
                        ).first()
                    elif name == "John Lewis":
                        member = session.query(Member).filter(
                            Member.first == "John",
                            Member.last == "Lewis"
                        ).first()
                    elif name == "Al Green":
                        member = session.query(Member).filter(
                            Member.first == "Al",
                            Member.last == "Green"
                        ).first()
                    elif name == "Sheila Jackson Lee":
                        member = session.query(Member).filter(
                            Member.first == "Sheila",
                            Member.last == "Jackson Lee"
                        ).first()
                    elif name == "Marcia Fudge":
                        member = session.query(Member).filter(
                            Member.first == "Marcia",
                            Member.last == "Fudge"
                        ).first()
                    elif name == "Joyce Beatty":
                        member = session.query(Member).filter(
                            Member.first == "Joyce",
                            Member.last == "Beatty"
                        ).first()
                    elif name == "Tim Ryan":
                        member = session.query(Member).filter(
                            Member.first == "Tim",
                            Member.last == "Ryan"
                        ).first()
                    elif name == "Debbie Dingell":
                        member = session.query(Member).filter(
                            Member.first == "Debbie",
                            Member.last == "Dingell"
                        ).first()
                    elif name == "Dan Kildee":
                        member = session.query(Member).filter(
                            Member.first == "Dan",
                            Member.last == "Kildee"
                        ).first()
                    elif name == "Betty McCollum":
                        member = session.query(Member).filter(
                            Member.first == "Betty",
                            Member.last == "McCollum"
                        ).first()
                    elif name == "Keith Ellison":
                        member = session.query(Member).filter(
                            Member.first == "Keith",
                            Member.last == "Ellison"
                        ).first()
                    elif name == "Nydia Velazquez":
                        member = session.query(Member).filter(
                            Member.first == "Nydia",
                            Member.last == "Velazquez"
                        ).first()
                    elif name == "Jerry Nadler":
                        member = session.query(Member).filter(
                            Member.first == "Jerry",
                            Member.last == "Nadler"
                        ).first()
                    elif name == "Carolyn Maloney":
                        member = session.query(Member).filter(
                            Member.first == "Carolyn",
                            Member.last == "Maloney"
                        ).first()
                    elif name == "Grace Meng":
                        member = session.query(Member).filter(
                            Member.first == "Grace",
                            Member.last == "Meng"
                        ).first()
                    elif name == "Hakeem Jeffries":
                        member = session.query(Member).filter(
                            Member.first == "Hakeem",
                            Member.last == "Jeffries"
                        ).first()
                    elif name == "Yvette Clarke":
                        member = session.query(Member).filter(
                            Member.first == "Yvette",
                            Member.last == "Clarke"
                        ).first()
                    elif name == "Gregory Meeks":
                        member = session.query(Member).filter(
                            Member.first == "Gregory",
                            Member.last == "Meeks"
                        ).first()
                    elif name == "Adriano Espaillat":
                        member = session.query(Member).filter(
                            Member.first == "Adriano",
                            Member.last == "Espaillat"
                        ).first()
                    elif name == "Jose Serrano":
                        member = session.query(Member).filter(
                            Member.first == "Jose",
                            Member.last == "Serrano"
                        ).first()
                    elif name == "Nita Lowey":
                        member = session.query(Member).filter(
                            Member.first == "Nita",
                            Member.last == "Lowey"
                        ).first()
                    elif name == "Eliot Engel":
                        member = session.query(Member).filter(
                            Member.first == "Eliot",
                            Member.last == "Engel"
                        ).first()
                    elif name == "Sean Patrick Maloney":
                        member = session.query(Member).filter(
                            Member.first == "Sean",
                            Member.last == "Maloney"
                        ).first()
                    elif name == "Antonio Delgado":
                        member = session.query(Member).filter(
                            Member.first == "Antonio",
                            Member.last == "Delgado"
                        ).first()
                    elif name == "Paul Tonko":
                        member = session.query(Member).filter(
                            Member.first == "Paul",
                            Member.last == "Tonko"
                        ).first()
                    elif name == "Joe Morelle":
                        member = session.query(Member).filter(
                            Member.first == "Joe",
                            Member.last == "Morelle"
                        ).first()
                    elif name == "Brian Higgins":
                        member = session.query(Member).filter(
                            Member.first == "Brian",
                            Member.last == "Higgins"
                        ).first()
                    elif name == "Suzan DelBene":
                        member = session.query(Member).filter(
                            Member.first == "Suzan",
                            Member.last == "DelBene"
                        ).first()
                    elif name == "Derek Kilmer":
                        member = session.query(Member).filter(
                            Member.first == "Derek",
                            Member.last == "Kilmer"
                        ).first()
                    elif name == "Suzanne Bonamici":
                        member = session.query(Member).filter(
                            Member.first == "Suzanne",
                            Member.last == "Bonamici"
                        ).first()
                    elif name == "Peter DeFazio":
                        member = session.query(Member).filter(
                            Member.first == "Peter",
                            Member.last == "DeFazio"
                        ).first()
                    elif name == "Kurt Schrader":
                        member = session.query(Member).filter(
                            Member.first == "Kurt",
                            Member.last == "Schrader"
                        ).first()
                    elif name == "John Garamendi":
                        member = session.query(Member).filter(
                            Member.first == "John",
                            Member.last == "Garamendi"
                        ).first()
                    elif name == "Mike Thompson":
                        member = session.query(Member).filter(
                            Member.first == "Mike",
                            Member.last == "Thompson"
                        ).first()
                    elif name == "Doris Matsui":
                        member = session.query(Member).filter(
                            Member.first == "Doris",
                            Member.last == "Matsui"
                        ).first()
                    elif name == "Ami Bera":
                        member = session.query(Member).filter(
                            Member.first == "Ami",
                            Member.last == "Bera"
                        ).first()
                    elif name == "Mark DeSaulnier":
                        member = session.query(Member).filter(
                            Member.first == "Mark",
                            Member.last == "DeSaulnier"
                        ).first()
                    elif name == "Eric Swalwell":
                        member = session.query(Member).filter(
                            Member.first == "Eric",
                            Member.last == "Swalwell"
                        ).first()
                    elif name == "Jimmy Panetta":
                        member = session.query(Member).filter(
                            Member.first == "Jimmy",
                            Member.last == "Panetta"
                        ).first()
                    elif name == "Salud Carbajal":
                        member = session.query(Member).filter(
                            Member.first == "Salud",
                            Member.last == "Carbajal"
                        ).first()
                    elif name == "Ted Lieu":
                        member = session.query(Member).filter(
                            Member.first == "Ted",
                            Member.last == "Lieu"
                        ).first()
                    elif name == "Nanette Barragán":
                        member = session.query(Member).filter(
                            Member.first == "Nanette",
                            Member.last == "Barragán"
                        ).first()
                    elif name == "Linda Sánchez":
                        member = session.query(Member).filter(
                            Member.first == "Linda",
                            Member.last == "Sánchez"
                        ).first()
                    elif name == "Lucille Roybal-Allard":
                        member = session.query(Member).filter(
                            Member.first == "Lucille",
                            Member.last == "Roybal-Allard"
                        ).first()
                    elif name == "Judy Chu":
                        member = session.query(Member).filter(
                            Member.first == "Judy",
                            Member.last == "Chu"
                        ).first()
                    elif name == "Brad Sherman":
                        member = session.query(Member).filter(
                            Member.first == "Brad",
                            Member.last == "Sherman"
                        ).first()
                    elif name == "Tony Cárdenas":
                        member = session.query(Member).filter(
                            Member.first == "Tony",
                            Member.last == "Cárdenas"
                        ).first()
                    elif name == "Raul Ruiz":
                        member = session.query(Member).filter(
                            Member.first == "Raul",
                            Member.last == "Ruiz"
                        ).first()
                    elif name == "Mark Takano":
                        member = session.query(Member).filter(
                            Member.first == "Mark",
                            Member.last == "Takano"
                        ).first()
                    elif name == "Pete Aguilar":
                        member = session.query(Member).filter(
                            Member.first == "Pete",
                            Member.last == "Aguilar"
                        ).first()
                    elif name == "Norma Torres":
                        member = session.query(Member).filter(
                            Member.first == "Norma",
                            Member.last == "Torres"
                        ).first()
                    elif name == "Jim Costa":
                        member = session.query(Member).filter(
                            Member.first == "Jim",
                            Member.last == "Costa"
                        ).first()
                    elif name == "Josh Harder":
                        member = session.query(Member).filter(
                            Member.first == "Josh",
                            Member.last == "Harder"
                        ).first()
                    elif name == "TJ Cox":
                        member = session.query(Member).filter(
                            Member.first == "TJ",
                            Member.last == "Cox"
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
                    elif name == "Julia Brownley":
                        member = session.query(Member).filter(
                            Member.first == "Julia",
                            Member.last == "Brownley"
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

def save_progressive_caucus_data(members, source='website_scrape'):
    """Save Progressive Caucus membership data to a JSON file."""
    
    data = {
        'caucus': 'Progressive Caucus',
        'source': source,
        'last_updated': datetime.now().isoformat(),
        'total_members': len(members),
        'members': members
    }
    
    filename = 'cache/progressive_caucus_members.json'
    os.makedirs('cache', exist_ok=True)
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"💾 Saved Progressive Caucus data to {filename}")
    return filename

def main():
    """Main function to scrape and process Progressive Caucus membership."""
    
    print("🔍 PROGRESSIVE CAUCUS MEMBERSHIP SCRAPER")
    print("=" * 50)
    
    # Try to scrape the website first
    scraped_members = scrape_progressive_caucus_website()
    
    if scraped_members:
        print(f"✅ Successfully scraped {len(scraped_members)} members from website")
        source = 'website_scrape'
        members_to_process = scraped_members
    else:
        print("⚠️  Website scraping failed, using known member list")
        scraped_members = get_known_progressive_caucus_members()
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
    filename = save_progressive_caucus_data(matched_members, source)
    
    # Summary
    print(f"\n📊 PROGRESSIVE CAUCUS SUMMARY:")
    print(f"   Total members: {len(matched_members)}")
    print(f"   Source: {source}")
    print(f"   Data saved to: {filename}")
    
    if matched_members:
        print(f"\n👥 Sample matched members:")
        for member in matched_members[:5]:
            print(f"   - {member['name']} ({member['state']}-{member['district']})")
        if len(matched_members) > 5:
            print(f"   ... and {len(matched_members) - 5} more")
    
    print("\n✅ Progressive Caucus data collection completed!")

if __name__ == "__main__":
    main()
