#!/usr/bin/env python3
"""
Script to load comprehensive 119th Congress data with realistic numbers.
"""

import os
import sys
import logging
import random
from datetime import datetime, date, timedelta
from typing import List, Dict

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_db_session
from scripts.setup_db import Member, Bill, Rollcall, Vote, Cosponsor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CompleteCongressLoader:
    """Loader for comprehensive 119th Congress data."""
    
    def __init__(self):
        self.congress = 119
        self.states = [
            'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
            'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
            'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
            'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
            'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
        ]
        
        # Party distribution (approximate current Congress)
        self.house_party_distribution = {'R': 0.52, 'D': 0.48}  # Republican majority
        self.senate_party_distribution = {'D': 0.51, 'R': 0.49}  # Democratic majority
        
    def generate_house_members(self) -> List[Dict]:
        """Generate comprehensive House member data."""
        members = []
        member_id_counter = 1
        
        # Correct district counts for all 50 states (total should be 435)
        state_districts = {
            'AL': 7, 'AK': 1, 'AZ': 9, 'AR': 4, 'CA': 52, 'CO': 8, 'CT': 5, 'DE': 1, 'FL': 28, 'GA': 14,
            'HI': 2, 'ID': 2, 'IL': 17, 'IN': 9, 'IA': 4, 'KS': 4, 'KY': 6, 'LA': 6, 'ME': 2, 'MD': 8,
            'MA': 9, 'MI': 13, 'MN': 8, 'MS': 4, 'MO': 8, 'MT': 2, 'NE': 3, 'NV': 4, 'NH': 2, 'NJ': 12,
            'NM': 3, 'NY': 26, 'NC': 14, 'ND': 1, 'OH': 15, 'OK': 5, 'OR': 6, 'PA': 17, 'RI': 2, 'SC': 7,
            'SD': 1, 'TN': 9, 'TX': 38, 'UT': 4, 'VT': 1, 'VA': 11, 'WA': 10, 'WV': 2, 'WI': 8, 'WY': 1
        }
        
        # Generate 435 House members
        for state, districts in state_districts.items():
            for district in range(1, districts + 1):
                # Determine party based on distribution
                party = 'R' if random.random() < self.house_party_distribution['R'] else 'D'
                
                # Generate realistic name
                first_names = ['James', 'John', 'Robert', 'Michael', 'William', 'David', 'Richard', 'Joseph', 'Thomas', 'Christopher',
                              'Mary', 'Patricia', 'Jennifer', 'Linda', 'Elizabeth', 'Barbara', 'Susan', 'Jessica', 'Sarah', 'Karen']
                last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
                             'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin']
                
                first = random.choice(first_names)
                last = random.choice(last_names)
                
                member = {
                    'member_id_bioguide': f'{last[0]}{str(member_id_counter).zfill(6)}',
                    'first': first,
                    'last': last,
                    'party': party,
                    'state': state,
                    'district': district,
                    'start_date': date(2023, 1, 3)
                }
                members.append(member)
                member_id_counter += 1
        
        return members
    
    def generate_senate_members(self) -> List[Dict]:
        """Generate comprehensive Senate member data."""
        members = []
        member_id_counter = 1000
        
        # Generate 100 Senate members (2 per state)
        for state in self.states:
            for seat in range(1, 3):
                # Determine party based on distribution
                party = 'D' if random.random() < self.senate_party_distribution['D'] else 'R'
                
                # Generate realistic name
                first_names = ['James', 'John', 'Robert', 'Michael', 'William', 'David', 'Richard', 'Joseph', 'Thomas', 'Christopher',
                              'Mary', 'Patricia', 'Jennifer', 'Linda', 'Elizabeth', 'Barbara', 'Susan', 'Jessica', 'Sarah', 'Karen']
                last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
                             'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin']
                
                first = random.choice(first_names)
                last = random.choice(last_names)
                
                member = {
                    'member_id_bioguide': f'{last[0]}{str(member_id_counter).zfill(6)}',
                    'first': first,
                    'last': last,
                    'party': party,
                    'state': state,
                    'district': None,  # Senators don't have districts
                    'start_date': date(2023, 1, 3)
                }
                members.append(member)
                member_id_counter += 1
        
        return members
    
    def generate_bills(self, members: List[Dict]) -> List[Dict]:
        """Generate comprehensive bill data."""
        bills = []
        bill_counter = 1
        
        # Generate ~2000 bills (realistic for a Congress)
        for _ in range(2000):
            # Randomly select a sponsor
            sponsor = random.choice(members)
            
            # Bill types
            bill_types = ['hr', 's', 'hjres', 'sjres', 'hconres', 'sconres']
            bill_type = random.choice(bill_types)
            
            # Bill titles
            bill_titles = [
                'Infrastructure Investment and Jobs Act',
                'American Rescue Plan Act',
                'Inflation Reduction Act',
                'Bipartisan Infrastructure Law',
                'CHIPS and Science Act',
                'Respect for Marriage Act',
                'Electoral Count Reform Act',
                'National Defense Authorization Act',
                'Farm Bill',
                'Tax Relief for American Families',
                'Healthcare Reform Act',
                'Education Funding Act',
                'Environmental Protection Act',
                'Immigration Reform Act',
                'Veterans Benefits Act',
                'Small Business Support Act',
                'Rural Development Act',
                'Urban Renewal Act',
                'Technology Innovation Act',
                'Workforce Development Act'
            ]
            
            title = random.choice(bill_titles)
            
            # Random introduction date in 2023-2024
            start_date = date(2023, 1, 3)
            end_date = date(2024, 12, 31)
            days_between = (end_date - start_date).days
            random_days = random.randint(0, days_between)
            introduced_date = start_date + timedelta(days=random_days)
            
            bill = {
                'bill_id': f'{bill_type}-{bill_counter}-{self.congress}',
                'congress': self.congress,
                'chamber': 'house' if bill_type.startswith('h') else 'senate',
                'number': bill_counter,
                'type': bill_type,
                'title': title,
                'introduced_date': introduced_date,
                'sponsor_bioguide': sponsor['member_id_bioguide']
            }
            bills.append(bill)
            bill_counter += 1
        
        return bills
    
    def generate_rollcalls(self, bills: List[Dict]) -> List[Dict]:
        """Generate comprehensive roll call data."""
        rollcalls = []
        rollcall_counter = 1
        
        # Generate ~500 roll calls (realistic for a Congress)
        for _ in range(500):
            # Randomly select a bill (or None for procedural votes)
            bill = random.choice(bills) if random.random() < 0.7 else None
            
            # Vote questions
            questions = [
                'On Passage of the Bill',
                'On Motion to Suspend the Rules',
                'On Motion to Recommit',
                'On Motion to Table',
                'On the Amendment',
                'On the Motion to Proceed',
                'On Cloture',
                'On Confirmation',
                'On the Resolution',
                'On the Motion to Adjourn'
            ]
            
            question = random.choice(questions)
            
            # Random vote date
            start_date = date(2023, 1, 3)
            end_date = date(2024, 12, 31)
            days_between = (end_date - start_date).days
            random_days = random.randint(0, days_between)
            vote_date = start_date + timedelta(days=random_days)
            
            rollcall = {
                'rollcall_id': f'rc-{rollcall_counter}-{self.congress}',
                'congress': self.congress,
                'chamber': 'house' if random.random() < 0.6 else 'senate',
                'session': 1 if vote_date.year == 2023 else 2,
                'rc_number': rollcall_counter,
                'question': question,
                'bill_id': bill['bill_id'] if bill else None,
                'date': vote_date
            }
            rollcalls.append(rollcall)
            rollcall_counter += 1
        
        return rollcalls
    
    def generate_votes(self, rollcalls: List[Dict], members: List[Dict]) -> List[Dict]:
        """Generate comprehensive vote data."""
        votes = []
        
        for rollcall in rollcalls:
            # Determine which members can vote (based on chamber)
            chamber_members = [m for m in members if 
                             (rollcall['chamber'] == 'house' and m['district'] is not None) or
                             (rollcall['chamber'] == 'senate' and m['district'] is None)]
            
            for member in chamber_members:
                # Generate realistic voting pattern based on party
                if member['party'] == 'R':
                    # Republicans more likely to vote Nay on Democratic bills
                    vote_prob = 0.3 if random.random() < 0.6 else 0.7
                else:
                    # Democrats more likely to vote Yea on Democratic bills
                    vote_prob = 0.7 if random.random() < 0.6 else 0.3
                
                # Add some randomness and bipartisanship
                if random.random() < 0.1:  # 10% chance of cross-party voting
                    vote_prob = 1 - vote_prob
                
                # Determine vote
                if random.random() < vote_prob:
                    vote_code = 'Yea'
                else:
                    vote_code = 'Nay'
                
                # Some members don't vote
                if random.random() < 0.05:  # 5% chance of not voting
                    vote_code = 'Not Voting'
                
                vote = {
                    'rollcall_id': rollcall['rollcall_id'],
                    'member_id_bioguide': member['member_id_bioguide'],
                    'vote_code': vote_code
                }
                votes.append(vote)
        
        return votes
    
    def generate_cosponsors(self, bills: List[Dict], members: List[Dict]) -> List[Dict]:
        """Generate comprehensive cosponsor data."""
        cosponsors = []
        
        for bill in bills:
            # Each bill gets 0-20 cosponsors
            num_cosponsors = random.randint(0, 20)
            
            # Randomly select cosponsors
            selected_cosponsors = random.sample(members, min(num_cosponsors, len(members)))
            
            for i, cosponsor in enumerate(selected_cosponsors):
                # Original cosponsors join early
                is_original = i < 3 and random.random() < 0.7
                
                # Cosponsor date
                if is_original:
                    cosponsor_date = bill['introduced_date']
                else:
                    # Later cosponsors join within 30 days
                    days_after = random.randint(1, 30)
                    cosponsor_date = bill['introduced_date'] + timedelta(days=days_after)
                
                cosponsor_data = {
                    'bill_id': bill['bill_id'],
                    'member_id_bioguide': cosponsor['member_id_bioguide'],
                    'date': cosponsor_date,
                    'is_original': is_original
                }
                cosponsors.append(cosponsor_data)
        
        return cosponsors
    
    def load_complete_data(self):
        """Load complete 119th Congress data."""
        logger.info("Generating comprehensive 119th Congress data...")
        
        # Generate data
        house_members = self.generate_house_members()
        senate_members = self.generate_senate_members()
        all_members = house_members + senate_members
        
        bills = self.generate_bills(all_members)
        rollcalls = self.generate_rollcalls(bills)
        votes = self.generate_votes(rollcalls, all_members)
        cosponsors = self.generate_cosponsors(bills, all_members)
        
        logger.info(f"Generated {len(all_members)} members, {len(bills)} bills, {len(rollcalls)} rollcalls, {len(votes)} votes, {len(cosponsors)} cosponsors")
        
        # Load into database
        with get_db_session() as session:
            logger.info("Loading members...")
            for member_data in all_members:
                member = Member(**member_data)
                session.add(member)
            session.commit()
            
            logger.info("Loading bills...")
            for bill_data in bills:
                bill = Bill(**bill_data)
                session.add(bill)
            session.commit()
            
            logger.info("Loading rollcalls...")
            for rollcall_data in rollcalls:
                rollcall = Rollcall(**rollcall_data)
                session.add(rollcall)
            session.commit()
            
            logger.info("Loading votes...")
            for vote_data in votes:
                vote = Vote(**vote_data)
                session.add(vote)
            session.commit()
            
            logger.info("Loading cosponsors...")
            for cosponsor_data in cosponsors:
                cosponsor = Cosponsor(**cosponsor_data)
                session.add(cosponsor)
            session.commit()
        
        logger.info("Complete 119th Congress data loaded successfully!")

def main():
    """Main function."""
    logger.info("Starting complete 119th Congress data generation...")
    
    loader = CompleteCongressLoader()
    loader.load_complete_data()
    
    logger.info("Data generation completed!")

if __name__ == "__main__":
    main()
