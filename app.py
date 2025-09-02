#!/usr/bin/env python3
"""
Flask web application for Congressional Coalition Analysis.
"""

import os
import sys
import json
from datetime import datetime, date
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.database import get_db_session
from scripts.setup_db import Member, Bill, Rollcall, Vote, Cosponsor, Action
from scripts.setup_caucus_tables import Caucus, CaucusMembership
from sqlalchemy import or_
from scripts.simple_house_analysis import run_simple_house_analysis
from scripts.ideological_labeling import calculate_voting_ideology_scores_fast, assign_ideological_labels
from scripts.precalculate_ideology import get_member_ideology_fast

def load_caucus_data():
    """Load caucus membership data from database."""
    print("DEBUG: load_caucus_data() called")
    caucus_data = {}
    
    try:
        with get_db_session() as session:
            # Load Freedom Caucus members
            freedom_caucus_members = session.query(CaucusMembership).join(Caucus).filter(
                Caucus.short_name == 'Freedom Caucus',
                CaucusMembership.end_date.is_(None)  # Active memberships only
            ).all()
            caucus_data['freedom_caucus'] = {m.member_id_bioguide for m in freedom_caucus_members}
            
            # Load Progressive Caucus members
            progressive_caucus_members = session.query(CaucusMembership).join(Caucus).filter(
                Caucus.short_name == 'Progressive Caucus',
                CaucusMembership.end_date.is_(None)
            ).all()
            caucus_data['progressive_caucus'] = {m.member_id_bioguide for m in progressive_caucus_members}
            
            # Load Blue Dog Coalition members
            blue_dog_members = session.query(CaucusMembership).join(Caucus).filter(
                Caucus.short_name == 'Blue Dog',
                CaucusMembership.end_date.is_(None)
            ).all()
            caucus_data['blue_dog_coalition'] = {m.member_id_bioguide for m in blue_dog_members}
            
            # Load Congressional Black Caucus members
            cbc_members = session.query(CaucusMembership).join(Caucus).filter(
                Caucus.short_name == 'CBC',
                CaucusMembership.end_date.is_(None)
            ).all()
            caucus_data['congressional_black_caucus'] = {m.member_id_bioguide for m in cbc_members}
            
            # Load MAGA Republican members from database
            maga_members = session.query(CaucusMembership).join(Caucus).filter(
                Caucus.short_name == 'MAGA',
                CaucusMembership.end_date.is_(None)
            ).all()
            caucus_data['maga_republicans'] = {m.member_id_bioguide for m in maga_members}
            
            # Load True Blue Democrats members
            true_blue_democrats_members = session.query(CaucusMembership).join(Caucus).filter(
                Caucus.short_name == 'True Blue Democrats',
                CaucusMembership.end_date.is_(None)
            ).all()
            caucus_data['true_blue_democrats'] = {m.member_id_bioguide for m in true_blue_democrats_members}
            
            print(f"DEBUG: Loaded CBC data with {len(caucus_data['congressional_black_caucus'])} members")
            print(f"DEBUG: CBC members: {sorted(list(caucus_data['congressional_black_caucus']))}")
            print(f"DEBUG: Loaded MAGA data with {len(caucus_data['maga_republicans'])} members")
            print(f"DEBUG: MAGA members: {sorted(list(caucus_data['maga_republicans']))}")
            print(f"DEBUG: load_caucus_data() returning CBC set: {caucus_data['congressional_black_caucus']}")
            
    except Exception as e:
        print(f"Error loading caucus data from database: {e}")
        # Fallback to empty sets
        caucus_data = {
            'freedom_caucus': set(),
            'progressive_caucus': set(),
            'blue_dog_coalition': set(),
            'congressional_black_caucus': set(),
            'maga_republicans': set(),
            'true_blue_democrats': set()
        }
    
    return caucus_data

app = Flask(__name__)
CORS(app)

# Note: Ideological profiles are now pre-calculated and cached for performance.
# See scripts/precalcul
# ate_ideology.py for the calculation logic.

# Set database URL

os.environ['DATABASE_URL'] = 'mysql://congressional:congressional123@localhost/congressional_coalitions'

@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('index.html')

