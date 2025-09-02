#!/usr/bin/env python3
"""
ActBlue URL Scraper for Congressional Members

This script searches ActBlue's directory for congressional members and 
automatically updates the database with their donation page URLs.

Usage:
    python scripts/actblue_scraper.py "Alexandria Ocasio-Cortez"
    python scripts/actblue_scraper.py --all  # Process all Democratic members
    python scripts/actblue_scraper.py --state CA  # Process all CA Democratic members
    python scripts/actblue_scraper.py --test  # Test with AOC

Prerequisites:
    pip install beautifulsoup4 requests mysql-connector-python
    OR: pip install -r requirements-scraper.txt
"""

import sys
import os
import re
import time
import argparse

# Import required packages with error handling
try:
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import urlencode, urljoin
    import mysql.connector
    from mysql.connector import Error
except ImportError as e:
    print(f"❌ Missing required package: {e}")
    print("📦 Install requirements with: pip install beautifulsoup4 requests mysql-connector-python")
    print("   Or: pip install -r requirements-scraper.txt")
    sys.exit(1)

# Add the parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'congressional_coalitions',
    'user': 'congressional',
    'password': 'congressional123'
}

class ActBlueScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def search_actblue(self, member_name):
        """
        Search ActBlue directory for a member and return their donation page URL.
        
        Args:
            member_name (str): Full name of the member (e.g., "Alexandria Ocasio-Cortez")
            
        Returns:
            str or None: The donation page URL if found, None otherwise
        """
        # Extract last name for search - works better than full name
        name_parts = member_name.strip().split()
        if len(name_parts) < 2:
            print(f"❌ Invalid name format: {member_name}")
            return None
            
        # Use last name or hyphenated last name for search
        last_name = name_parts[-1].lower()
        search_query = last_name
        
        # If last name is hyphenated or has multiple parts, use the full last portion
        if len(name_parts) > 2:
            # Handle names like "Ocasio-Cortez" or "Van Hollen"
            potential_last = " ".join(name_parts[-2:]).lower()
            if "-" in potential_last or len(name_parts) > 2:
                search_query = potential_last.replace(" ", "-")
        
        print(f"🔍 Searching ActBlue for: {member_name} (query: {search_query})")
        
        try:
            # Search ActBlue directory
            search_url = f"https://secure.actblue.com/directory?query={search_query}"
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Debug: Save the HTML to see what we're working with
            if "ocasio" in search_query.lower():
                print(f"🔍 Debug: Page title contains: {soup.title.string if soup.title else 'No title'}")
                # Look for the main content area
                main_content = soup.find('main') or soup.find('div', class_='container') or soup.body
                print(f"🔍 Debug: Found main content area: {bool(main_content)}")
            
            # Look for candidate entries using various selectors based on the actual HTML structure
            candidate_entries = []
            
            # Try multiple selectors that might match ActBlue's structure
            selectors_to_try = [
                'div.candidate-entry',
                'article',
                'div[class*="candidate"]',
                'div[class*="entry"]',
                'div[class*="card"]',
                'div[class*="result"]',
                'div[class*="item"]',
                'section',
                # Look for areas that contain candidate info
                'div:has(h3)',
                'div:has(img)',
                'div:has(a[href*="contribute"])',
                'div:has(a[href*="donate"])'
            ]
            
            for selector in selectors_to_try:
                try:
                    entries = soup.select(selector)
                    if entries:
                        candidate_entries.extend(entries)
                        print(f"🔍 Found {len(entries)} entries with selector: {selector}")
                except Exception as e:
                    continue
            
            # Remove duplicates while preserving order
            unique_entries = []
            seen = set()
            for entry in candidate_entries:
                entry_html = str(entry)[:100]  # First 100 chars as identifier
                if entry_html not in seen:
                    unique_entries.append(entry)
                    seen.add(entry_html)
            
            candidate_entries = unique_entries
            print(f"📋 Found {len(candidate_entries)} unique candidate entries")
            
            for entry in candidate_entries:
                # Look for the candidate name in the entry
                name_element = entry.find('h3') or entry.find('h2') or entry.find('h4')
                if not name_element:
                    continue
                    
                candidate_name = name_element.get_text(strip=True)
                print(f"🧑‍💼 Checking candidate: {candidate_name}")
                
                # Check if this matches our target member (fuzzy matching)
                if self.names_match(member_name, candidate_name):
                    print(f"✅ Found matching candidate: {candidate_name}")
                    
                    # Look for the donation link with multiple strategies
                    donation_link = None
                    
                    # Method 1: Look for "Contribute" links specifically (prioritize over "Go to website")
                    contribute_links = entry.find_all('a', string=re.compile(r'Contribute', re.I))
                    if contribute_links:
                        donation_link = contribute_links[0].get('href')
                        print(f"🔗 Found donation link via 'Contribute' text: {donation_link}")
                    
                    # Fallback to other donation-related text if no "Contribute" found
                    if not donation_link:
                        other_donation_links = entry.find_all('a', string=re.compile(r'(Donate|Go to website)', re.I))
                        if other_donation_links:
                            donation_link = other_donation_links[0].get('href')
                            print(f"🔗 Found donation link via other text match: {donation_link}")
                    
                    # Method 2: Look for buttons/links with donation-related classes
                    if not donation_link:
                        donation_selectors = [
                            'a[class*="contribute"]',
                            'a[class*="donate"]', 
                            'a[class*="button"]',
                            'button[class*="contribute"]',
                            'button[class*="donate"]'
                        ]
                        for selector in donation_selectors:
                            elements = entry.select(selector)
                            if elements:
                                donation_link = elements[0].get('href')
                                if donation_link:
                                    print(f"🔗 Found donation link via selector {selector}: {donation_link}")
                                    break
                    
                    # Method 3: Look for any link that contains donation-related URLs
                    if not donation_link:
                        all_links = entry.find_all('a', href=True)
                        for link in all_links:
                            href = link.get('href', '')
                            link_text = link.get_text(strip=True).lower()
                            
                            # Check if URL or text suggests it's a donation link
                            donation_indicators = [
                                'secure.actblue.com/donate',
                                'actblue.com/donate',
                                '/donate/',
                                'contribute',
                                'donation'
                            ]
                            
                            if any(indicator in href.lower() or indicator in link_text for indicator in donation_indicators):
                                donation_link = href
                                print(f"🔗 Found donation link via URL/text analysis: {donation_link}")
                                break
                    
                    # Method 4: If we found the right candidate but no clear donation link,
                    # try to find ANY link from this entry that could be the donation page
                    if not donation_link:
                        all_links = entry.find_all('a', href=True)
                        for link in all_links:
                            href = link.get('href', '')
                            if 'actblue.com' in href and href not in ['/', '#']:
                                donation_link = href
                                print(f"🔗 Found potential donation link (fallback): {donation_link}")
                                break
                    
                    if donation_link:
                        # Ensure the URL is absolute
                        if donation_link.startswith('/'):
                            donation_link = urljoin('https://secure.actblue.com', donation_link)
                        elif not donation_link.startswith('http'):
                            donation_link = f"https://secure.actblue.com{donation_link}"
                            
                        print(f"💰 Found donation link: {donation_link}")
                        return donation_link
                    else:
                        print(f"⚠️  Found candidate but no donation link")
            
            print(f"❌ No matching candidate found for {member_name}")
            return None
            
        except requests.RequestException as e:
            print(f"❌ Error searching ActBlue: {e}")
            return None
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return None
    
    def names_match(self, target_name, candidate_name):
        """
        Check if two names likely refer to the same person.
        Handles variations in formatting, nicknames, etc.
        """
        target_parts = target_name.lower().split()
        candidate_parts = candidate_name.lower().split()
        
        # Remove common titles and suffixes
        titles = {'rep.', 'senator', 'sen.', 'congressman', 'congresswoman', 'dr.', 'mr.', 'ms.', 'mrs.'}
        suffixes = {'jr.', 'sr.', 'ii', 'iii', 'iv'}
        
        target_clean = [p for p in target_parts if p not in titles and p not in suffixes]
        candidate_clean = [p for p in candidate_parts if p not in titles and p not in suffixes]
        
        if len(target_clean) < 2 or len(candidate_clean) < 2:
            return False
        
        # Check if last names match
        if target_clean[-1] != candidate_clean[-1]:
            return False
        
        # Check if first names match or are similar (nicknames, etc.)
        first_target = target_clean[0]
        first_candidate = candidate_clean[0]
        
        # Exact match
        if first_target == first_candidate:
            return True
        
        # Check if one is a nickname of the other
        nicknames = {
            'alexandria': ['alex', 'ally'],
            'elizabeth': ['liz', 'beth', 'betty'],
            'katherine': ['kate', 'kathy', 'katie'],
            'robert': ['rob', 'bob', 'bobby'],
            'william': ['bill', 'will', 'billy'],
            'james': ['jim', 'jimmy', 'jamie'],
            'joseph': ['joe', 'joey'],
            'michael': ['mike', 'mick'],
            'christopher': ['chris'],
            'anthony': ['tony'],
            'benjamin': ['ben'],
            'matthew': ['matt'],
            'andrew': ['andy', 'drew']
        }
        
        for full_name, nicks in nicknames.items():
            if (first_target == full_name and first_candidate in nicks) or \
               (first_candidate == full_name and first_target in nicks):
                return True
        
        # Check if first name starts the same (for abbreviated names)
        if len(first_target) >= 3 and len(first_candidate) >= 3:
            if first_target[:3] == first_candidate[:3]:
                return True
        
        return False

