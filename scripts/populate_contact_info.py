#!/usr/bin/env python3
"""
Script to populate member contact information from unitedstates/congress-legislators data.
This uses the same authoritative source as congress.gov.
"""

import os
import sys
import requests
import yaml
import time
from datetime import datetime

# Add src to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_house_members_with_contact_info():
    """
    Fetch House members with contact info from unitedstates/congress-legislators GitHub repo.
    This is the same authoritative source used by congress.gov.
    """
    print("Fetching contact info from unitedstates/congress-legislators...")
    
    # URLs for the congress-legislators data
    legislators_url = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/legislators-current.yaml"
    social_url = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/legislators-social-media.yaml"
    
    try:
        # Fetch current legislators
        print("Downloading legislators-current.yaml...")
        response = requests.get(legislators_url, timeout=30)
        response.raise_for_status()
        legislators_data = yaml.safe_load(response.text)
        
        # Fetch social media data (includes official websites)
        print("Downloading legislators-social-media.yaml...")
        response = requests.get(social_url, timeout=30)
        response.raise_for_status()
        social_data = yaml.safe_load(response.text)
        
        # Create lookup for social media data by bioguide ID
        social_lookup = {}
        for entry in social_data:
            bioguide_id = entry['id']['bioguide']
            social_lookup[bioguide_id] = entry.get('social', {})
        
        # Extract contact info for current House members
        contact_data = []
        house_count = 0
        
        for legislator in legislators_data:
            # Check if current House member
            current_terms = legislator.get('terms', [])
            if not current_terms:
                continue
                
            latest_term = current_terms[-1]
            if (latest_term.get('type') == 'rep' and 
                latest_term.get('end') >= '2024-01-01'):  # Current term
                
                bioguide_id = legislator['id']['bioguide']
                house_count += 1
                
                # Get contact info
                social_info = social_lookup.get(bioguide_id, {})
                
                # Construct email (most House members use this format)
                first_name = legislator['name']['first'].lower()
                last_name = legislator['name']['last'].lower()
                email = f"{first_name}.{last_name}@mail.house.gov"
                
                # Get website from social media data
                website = social_info.get('url', f"https://{last_name}.house.gov")
                
                # DC office info from latest term
                dc_office = latest_term.get('address', 'U.S. House of Representatives, Washington, DC 20515')
                phone = latest_term.get('phone', '(202) 225-0000')
                
                contact_info = {
                    'bioguide_id': bioguide_id,
                    'email': email,
                    'phone': phone,
                    'website': website,
                    'dc_office': dc_office
                }
                contact_data.append(contact_info)
        
        print(f"✓ Retrieved contact info for {house_count} current House members")
        return contact_data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching from GitHub: {e}")
        return []
    except yaml.YAMLError as e:
        print(f"❌ Error parsing YAML data: {e}")
        return []
    except Exception as e:
        print(f"❌ Error processing data: {e}")
        return []

def update_members_with_contact_info(contact_data):
    """Update members table with contact information."""
    if not contact_data:
        print("❌ No contact data to update")
        return
    
    try:
        # Use MySQL directly since SQLAlchemy isn't available
        import subprocess
        
        updated_count = 0
        for member in contact_data:
            bioguide_id = member['bioguide_id']
            email = member['email'] or 'NULL'
            phone = member['phone'] or 'NULL'
            website = member['website'] or 'NULL'
            dc_office = member['dc_office'] or 'NULL'
            
            # Escape single quotes in SQL values
            if email != 'NULL':
                email = f"'{email.replace("'", "''")}'"
            if phone != 'NULL':
                phone = f"'{phone.replace("'", "''")}'"
            if website != 'NULL':
                website = f"'{website.replace("'", "''")}'"
            if dc_office != 'NULL':
                dc_office = f"'{dc_office.replace("'", "''")}'"
            
            sql = f"""
            UPDATE members 
            SET email = {email}, 
                phone = {phone}, 
                website = {website}, 
                dc_office = {dc_office},
                updated_at = NOW()
            WHERE member_id_bioguide = '{bioguide_id}'
            """
            
            cmd = [
                'mysql', '-u', 'congressional', '-pcongressional123', 
                '-D', 'congressional_coalitions', '-e', sql
            ]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    updated_count += 1
                    if updated_count <= 5:  # Show first 5 for debugging
                        print(f"✓ Updated {bioguide_id}")
                else:
                    print(f"⚠ Failed to update {bioguide_id}: {result.stderr}")
            except Exception as e:
                print(f"⚠ Error updating {bioguide_id}: {e}")
        
        print(f"✓ Updated contact info for {updated_count} members")
        
    except Exception as e:
        print(f"❌ Error updating database: {e}")

def populate_sample_contact_info():
    """
    Populate some sample contact info for testing without API key.
    This adds generic congressional emails and DC phone numbers.
    """
    print("Populating sample contact info for testing...")
    
    try:
        import subprocess
        
        # Get some member IDs from the database
        cmd = [
            'mysql', '-u', 'congressional', '-pcongressional123', 
            '-D', 'congressional_coalitions', '-e', 
            "SELECT member_id_bioguide, first, last FROM members WHERE district IS NOT NULL LIMIT 10"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Error querying members: {result.stderr}")
            return
        
        lines = result.stdout.strip().split('\n')[1:]  # Skip header
        updated_count = 0
        
        for line in lines:
            if '\t' in line:
                parts = line.split('\t')
                bioguide_id = parts[0]
                first = parts[1]
                last = parts[2]
                
                # Create sample contact info
                email = f"{first.lower()}.{last.lower()}@mail.house.gov"
                phone = "(202) 225-0000"  # Generic House number
                website = f"https://{last.lower()}.house.gov"
                dc_office = "U.S. House of Representatives, Washington, DC 20515"
                
                sql = f"""
                UPDATE members 
                SET email = '{email}', 
                    phone = '{phone}', 
                    website = '{website}', 
                    dc_office = '{dc_office}',
                    updated_at = NOW()
                WHERE member_id_bioguide = '{bioguide_id}'
                """
                
                cmd = [
                    'mysql', '-u', 'congressional', '-pcongressional123', 
                    '-D', 'congressional_coalitions', '-e', sql
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    updated_count += 1
                    print(f"✓ Added sample contact info for {first} {last}")
        
        print(f"✓ Added sample contact info for {updated_count} members")
        
    except Exception as e:
        print(f"❌ Error adding sample data: {e}")

def main():
    """Main function."""
    print("Congressional Contact Info Populator")
    print("====================================")
    
    print("Using unitedstates/congress-legislators data (no API key required)...")
    contact_data = get_house_members_with_contact_info()
    
    if contact_data:
        update_members_with_contact_info(contact_data)
    else:
        print("Failed to fetch contact data. Using sample data for testing...")
        populate_sample_contact_info()

if __name__ == '__main__':
    main()
