#!/usr/bin/env python3
"""
Script to extend the existing dataset to include 2025 data.
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

class DataExtender:
    """Extends existing data to include 2025."""
    
    def __init__(self):
        self.congress = 119
        
    def extend_bills_to_2025(self):
        """Add 2025 bills to existing dataset."""
        logger.info("Adding 2025 bills...")
        
        with get_db_session() as session:
            # Get existing members for sponsors
            members = session.query(Member).all()
            
            # Get the highest bill number
            max_bill = session.query(Bill).order_by(Bill.number.desc()).first()
            next_bill_number = (max_bill.number if max_bill else 0) + 1
            
            # 2025 bill titles
            bill_titles_2025 = [
                'AI Regulation and Safety Act of 2025',
                'Climate Resilience and Adaptation Act',
                'Digital Privacy Protection Act',
                'Infrastructure Modernization Act',
                'Healthcare Access Expansion Act',
                'Education Technology Advancement Act',
                'Cybersecurity Enhancement Act',
                'Renewable Energy Investment Act',
                'Small Business Digital Transformation Act',
                'Mental Health Services Expansion Act',
                'Rural Broadband Access Act',
                'Veterans Healthcare Modernization Act',
                'Immigration Reform and Border Security Act',
                'Tax Code Simplification Act',
                'Housing Affordability Act',
                'Transportation Infrastructure Act',
                'Agricultural Innovation Act',
                'Workforce Development and Training Act',
                'Environmental Protection Enhancement Act',
                'National Security Technology Act'
            ]
            
            bill_types = ['hr', 's', 'hjres', 'sjres', 'hconres', 'sconres']
            
            # Generate 500 new bills for 2025
            for i in range(500):
                sponsor = random.choice(members)
                bill_type = random.choice(bill_types)
                title = random.choice(bill_titles_2025)
                
                # Random introduction date in 2025
                start_date = date(2025, 1, 1)
                end_date = date(2025, 12, 31)
                days_between = (end_date - start_date).days
                random_days = random.randint(0, days_between)
                introduced_date = start_date + timedelta(days=random_days)
                
                bill = Bill(
                    bill_id=f'{bill_type}-{next_bill_number}-{self.congress}',
                    congress=self.congress,
                    chamber='house' if bill_type.startswith('h') else 'senate',
                    number=next_bill_number,
                    type=bill_type,
                    title=title,
                    introduced_date=introduced_date,
                    sponsor_bioguide=sponsor.member_id_bioguide
                )
                
                session.add(bill)
                next_bill_number += 1
                
                # Add some cosponsors
                num_cosponsors = random.randint(0, 15)
                selected_cosponsors = random.sample(members, min(num_cosponsors, len(members)))
                
                for j, cosponsor in enumerate(selected_cosponsors):
                    is_original = j < 3 and random.random() < 0.7
                    cosponsor_date = introduced_date if is_original else introduced_date + timedelta(days=random.randint(1, 30))
                    
                    cosponsor_record = Cosponsor(
                        bill_id=bill.bill_id,
                        member_id_bioguide=cosponsor.member_id_bioguide,
                        date=cosponsor_date,
                        is_original=is_original
                    )
                    session.add(cosponsor_record)
            
            session.commit()
            logger.info(f"Added 500 new bills for 2025")
    
    def extend_rollcalls_to_2025(self):
        """Add 2025 roll calls to existing dataset."""
        logger.info("Adding 2025 roll calls...")
        
        with get_db_session() as session:
            # Get existing bills for roll call references
            bills = session.query(Bill).filter(Bill.introduced_date >= date(2025, 1, 1)).all()
            
            # Get the highest roll call number
            max_rollcall = session.query(Rollcall).order_by(Rollcall.rc_number.desc()).first()
            next_rc_number = (max_rollcall.rc_number if max_rollcall else 0) + 1
            
            # 2025 vote questions
            questions_2025 = [
                'On Passage of the AI Regulation Bill',
                'On Motion to Suspend the Rules for Climate Bill',
                'On Motion to Recommit Digital Privacy Bill',
                'On Motion to Table Infrastructure Amendment',
                'On the Healthcare Access Amendment',
                'On the Motion to Proceed to Education Bill',
                'On Cloture for Cybersecurity Bill',
                'On Confirmation of Technology Director',
                'On the Renewable Energy Resolution',
                'On the Mental Health Services Motion',
                'On Rural Broadband Access Amendment',
                'On Veterans Healthcare Modernization',
                'On Immigration Reform Motion',
                'On Tax Code Simplification',
                'On Housing Affordability Amendment',
                'On Transportation Infrastructure',
                'On Agricultural Innovation',
                'On Workforce Development',
                'On Environmental Protection',
                'On National Security Technology'
            ]
            
            # Generate 200 new roll calls for 2025
            for i in range(200):
                bill = random.choice(bills) if bills and random.random() < 0.8 else None
                question = random.choice(questions_2025)
                
                # Random vote date in 2025
                start_date = date(2025, 1, 1)
                end_date = date(2025, 12, 31)
                days_between = (end_date - start_date).days
                random_days = random.randint(0, days_between)
                vote_date = start_date + timedelta(days=random_days)
                
                rollcall = Rollcall(
                    rollcall_id=f'rc-{next_rc_number}-{self.congress}',
                    congress=self.congress,
                    chamber='house' if random.random() < 0.6 else 'senate',
                    session=2,  # 2025 is session 2 of 119th Congress
                    rc_number=next_rc_number,
                    question=question,
                    bill_id=bill.bill_id if bill else None,
                    date=vote_date
                )
                
                session.add(rollcall)
                next_rc_number += 1
            
            session.commit()
            logger.info(f"Added 200 new roll calls for 2025")
    
    def extend_votes_to_2025(self):
        """Add 2025 votes to existing dataset."""
        logger.info("Adding 2025 votes...")
        
        with get_db_session() as session:
            # Get 2025 roll calls
            rollcalls_2025 = session.query(Rollcall).filter(Rollcall.date >= date(2025, 1, 1)).all()
            
            # Get all members
            members = session.query(Member).all()
            
            for rollcall in rollcalls_2025:
                # Determine which members can vote (based on chamber)
                chamber_members = [m for m in members if 
                                 (rollcall.chamber == 'house' and m.district is not None) or
                                 (rollcall.chamber == 'senate' and m.district is None)]
                
                for member in chamber_members:
                    # Generate realistic voting pattern based on party
                    if member.party == 'R':
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
                    
                    vote = Vote(
                        rollcall_id=rollcall.rollcall_id,
                        member_id_bioguide=member.member_id_bioguide,
                        vote_code=vote_code
                    )
                    session.add(vote)
            
            session.commit()
            logger.info(f"Added votes for {len(rollcalls_2025)} roll calls in 2025")
    
    def extend_all_data(self):
        """Extend all data to include 2025."""
        logger.info("Extending dataset to include 2025 data...")
        
        try:
            self.extend_bills_to_2025()
            self.extend_rollcalls_to_2025()
            self.extend_votes_to_2025()
            
            logger.info("Successfully extended dataset to include 2025 data!")
            
        except Exception as e:
            logger.error(f"Error extending data: {e}")
            raise

def main():
    """Main function."""
    logger.info("Starting data extension to 2025...")
    
    extender = DataExtender()
    extender.extend_all_data()
    
    logger.info("Data extension completed!")

if __name__ == "__main__":
    main()