@app.route('/api/summary')
def get_summary():
    """Get House-only database summary statistics."""
    try:
        with get_db_session() as session:
            # House-only counts
            member_count = session.query(Member).filter(Member.district.isnot(None)).count()
            bill_count = session.query(Bill).filter(Bill.chamber == 'house').count()
            rollcall_count = session.query(Rollcall).filter(Rollcall.chamber == 'house').count()
            vote_count = session.query(Vote).join(Rollcall).filter(Rollcall.chamber == 'house').count()
            cosponsor_count = session.query(Cosponsor).join(Bill).filter(Bill.chamber == 'house').count()
            
            # Get House party breakdown
            house_members = session.query(Member).filter(Member.district.isnot(None)).all()
            house_party_breakdown = {}
            
            for member in house_members:
                party = member.party or 'Unknown'
                house_party_breakdown[party] = house_party_breakdown.get(party, 0) + 1
            
            return jsonify({
                'total_members': member_count,
                'total_bills': bill_count,
                'total_rollcalls': rollcall_count,
                'total_votes': vote_count,
                'total_cosponsors': cosponsor_count,
                'house_party_breakdown': house_party_breakdown,
                'note': 'House-only data'
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/members')
def get_members():
    """Get House members only with their details."""
    try:
        # Load caucus data
        caucus_data = load_caucus_data()
        
        with get_db_session() as session:
            # Filter for House members only (those with districts)
            members = session.query(Member).filter(Member.district.isnot(None)).all()
            member_data = []
            
            for member in members:
                # Get voting statistics
                vote_count = session.query(Vote).filter(Vote.member_id_bioguide == member.member_id_bioguide).count()
                
                # Get cosponsorship count
                cosponsor_count = session.query(Cosponsor).filter(Cosponsor.member_id_bioguide == member.member_id_bioguide).count()
                
                # Check caucus memberships
                is_freedom_caucus = member.member_id_bioguide in caucus_data['freedom_caucus']
                is_progressive_caucus = member.member_id_bioguide in caucus_data['progressive_caucus']
                is_blue_dog_coalition = member.member_id_bioguide in caucus_data['blue_dog_coalition']
                is_maga_republican = member.member_id_bioguide in caucus_data['maga_republicans']
                is_congressional_black_caucus = member.member_id_bioguide in caucus_data['congressional_black_caucus']
                is_true_blue_democrat = member.member_id_bioguide in caucus_data['true_blue_democrats']
                
                # Debug logging for Kaptur
                if member.first == 'Marcy' and member.last == 'Kaptur':
                    print(f"DEBUG: Kaptur {member.member_id_bioguide} CBC check: {is_congressional_black_caucus}")
                    print(f"DEBUG: CBC data contains: {member.member_id_bioguide in caucus_data['congressional_black_caucus']}")
                    print(f"DEBUG: CBC set: {caucus_data['congressional_black_caucus']}")
                
                member_data.append({
                    'id': member.member_id_bioguide,
                    'name': f"{member.first} {member.last}",
                    'party': member.party,
                    'state': member.state,
                    'district': member.district,
                    'chamber': 'House',
                    'vote_count': vote_count,
                    'cosponsor_count': cosponsor_count,
                    'start_date': member.start_date.isoformat() if member.start_date else None,
                    'is_freedom_caucus': is_freedom_caucus,
                    'is_progressive_caucus': is_progressive_caucus,
                    'is_blue_dog_coalition': is_blue_dog_coalition,
                    'is_maga_republican': is_maga_republican,
                    'is_congressional_black_caucus': is_congressional_black_caucus,
                    'is_true_blue_democrat': is_true_blue_democrat
                })
            
            # Sort members by last name, then first name
            member_data.sort(key=lambda x: (x['name'].split()[-1], x['name'].split()[0]))
            
            return jsonify(member_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bills')
def get_bills():
    """Get House bills only with their details."""
    try:
        with get_db_session() as session:
            # Filter for House bills only and order by last action date descending
            bills = session.query(Bill).filter(Bill.chamber == 'house').all()
            bill_data = []
            
            for bill in bills:
                # Get sponsor name
                sponsor = session.query(Member).filter(Member.member_id_bioguide == bill.sponsor_bioguide).first()
                sponsor_name = f"{sponsor.first} {sponsor.last}" if sponsor else "Unknown"
                
                # Get cosponsor count
                cosponsor_count = session.query(Cosponsor).filter(Cosponsor.bill_id == bill.bill_id).count()
                
                # Get last action date and code
                last_action = session.query(Action).filter(
                    Action.bill_id == bill.bill_id
                ).order_by(Action.action_date.desc()).first()
                
                last_action_date = None
                last_action_code = None
                if last_action:
                    last_action_date = last_action.action_date.isoformat()
                    last_action_code = last_action.action_code
                
                bill_data.append({
                    'id': bill.bill_id,
                    'title': bill.title,
                    'congress': bill.congress,
                    'chamber': bill.chamber.title(),
                    'number': bill.number,
                    'type': bill.type.upper(),
                    'sponsor': sponsor_name,
                    'sponsor_party': sponsor.party if sponsor else None,
                    'cosponsor_count': cosponsor_count,
                    'introduced_date': bill.introduced_date.isoformat() if bill.introduced_date else None,
                    'last_action_date': last_action_date,
                    'last_action_code': last_action_code
                })
            
            # Sort bills by last action date descending (most recent first)
            bill_data.sort(key=lambda x: x['last_action_date'] or '1900-01-01', reverse=True)
            
            return jsonify(bill_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rollcalls')
def get_rollcalls():
    """Get House roll call votes only with their details."""
    try:
        with get_db_session() as session:
            # Filter for House rollcalls only
            rollcalls = session.query(Rollcall).filter(Rollcall.chamber == 'house').all()
            rollcall_data = []
            
            for rollcall in rollcalls:
                # Get vote counts
                yea_count = session.query(Vote).filter(
                    Vote.rollcall_id == rollcall.rollcall_id,
                    Vote.vote_code == 'Yea'
                ).count()
                
                nay_count = session.query(Vote).filter(
                    Vote.rollcall_id == rollcall.rollcall_id,
                    Vote.vote_code == 'Nay'
                ).count()
                
                present_count = session.query(Vote).filter(
                    Vote.rollcall_id == rollcall.rollcall_id,
                    Vote.vote_code == 'Present'
                ).count()
                
                # Get bill title if bill_id exists
                bill_title = None
                if rollcall.bill_id:
                    bill = session.query(Bill).filter(Bill.bill_id == rollcall.bill_id).first()
                    bill_title = bill.title if bill else None
                
                rollcall_data.append({
                    'id': rollcall.rollcall_id,
                    'congress': rollcall.congress,
                    'chamber': rollcall.chamber.title(),
                    'session': rollcall.session,
                    'rc_number': rollcall.rc_number,
                    'question': rollcall.question,
                    'bill_id': rollcall.bill_id,
                    'bill_title': bill_title,
                    'date': rollcall.date.isoformat() if rollcall.date else None,
                    'yea_count': yea_count,
                    'nay_count': nay_count,
                    'present_count': present_count,
                    'total_votes': yea_count + nay_count + present_count
                })
            
            return jsonify(rollcall_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analysis/<congress>/<chamber>')
def get_analysis(congress, chamber):
    """Get coalition analysis for a specific Congress and chamber."""
    try:
        congress = int(congress)
        chamber = chamber.lower()
        
        # Run simplified House analysis
        results = run_simple_house_analysis(congress, chamber, window_days=1000)
        
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/votes/<rollcall_id>')
def get_votes(rollcall_id):
    """Get individual votes for a specific roll call."""
    try:
        with get_db_session() as session:
            votes = session.query(Vote).filter(Vote.rollcall_id == rollcall_id).all()
            vote_data = []
            
            for vote in votes:
                # Get member details
                member = session.query(Member).filter(Member.member_id_bioguide == vote.member_id_bioguide).first()
                
                vote_data.append({
                    'member_id': vote.member_id_bioguide,
                    'member_name': f"{member.first} {member.last}" if member else "Unknown",
                    'party': member.party if member else None,
                    'state': member.state if member else None,
                    'vote_code': vote.vote_code
                })
            
            return jsonify(vote_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cosponsors/<bill_id>')
def get_cosponsors(bill_id):
    """Get cosponsors for a specific bill."""
    try:
        with get_db_session() as session:
            cosponsors = session.query(Cosponsor).filter(Cosponsor.bill_id == bill_id).all()
            cosponsor_data = []
            
            for cosponsor in cosponsors:
                # Get member details
                member = session.query(Member).filter(Member.member_id_bioguide == cosponsor.member_id_bioguide).first()
                
                cosponsor_data.append({
                    'member_id': cosponsor.member_id_bioguide,
                    'member_name': f"{member.first} {member.last}" if member else "Unknown",
                    'party': member.party if member else None,
                    'state': member.state if member else None,
                    'date': cosponsor.date.isoformat() if cosponsor.date else None,
                    'is_original': cosponsor.is_original
                })
            
            return jsonify(cosponsor_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/network/cosponsorship')
def get_cosponsorship_network():
    """Get co-sponsorship network data for visualization."""
    try:
        with get_db_session() as session:
            # Get all House members with their party info
            members = session.query(Member).filter(
                Member.district.isnot(None)  # House members only
            ).all()
            
            # Count bills sponsored by each member
            member_bill_counts = {}
            for member in members:
                bill_count = session.query(Bill).filter(
                    Bill.sponsor_bioguide == member.member_id_bioguide,
                    Bill.chamber == 'house'
                ).count()
                member_bill_counts[member.member_id_bioguide] = bill_count
            
            # Create nodes (members)
            nodes = []
            for member in members:
                # Determine color based on party
                color = '#1f77b4' if member.party == 'D' else '#d62728' if member.party == 'R' else '#ff7f0e'
                
                nodes.append({
                    'id': member.member_id_bioguide,
                    'label': f"{member.first} {member.last}",
                    'party': member.party,
                    'state': member.state,
                    'district': member.district,
                    'color': color,
                    'bills_sponsored': member_bill_counts[member.member_id_bioguide]
                })
            
            # Get all co-sponsorship relationships with bill details
            cosponsorships = session.query(Cosponsor, Bill).join(
                Bill, Cosponsor.bill_id == Bill.bill_id
            ).filter(
                Bill.chamber == 'house'
            ).all()
            
            # Create links with detailed information
            links = []
            for cosponsor, bill in cosponsorships:
                if cosponsor.member_id_bioguide != bill.sponsor_bioguide:
                    links.append({
                        'source': bill.sponsor_bioguide,
                        'target': cosponsor.member_id_bioguide,
                        'bill_id': bill.bill_id,
                        'bill_title': bill.title or f"{bill.type.upper()} {bill.number}",
                        'cosponsor_date': cosponsor.date.isoformat() if cosponsor.date else None
                    })
            
            return jsonify({
                'nodes': nodes,
                'links': links
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/network/cosponsorship/simplified')
def get_simplified_cosponsorship_network():
    """Get simplified co-sponsorship network data with filtering options."""
    try:
        # Get query parameters for filtering
        min_relationships = int(request.args.get('min_relationships', 3))
        min_bills_sponsored = int(request.args.get('min_bills_sponsored', 1))
        max_edges_per_node = int(request.args.get('max_edges_per_node', 20))
        party_filter = request.args.get('party', None)
        
        print(f"DEBUG: Received params - min_relationships={min_relationships}, min_bills_sponsored={min_bills_sponsored}, max_edges_per_node={max_edges_per_node}, party_filter={party_filter}")
        
        with get_db_session() as session:
            # Get House members with filtering
            member_query = session.query(Member).filter(
                Member.district.isnot(None)  # House members only
            )
            
            if party_filter:
                member_query = member_query.filter(Member.party == party_filter)
            
            members = member_query.all()
            
            # Count bills sponsored by each member
            member_bill_counts = {}
            for member in members:
                bill_count = session.query(Bill).filter(
                    Bill.sponsor_bioguide == member.member_id_bioguide,
                    Bill.chamber == 'house'
                ).count()
                member_bill_counts[member.member_id_bioguide] = bill_count
            
            # Filter members by minimum bills sponsored
            active_members = [m for m in members if member_bill_counts[m.member_id_bioguide] >= min_bills_sponsored]
            
            # Create nodes (only active members)
            nodes = []
            for member in active_members:
                # Determine color based on party
                color = '#1f77b4' if member.party == 'D' else '#d62728' if member.party == 'R' else '#ff7f0e'
                
                nodes.append({
                    'id': member.member_id_bioguide,
                    'label': f"{member.first} {member.last}",
                    'party': member.party,
                    'state': member.state,
                    'district': member.district,
                    'color': color,
                    'bills_sponsored': member_bill_counts[member.member_id_bioguide]
                })
            
            # Get co-sponsorship relationships only for active members
            active_member_ids = {m.member_id_bioguide for m in active_members}
            
            cosponsorships = session.query(Cosponsor, Bill).join(
                Bill, Cosponsor.bill_id == Bill.bill_id
            ).filter(
                Bill.chamber == 'house',
                Bill.sponsor_bioguide.in_(active_member_ids),
                Cosponsor.member_id_bioguide.in_(active_member_ids)
            ).all()
            
            # Group by sponsor -> cosponsor relationships (bidirectional)
            edges = {}
            for cosponsor, bill in cosponsorships:
                if bill.sponsor_bioguide != cosponsor.member_id_bioguide:
                    # Create edge key for this specific direction
                    edge_key = f"{bill.sponsor_bioguide}->{cosponsor.member_id_bioguide}"
                    
                    if edge_key not in edges:
                        edges[edge_key] = {
                            'source': bill.sponsor_bioguide,
                            'target': cosponsor.member_id_bioguide,
                            'bills': []
                        }
                    
                    edges[edge_key]['bills'].append({
                        'bill_id': bill.bill_id,
                        'bill_title': bill.title or f"{bill.type.upper()} {bill.number}",
                        'cosponsor_date': cosponsor.date.isoformat() if cosponsor.date else None
                    })
            
            # Filter edges by minimum relationships and limit per node
            links = []
            node_edge_counts = {}
            
            print(f"DEBUG: Total edges before filtering: {len(edges)}")
            
            # Sort edges by weight (number of bills) to prioritize stronger relationships
            sorted_edges = sorted(edges.items(), key=lambda x: len(x[1]['bills']), reverse=True)
            
            for edge_key, edge_data in sorted_edges:
                relationship_count = len(edge_data['bills'])
                
                # Skip if below minimum threshold
                if relationship_count < min_relationships:
                    continue
                
                # Check edge count limits for both nodes
                source_node = edge_data['source']
                target_node = edge_data['target']
                
                if (node_edge_counts.get(source_node, 0) >= max_edges_per_node or 
                    node_edge_counts.get(target_node, 0) >= max_edges_per_node):
                    continue
                
                # Add the edge with all bills in the relationship
                first_bill = edge_data['bills'][0]  # Get the first bill for basic info
                links.append({
                    'source': source_node,
                    'target': target_node,
                    'bill_id': first_bill['bill_id'],
                    'bill_title': first_bill['bill_title'],
                    'cosponsor_date': first_bill['cosponsor_date'],
                    'all_bills': edge_data['bills']  # Include all bills for tooltip
                })
                
                # Update edge counts
                node_edge_counts[source_node] = node_edge_counts.get(source_node, 0) + 1
                node_edge_counts[target_node] = node_edge_counts.get(target_node, 0) + 1
            
            print(f"DEBUG: Final results - nodes: {len(nodes)}, links: {len(links)}")
            
            return jsonify({
                'nodes': nodes,
                'links': links
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/network')
def network_page():
    """Network visualization page."""
    return render_template('network.html')

@app.route('/network/simplified')
def simplified_network_page():
    """Simplified network visualization page."""
    return render_template('network_simplified.html')

@app.route('/network/member/<bioguide_id>')
def member_network_page(bioguide_id):
    """Member-specific network visualization page."""
    return render_template('member_network.html', bioguide_id=bioguide_id)

@app.route('/api/network/member/<bioguide_id>')
def get_member_network(bioguide_id):
    """Get network data for a specific member with only distance-1 relationships."""
    try:
        with get_db_session() as session:
            # Get the target member
            target_member = session.query(Member).filter(
                Member.member_id_bioguide == bioguide_id
            ).first()
            
            if not target_member:
                return jsonify({'error': 'Member not found'}), 404
            
            # Get all co-sponsorships involving this member
            cosponsorships = session.query(Cosponsor, Bill).join(Bill).filter(
                or_(
                    Cosponsor.member_id_bioguide == bioguide_id,  # Member is co-sponsor
                    Bill.sponsor_bioguide == bioguide_id  # Member is sponsor
                )
            ).all()
            
            # Collect all unique member IDs involved
            member_ids = {bioguide_id}  # Include the target member
            
            # Get all relationships involving the target member
            edges = {}
            for cosponsor, bill in cosponsorships:
                if bill.sponsor_bioguide != cosponsor.member_id_bioguide:
                    # Add both members to the set
                    member_ids.add(bill.sponsor_bioguide)
                    member_ids.add(cosponsor.member_id_bioguide)
                    
                    # Create edge key
                    edge_key = f"{bill.sponsor_bioguide}->{cosponsor.member_id_bioguide}"
                    
                    if edge_key not in edges:
                        edges[edge_key] = {
                            'source': bill.sponsor_bioguide,
                            'target': cosponsor.member_id_bioguide,
                            'bills': []
                        }
                    
                    edges[edge_key]['bills'].append({
                        'bill_id': bill.bill_id,
                        'bill_title': bill.title or f"{bill.type.upper()} {bill.number}",
                        'cosponsor_date': cosponsor.date.isoformat() if cosponsor.date else None
                    })
            
            # Get all members involved
            members = session.query(Member).filter(
                Member.member_id_bioguide.in_(member_ids)
            ).all()
            
            # Create nodes
            nodes = []
            for member in members:
                # Count bills sponsored by this member
                bills_sponsored = session.query(Bill).filter(
                    Bill.sponsor_bioguide == member.member_id_bioguide
                ).count()
                
                # Determine node color based on party
                color = '#1f77b4'  # Default blue (Democrat)
                if member.party == 'Republican' or member.party == 'R':
                    color = '#d62728'  # Red
                elif member.party == 'Independent' or member.party == 'I':
                    color = '#ff7f0e'  # Orange
                
                # Debug: print party info
                print(f"DEBUG: Member {member.first} {member.last} - Party: '{member.party}' - Color: {color}")
                
                nodes.append({
                    'id': member.member_id_bioguide,
                    'label': f"{member.first} {member.last}",
                    'party': member.party,
                    'state': member.state,
                    'district': member.district,
                    'color': color,
                    'bills_sponsored': bills_sponsored,
                    'is_target': member.member_id_bioguide == bioguide_id
                })
            
            # Create links
            links = []
            for edge_key, edge_data in edges.items():
                first_bill = edge_data['bills'][0]
                links.append({
                    'source': edge_data['source'],
                    'target': edge_data['target'],
                    'bill_id': first_bill['bill_id'],
                    'bill_title': first_bill['bill_title'],
                    'cosponsor_date': first_bill['cosponsor_date'],
                    'all_bills': edge_data['bills']
                })
            
            return jsonify({
                'nodes': nodes,
                'links': links,
                'target_member': {
                    'id': target_member.member_id_bioguide,
                    'name': f"{target_member.first} {target_member.last}",
                    'party': target_member.party,
                    'state': target_member.state,
                    'district': target_member.district
                }
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/member/<bioguide_id>')
def member_details_page(bioguide_id):
    """Member details page."""
    return render_template('member.html', bioguide_id=bioguide_id)


@app.route('/api/member/<bioguide_id>')
def get_member_details(bioguide_id):
    """Get detailed information for a specific member."""
    app.logger.info(f"DEBUG: get_member_details called for bioguide_id: {bioguide_id}")
    try:
        # Load caucus data
        caucus_data = load_caucus_data()
        
        with get_db_session() as session:
            # Get member basic info
            member = session.query(Member).filter(Member.member_id_bioguide == bioguide_id).first()
            app.logger.info(f"DEBUG: Member query result: {member.member_id_bioguide if member else 'None'}")
            if not member:
                return jsonify({'error': 'Member not found'}), 404
            
            # Get voting statistics
            total_votes = session.query(Vote).filter(Vote.member_id_bioguide == bioguide_id).count()
            yea_votes = session.query(Vote).filter(
                Vote.member_id_bioguide == bioguide_id,
                Vote.vote_code == 'Yea'
            ).count()
            nay_votes = session.query(Vote).filter(
                Vote.member_id_bioguide == bioguide_id,
                Vote.vote_code == 'Nay'
            ).count()
            present_votes = session.query(Vote).filter(
                Vote.member_id_bioguide == bioguide_id,
                Vote.vote_code == 'Present'
            ).count()
            
            # Get sponsored bills
            sponsored_bills = session.query(Bill).filter(Bill.sponsor_bioguide == bioguide_id).all()
            sponsored_bills_data = []
            for bill in sponsored_bills:
                sponsored_bills_data.append({
                    'bill_id': bill.bill_id,
                    'title': bill.title,
                    'type': bill.type.upper(),
                    'number': bill.number,
                    'introduced_date': bill.introduced_date.isoformat() if bill.introduced_date else None
                })
            
            # Get cosponsored bills
            cosponsored_bills = session.query(Cosponsor).filter(Cosponsor.member_id_bioguide == bioguide_id).all()
            cosponsored_bills_data = []
            for cosponsor in cosponsored_bills:
                bill = session.query(Bill).filter(Bill.bill_id == cosponsor.bill_id).first()
                if bill:
                    cosponsored_bills_data.append({
                        'bill_id': bill.bill_id,
                        'title': bill.title,
                        'type': bill.type.upper(),
                        'number': bill.number,
                        'date': cosponsor.date.isoformat() if cosponsor.date else None,
                        'is_original': cosponsor.is_original
                    })
            
            # Get recent votes (last 20)
            recent_votes = session.query(Vote).filter(
                Vote.member_id_bioguide == bioguide_id
            ).join(Rollcall).order_by(Rollcall.date.desc()).limit(20).all()
            
            # Get ideological profile from cache (fast)
            app.logger.info(f"DEBUG: About to call get_member_ideology_fast for {member.member_id_bioguide}")
            try:
                ideological_data = get_member_ideology_fast(member.member_id_bioguide, congress=119, chamber='house')
                app.logger.info(f"DEBUG: Successfully got ideological data for {member.member_id_bioguide}")
                app.logger.info(f"DEBUG: Raw ideological_data: {ideological_data}")
            except Exception as e:
                app.logger.error(f"DEBUG: Error getting ideological data for {member.member_id_bioguide}: {e}")
                ideological_data = {}
            
            # Debug: Log what we're getting from cache
            app.logger.info(f"DEBUG: Member {member.member_id_bioguide} ideological data from cache:")
            app.logger.info(f"  Party Line: {ideological_data.get('party_line_percentage', 'N/A')}%")
            app.logger.info(f"  Cross-Party: {ideological_data.get('cross_party_percentage', 'N/A')}%")
            app.logger.info(f"  Labels: {ideological_data.get('labels', 'N/A')}")
            app.logger.info(f"  Full ideological_data keys: {list(ideological_data.keys()) if isinstance(ideological_data, dict) else 'Not a dict'}")
            
            recent_votes_data = []
            for vote in recent_votes:
                rollcall = session.query(Rollcall).filter(Rollcall.rollcall_id == vote.rollcall_id).first()
                if rollcall:
                    # Get bill title if bill_id exists
                    bill_title = None
                    if rollcall.bill_id:
                        bill = session.query(Bill).filter(Bill.bill_id == rollcall.bill_id).first()
                        if bill:
                            bill_title = bill.title
                    
                    recent_votes_data.append({
                        'rollcall_id': vote.rollcall_id,
                        'vote_code': vote.vote_code,
                        'question': rollcall.question,
                        'date': rollcall.date.isoformat() if rollcall.date else None,
                        'bill_id': rollcall.bill_id,
                        'bill_title': bill_title
                    })
            
            # Check caucus memberships
            is_freedom_caucus = member.member_id_bioguide in caucus_data['freedom_caucus']
            is_progressive_caucus = member.member_id_bioguide in caucus_data['progressive_caucus']
            is_blue_dog_coalition = member.member_id_bioguide in caucus_data['blue_dog_coalition']
            is_maga_republican = member.member_id_bioguide in caucus_data['maga_republicans']
            is_congressional_black_caucus = member.member_id_bioguide in caucus_data['congressional_black_caucus']
            is_true_blue_democrat = member.member_id_bioguide in caucus_data['true_blue_democrats']
            
            return jsonify({
                'member': {
                    'id': member.member_id_bioguide,
                    'name': f"{member.first} {member.last}",
                    'first': member.first,
                    'last': member.last,
                    'party': member.party,
                    'state': member.state,
                    'district': member.district,
                    'chamber': 'House' if member.district else 'Senate',
                    'start_date': member.start_date.isoformat() if member.start_date else None,
                    'is_freedom_caucus': is_freedom_caucus,
                    'is_progressive_caucus': is_progressive_caucus,
                    'is_blue_dog_coalition': is_blue_dog_coalition,
                    'is_maga_republican': is_maga_republican,
                    'is_congressional_black_caucus': is_congressional_black_caucus,
                    'is_true_blue_democrat': is_true_blue_democrat
                },
                'voting_stats': {
                    'total_votes': total_votes,
                    'yea_votes': yea_votes,
                    'nay_votes': nay_votes,
                    'present_votes': present_votes,
                    'yea_percentage': round((yea_votes / total_votes * 100), 1) if total_votes > 0 else 0,
                    'nay_percentage': round((nay_votes / total_votes * 100), 1) if total_votes > 0 else 0
                },
                'sponsored_bills': sponsored_bills_data,
                'cosponsored_bills': cosponsored_bills_data,
                'recent_votes': recent_votes_data,
                'ideological_profile': ideological_data
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/vote/<rollcall_id>')
def vote_details_page(rollcall_id):
    """Render a page showing bill/amendment details and the full vote record."""
    try:
        with get_db_session() as session:
            rc = session.query(Rollcall).filter(Rollcall.rollcall_id == rollcall_id).first()
            if not rc:
                return render_template('vote.html', error=f'Roll call {rollcall_id} not found', rollcall=None, bill=None, votes=[])
            bill = None
            if rc.bill_id:
                bill = session.query(Bill).filter(Bill.bill_id == rc.bill_id).first()
            votes = session.query(Vote).filter(Vote.rollcall_id == rollcall_id).all()
            
            # Calculate vote counts
            yea_count = len([v for v in votes if v.vote_code == 'Yea'])
            nay_count = len([v for v in votes if v.vote_code == 'Nay'])
            present_count = len([v for v in votes if v.vote_code == 'Present'])
            not_voting_count = len([v for v in votes if v.vote_code == 'Not Voting'])
            total_votes = len(votes)
            
            vote_counts = {
                'yea': yea_count,
                'nay': nay_count,
                'present': present_count,
                'not_voting': not_voting_count,
                'total': total_votes
            }
            
            # join member info
            vote_rows = []
            for v in votes:
                m = session.query(Member).filter(Member.member_id_bioguide == v.member_id_bioguide).first()
                vote_rows.append({
                    'member_id': v.member_id_bioguide,
                    'member_name': f"{m.first} {m.last}" if m else 'Unknown',
                    'party': m.party if m else None,
                    'state': m.state if m else None,
                    'vote_code': v.vote_code
                })
            return render_template('vote.html', rollcall=rc, bill=bill, votes=vote_rows, vote_counts=vote_counts)
    except Exception as e:
        print(f"/vote/<id> failed: {e}")
        return render_template('vote.html', error=str(e), rollcall=None, bill=None, votes=[])

@app.route('/bill/<bill_id>')
def bill_details_page(bill_id):
    """Render a page showing bill details, sponsor, cosponsors, related rollcalls."""
    try:
        with get_db_session() as session:
            bill = session.query(Bill).filter(Bill.bill_id == bill_id).first()
            if not bill:
                return render_template('bill.html', error=f'Bill {bill_id} not found', bill=None, sponsor=None, cosponsors=[], rollcalls=[])
            
            sponsor = session.query(Member).filter(Member.member_id_bioguide == bill.sponsor_bioguide).first()
            
            cos = session.query(Cosponsor).filter(Cosponsor.bill_id == bill_id).all()
            cos_rows = []
            for c in cos:
                m = session.query(Member).filter(Member.member_id_bioguide == c.member_id_bioguide).first()
                cos_rows.append({
                    'member_id': c.member_id_bioguide,
                    'member_name': f"{m.first} {m.last}" if m else 'Unknown',
                    'party': m.party if m else None,
                    'state': m.state if m else None,
                    'date': c.date,
                    'is_original': c.is_original
                })
            
            rcs = session.query(Rollcall).filter(Rollcall.bill_id == bill_id).all()
            print(f"Bill {bill_id}: found {len(rcs)} roll calls")
            
            return render_template('bill.html', bill=bill, sponsor=sponsor, cosponsors=cos_rows, rollcalls=rcs)
    except Exception as e:
        print(f"/bill/<id> failed: {e}")
        return render_template('bill.html', error=str(e), bill=None, sponsor=None, cosponsors=[], rollcalls=[])

# Caucus Management Routes
@app.route('/caucus-management')
def caucus_management_page():
    """Render the caucus management page."""
    return render_template('caucus_management.html')

@app.route('/api/caucuses')
def get_caucuses():
    """Get all caucuses."""
    try:
        with get_db_session() as session:
            caucuses = session.query(Caucus).filter(Caucus.is_active == True).all()
            caucus_data = []
            
            for caucus in caucuses:
                member_count = session.query(CaucusMembership).filter(
                    CaucusMembership.caucus_id == caucus.id,
                    CaucusMembership.end_date.is_(None)
                ).count()
                
                caucus_data.append({
                    'id': caucus.id,
                    'name': caucus.name,
                    'short_name': caucus.short_name,
                    'description': caucus.description,
                    'color': caucus.color,
                    'icon': caucus.icon,
                    'member_count': member_count
                })
            
            return jsonify(caucus_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/caucuses/<int:caucus_id>')
def get_caucus(caucus_id):
    """Get a specific caucus by ID."""
    try:
        with get_db_session() as session:
            caucus = session.query(Caucus).filter(Caucus.id == caucus_id).first()
            if not caucus:
                return jsonify({'error': 'Caucus not found'}), 404
            
            member_count = session.query(CaucusMembership).filter(
                CaucusMembership.caucus_id == caucus.id,
                CaucusMembership.end_date.is_(None)
            ).count()
            
            return jsonify({
                'id': caucus.id,
                'name': caucus.name,
                'short_name': caucus.short_name,
                'description': caucus.description,
                'color': caucus.color,
                'icon': caucus.icon,
                'member_count': member_count
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/caucuses/<int:caucus_id>/members')
def get_caucus_members(caucus_id):
    """Get all members of a specific caucus."""
    try:
        with get_db_session() as session:
            memberships = session.query(CaucusMembership).join(Member).filter(
                CaucusMembership.caucus_id == caucus_id,
                CaucusMembership.end_date.is_(None)
            ).all()
            
            member_data = []
            for membership in memberships:
                member_data.append({
                    'id': membership.id,
                    'member_id_bioguide': membership.member_id_bioguide,
                    'member_name': f"{membership.member.first} {membership.member.last}",
                    'party': membership.member.party,
                    'state': membership.member.state,
                    'district': membership.member.district,
                    'start_date': membership.start_date.isoformat() if membership.start_date else None,
                    'notes': membership.notes
                })
            
            # Sort caucus members by last name, then first name
            member_data.sort(key=lambda x: (x['member_name'].split()[-1], x['member_name'].split()[0]))
            
            return jsonify(member_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/caucus-memberships', methods=['POST'])
def create_caucus_membership():
    """Create a new caucus membership."""
    try:
        data = request.get_json()
        member_id_bioguide = data.get('member_id_bioguide')
        caucus_id = data.get('caucus_id')
        start_date = data.get('start_date')
        notes = data.get('notes')
        
        if not all([member_id_bioguide, caucus_id]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        with get_db_session() as session:
            # Check if membership already exists
            existing = session.query(CaucusMembership).filter(
                CaucusMembership.member_id_bioguide == member_id_bioguide,
                CaucusMembership.caucus_id == caucus_id,
                CaucusMembership.end_date.is_(None)
            ).first()
            
            if existing:
                return jsonify({'error': 'Member is already in this caucus'}), 400
            
            # Create new membership
            start_date_obj = None
            if start_date:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            
            membership = CaucusMembership(
                member_id_bioguide=member_id_bioguide,
                caucus_id=caucus_id,
                start_date=start_date_obj,
                notes=notes
            )
            
            session.add(membership)
            session.commit()
            
            return jsonify({'message': 'Membership created successfully', 'id': membership.id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/caucus-memberships/<int:membership_id>', methods=['DELETE'])
def delete_caucus_membership(membership_id):
    """Delete a caucus membership (set end date to today)."""
    try:
        with get_db_session() as session:
            membership = session.query(CaucusMembership).filter(CaucusMembership.id == membership_id).first()
            if not membership:
                return jsonify({'error': 'Membership not found'}), 404
            
            membership.end_date = date.today()
            session.commit()
            
            return jsonify({'message': 'Membership ended successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