class DatabaseManager:
    def __init__(self):
        self.connection = None
        
    def connect(self):
        """Connect to the MySQL database."""
        try:
            self.connection = mysql.connector.connect(**DB_CONFIG)
            if self.connection.is_connected():
                print("📊 Connected to database")
                return True
        except Error as e:
            print(f"❌ Database connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the database."""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("📊 Database disconnected")
    
    def get_democratic_members(self, state_filter=None):
        """
        Get list of Democratic House members from the database.
        
        Args:
            state_filter (str, optional): Filter by state (e.g., 'CA', 'NY')
            
        Returns:
            list: List of tuples (bioguide_id, full_name, state, district, current_actblue_url)
        """
        if not self.connection:
            return []
        
        try:
            cursor = self.connection.cursor()
            
            query = """
                SELECT member_id_bioguide, CONCAT(first, ' ', last) as full_name, 
                       state, district, actblue_url
                FROM members 
                WHERE district IS NOT NULL 
                AND party IN ('D', 'Democrat', 'Democratic')
            """
            params = []
            
            if state_filter:
                query += " AND state = %s"
                params.append(state_filter.upper())
            
            query += " ORDER BY state, district"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
            
            return results
            
        except Error as e:
            print(f"❌ Database query error: {e}")
            return []
    
    def update_actblue_url(self, bioguide_id, actblue_url):
        """
        Update the ActBlue URL for a specific member.
        
        Args:
            bioguide_id (str): Member's bioguide ID
            actblue_url (str): The ActBlue donation URL
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connection:
            return False
        
        try:
            cursor = self.connection.cursor()
            
            query = "UPDATE members SET actblue_url = %s WHERE member_id_bioguide = %s"
            cursor.execute(query, (actblue_url, bioguide_id))
            self.connection.commit()
            
            if cursor.rowcount > 0:
                print(f"✅ Updated database: {bioguide_id} -> {actblue_url}")
                cursor.close()
                return True
            else:
                print(f"❌ No member found with bioguide_id: {bioguide_id}")
                cursor.close()
                return False
                
        except Error as e:
            print(f"❌ Database update error: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description='Scrape ActBlue URLs for Congressional members')
    parser.add_argument('member_name', nargs='?', help='Full name of the member to search for')
    parser.add_argument('--all', action='store_true', help='Process all Democratic members')
    parser.add_argument('--state', help='Process all Democratic members from a specific state (e.g., CA, NY)')
    parser.add_argument('--test', action='store_true', help='Test with Alexandria Ocasio-Cortez (no database update)')
    parser.add_argument('--delay', type=float, default=2.0, help='Delay between requests in seconds (default: 2.0)')
    parser.add_argument('--skip-existing', action='store_true', help='Skip members who already have ActBlue URLs')
    parser.add_argument('--dry-run', action='store_true', help='Search but do not update database')
    
    args = parser.parse_args()
    
    if not args.member_name and not args.all and not args.state and not args.test:
        parser.print_help()
        sys.exit(1)
    
    # Initialize components
    scraper = ActBlueScraper()
    
    # Test mode - no database required
    if args.test:
        print("🧪 Test mode: Searching for Alexandria Ocasio-Cortez")
        actblue_url = scraper.search_actblue("Alexandria Ocasio-Cortez")
        if actblue_url:
            print(f"🎉 Found ActBlue URL: {actblue_url}")
        else:
            print("😞 No ActBlue page found")
        return
    
    # Database operations
    db = DatabaseManager()
    
    if not db.connect():
        print("❌ Could not connect to database")
        sys.exit(1)
    
    try:
        if args.member_name:
            # Single member mode
            print(f"🎯 Processing single member: {args.member_name}")
            
            # Get member from database to find bioguide_id
            members = db.get_democratic_members()
            target_member = None
            
            for bioguide_id, full_name, state, district, current_url in members:
                if scraper.names_match(args.member_name, full_name):
                    target_member = (bioguide_id, full_name, state, district, current_url)
                    break
            
            if not target_member:
                print(f"❌ Member not found in database: {args.member_name}")
                return
            
            bioguide_id, full_name, state, district, current_url = target_member
            
            if current_url and args.skip_existing:
                print(f"⏭️  Skipping {full_name} - already has URL: {current_url}")
                return
            
            actblue_url = scraper.search_actblue(full_name)
            if actblue_url:
                if args.dry_run:
                    print(f"🔍 Dry run: Would update {full_name} with URL: {actblue_url}")
                else:
                    db.update_actblue_url(bioguide_id, actblue_url)
                    print(f"🎉 Success! Updated {full_name} with URL: {actblue_url}")
            else:
                print(f"😞 No ActBlue page found for {full_name}")
        
        else:
            # Batch mode
            members = db.get_democratic_members(args.state)
            print(f"👥 Processing {len(members)} Democratic members" + 
                  (f" from {args.state}" if args.state else ""))
            
            success_count = 0
            skip_count = 0
            
            for i, (bioguide_id, full_name, state, district, current_url) in enumerate(members, 1):
                print(f"\n[{i}/{len(members)}] Processing: {full_name} ({state}-{district})")
                
                if current_url and args.skip_existing:
                    print(f"⏭️  Skipping - already has URL: {current_url}")
                    skip_count += 1
                    continue
                
                actblue_url = scraper.search_actblue(full_name)
                if actblue_url:
                    if args.dry_run:
                        print(f"🔍 Dry run: Would update {full_name} with URL: {actblue_url}")
                        success_count += 1
                    else:
                        if db.update_actblue_url(bioguide_id, actblue_url):
                            success_count += 1
                            print(f"🎉 Success! Updated {full_name}")
                        else:
                            print(f"❌ Failed to update database for {full_name}")
                else:
                    print(f"😞 No ActBlue page found for {full_name}")
                
                # Rate limiting - be respectful to ActBlue's servers
                if i < len(members):  # Don't delay after the last request
                    print(f"⏳ Waiting {args.delay} seconds...")
                    time.sleep(args.delay)
            
            print(f"\n📊 Summary:")
            print(f"   ✅ Successfully updated: {success_count}")
            print(f"   ⏭️  Skipped (existing URLs): {skip_count}")
            print(f"   ❌ Not found: {len(members) - success_count - skip_count}")
    
    finally:
        db.disconnect()

if __name__ == "__main__":
    main()
