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
from scripts.simple_house_analysis import run_simple_house_analysis

app = Flask(__name__)
CORS(app)

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
        with get_db_session() as session:
            # Filter for House members only (those with districts)
            members = session.query(Member).filter(Member.district.isnot(None)).all()
            member_data = []
            
            for member in members:
                # Get voting statistics
                vote_count = session.query(Vote).filter(Vote.member_id_bioguide == member.member_id_bioguide).count()
                
                # Get cosponsorship count
                cosponsor_count = session.query(Cosponsor).filter(Cosponsor.member_id_bioguide == member.member_id_bioguide).count()
                
                member_data.append({
                    'id': member.member_id_bioguide,
                    'name': f"{member.first} {member.last}",
                    'party': member.party,
                    'state': member.state,
                    'district': member.district,
                    'chamber': 'House',
                    'vote_count': vote_count,
                    'cosponsor_count': cosponsor_count,
                    'start_date': member.start_date.isoformat() if member.start_date else None
                })
            
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
            
            # Create nodes (members)
            nodes = []
            for member in members:
                # Determine color based on party
                color = '#0066cc' if member.party == 'D' else '#cc0000' if member.party == 'R' else '#666666'
                
                nodes.append({
                    'id': member.member_id_bioguide,
                    'label': f"{member.first} {member.last}",
                    'party': member.party,
                    'state': member.state,
                    'district': member.district,
                    'color': color,
                    'title': f"{member.first} {member.last} ({member.party}-{member.state}-{member.district})"
                })
            
            # Get all co-sponsorship relationships
            cosponsorships = session.query(Cosponsor, Bill).join(
                Bill, Cosponsor.bill_id == Bill.bill_id
            ).filter(
                Bill.chamber == 'house'
            ).all()
            
            # Group by sponsor -> cosponsor relationships
            edges = {}
            for cosponsor, bill in cosponsorships:
                # Get the sponsor of this bill
                sponsor = session.query(Member).filter(
                    Member.member_id_bioguide == bill.sponsor_bioguide
                ).first()
                
                if sponsor and cosponsor.member_id_bioguide != bill.sponsor_bioguide:
                    # Create edge key: sponsor -> cosponsor
                    edge_key = f"{bill.sponsor_bioguide}->{cosponsor.member_id_bioguide}"
                    
                    if edge_key not in edges:
                        edges[edge_key] = {
                            'from': bill.sponsor_bioguide,
                            'to': cosponsor.member_id_bioguide,
                            'bills': []
                        }
                    
                    edges[edge_key]['bills'].append({
                        'bill_id': bill.bill_id,
                        'title': bill.title or f"{bill.type.upper()} {bill.number}"
                    })
            
            # Convert edges to list format
            edges_list = []
            for edge_key, edge_data in edges.items():
                # Create tooltip with bill details
                bill_tooltip = "<br>".join([
                    f"{bill['bill_id']}: {bill['title']}" 
                    for bill in edge_data['bills']
                ])
                
                edges_list.append({
                    'from': edge_data['from'],
                    'to': edge_data['to'],
                    'title': bill_tooltip,
                    'value': len(edge_data['bills'])  # Edge weight based on number of bills
                })
            
            return jsonify({
                'nodes': nodes,
                'edges': edges_list
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/network/cosponsorship/simplified')
def get_simplified_cosponsorship_network():
    """Get simplified co-sponsorship network data with filtering options."""
    try:
        # Get query parameters for filtering
        min_relationships = int(request.args.get('min_relationships', 3))  # Minimum co-sponsorships to show edge
        min_bills_sponsored = int(request.args.get('min_bills_sponsored', 1))  # Minimum bills sponsored to include member
        max_edges_per_node = int(request.args.get('max_edges_per_node', 20))  # Max edges per node to prevent cluttering
        party_filter = request.args.get('party', None)  # Filter by party (D, R, or None for all)
        
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
                color = '#0066cc' if member.party == 'D' else '#cc0000' if member.party == 'R' else '#666666'
                
                nodes.append({
                    'id': member.member_id_bioguide,
                    'label': f"{member.first} {member.last}",
                    'party': member.party,
                    'state': member.state,
                    'district': member.district,
                    'color': color,
                    'title': f"{member.first} {member.last} ({member.party}-{member.state}-{member.district}) - {member_bill_counts[member.member_id_bioguide]} bills sponsored",
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
            
            # Group by sponsor -> cosponsor relationships
            edges = {}
            for cosponsor, bill in cosponsorships:
                if bill.sponsor_bioguide != cosponsor.member_id_bioguide:
                    edge_key = f"{bill.sponsor_bioguide}->{cosponsor.member_id_bioguide}"
                    
                    if edge_key not in edges:
                        edges[edge_key] = {
                            'from': bill.sponsor_bioguide,
                            'to': cosponsor.member_id_bioguide,
                            'bills': []
                        }
                    
                    edges[edge_key]['bills'].append({
                        'bill_id': bill.bill_id,
                        'title': bill.title or f"{bill.type.upper()} {bill.number}"
                    })
            
            # Filter edges by minimum relationships and limit per node
            edges_list = []
            node_edge_counts = {}
            
            # Sort edges by weight (number of bills) to prioritize stronger relationships
            sorted_edges = sorted(edges.items(), key=lambda x: len(x[1]['bills']), reverse=True)
            
            for edge_key, edge_data in sorted_edges:
                relationship_count = len(edge_data['bills'])
                
                # Skip if below minimum threshold
                if relationship_count < min_relationships:
                    continue
                
                # Check edge count limits for both nodes
                from_node = edge_data['from']
                to_node = edge_data['to']
                
                if (node_edge_counts.get(from_node, 0) >= max_edges_per_node or 
                    node_edge_counts.get(to_node, 0) >= max_edges_per_node):
                    continue
                
                # Create tooltip with bill details (limit to first 5 for readability)
                bill_tooltip = "<br>".join([
                    f"{bill['bill_id']}: {bill['title']}" 
                    for bill in edge_data['bills'][:5]
                ])
                if len(edge_data['bills']) > 5:
                    bill_tooltip += f"<br>... and {len(edge_data['bills']) - 5} more"
                
                edges_list.append({
                    'from': from_node,
                    'to': to_node,
                    'title': bill_tooltip,
                    'value': relationship_count
                })
                
                # Update edge counts
                node_edge_counts[from_node] = node_edge_counts.get(from_node, 0) + 1
                node_edge_counts[to_node] = node_edge_counts.get(to_node, 0) + 1
            
            return jsonify({
                'nodes': nodes,
                'edges': edges_list,
                'filters': {
                    'min_relationships': min_relationships,
                    'min_bills_sponsored': min_bills_sponsored,
                    'max_edges_per_node': max_edges_per_node,
                    'party_filter': party_filter
                },
                'stats': {
                    'total_members': len(members),
                    'active_members': len(nodes),
                    'total_edges': len(edges),
                    'filtered_edges': len(edges_list)
                }
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

@app.route('/member/<bioguide_id>')
def member_details_page(bioguide_id):
    """Member details page."""
    return render_template('member.html', bioguide_id=bioguide_id)


@app.route('/api/member/<bioguide_id>')
def get_member_details(bioguide_id):
    """Get detailed information for a specific member."""
    try:
        with get_db_session() as session:
            # Get member basic info
            member = session.query(Member).filter(Member.member_id_bioguide == bioguide_id).first()
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
                    'start_date': member.start_date.isoformat() if member.start_date else None
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
                'recent_votes': recent_votes_data
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
