
#!/usr/bin/env python3
"""
Flask web application for Congressional Coalition Analysis.
"""

import os
import sys
import json
import unicodedata
import requests
from datetime import datetime, date
from flask import Flask, render_template, jsonify, request, send_file, Response
from flask_cors import CORS
from flask_caching import Cache
from io import BytesIO
import re # Added for markdown conversion

# Development mode check
DEV_MODE = os.environ.get('DEV_MODE', 'false').lower() == 'true'

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.database import get_db_session
from scripts.setup_db import Member, Bill, Rollcall, Vote, Cosponsor, Action, BillSubject
from scripts.setup_caucus_tables import Caucus, CaucusMembership
from sqlalchemy import or_, and_, text
from scripts.simple_house_analysis import run_simple_house_analysis
from scripts.ideological_labeling import calculate_voting_ideology_scores_fast, assign_ideological_labels
from scripts.precalculate_ideology import get_member_ideology_fast
import numpy as np
from collections import defaultdict
try:
    from sklearn.decomposition import TruncatedSVD
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score
    _SKLEARN_AVAILABLE = True
except Exception:
    _SKLEARN_AVAILABLE = False

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
            
            # Load True Blue Democrats members (short_name 'TB' in defaults; also match by full name)
            true_blue_democrats_members = session.query(CaucusMembership).join(Caucus).filter(
                or_(Caucus.short_name == 'TB', Caucus.name == 'True Blue Democrats'),
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

# Configure caching
cache_config = {
    'CACHE_TYPE': 'filesystem',  # File-based cache for persistence across restarts
    'CACHE_DIR': '/tmp/congressional_cache',  # Cache directory
    'CACHE_DEFAULT_TIMEOUT': 300  # 5 minutes default timeout
}
app.config.update(cache_config)
cache = Cache(app)

def normalize_for_sorting(text):
    """Remove accents and diacritics from text for consistent alphabetical sorting."""
    # Normalize unicode characters (NFD = Canonical Decomposition)
    normalized = unicodedata.normalize('NFD', text)
    # Filter out diacritical marks (category 'Mn')
    without_accents = ''.join(char for char in normalized if unicodedata.category(char) != 'Mn')
    return without_accents

# Note: Ideological profiles are now pre-calculated and cached for performance.
# See scripts/precalcul
# ate_ideology.py for the calculation logic.

# Set database URL

os.environ['DATABASE_URL'] = 'mysql://congressional:congressional123@localhost/congressional_coalitions'

@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('index.html', dev_mode=DEV_MODE)

@app.route('/api/summary')
def get_summary():
    """Get House-only database summary statistics for current Congress period."""
    try:
        with get_db_session() as session:
            # Calculate time period since 119th Congress started (January 3, 2025)
            from datetime import date
            congress_start = date(2025, 1, 3)
            today = date.today()
            days_since_start = (today - congress_start).days + 1
            
            # House-only counts (members count is not time-filtered as it represents current membership)
            member_count = session.query(Member).filter(Member.district.isnot(None)).count()
            
            # Bills introduced since Congress start
            bill_count = session.query(Bill).filter(
                Bill.chamber == 'house',
                Bill.introduced_date >= congress_start
            ).count()
            
            # Roll calls since Congress start
            rollcall_count = session.query(Rollcall).filter(
                Rollcall.chamber == 'house',
                Rollcall.date >= congress_start
            ).count()
            
            # Votes cast since Congress start
            vote_count = session.query(Vote).join(Rollcall).filter(
                Rollcall.chamber == 'house',
                Rollcall.date >= congress_start
            ).count()
            
            # Cosponsorships since Congress start
            cosponsor_count = session.query(Cosponsor).join(Bill).filter(
                Bill.chamber == 'house',
                Bill.introduced_date >= congress_start
            ).count()
            
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
                'time_period': {
                    'start_date': congress_start.isoformat(),
                    'end_date': today.isoformat(),
                    'days_covered': days_since_start,
                    'description': f'119th Congress (since {congress_start.strftime("%B %d, %Y")})'
                },
                'note': f'House-only data since 119th Congress start ({days_since_start} days)'
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/svd/components')
def api_svd_components():
    """Return summaries to help characterize SVD axes (components).

    Params: dims (default 3), congress (119), chamber (house), rc_limit (optional),
    min_votes (default 5), exclude_procedural (default true), scope, subject.
    """
    if not _SKLEARN_AVAILABLE:
        return jsonify({'error': 'scikit-learn not available in this runtime'}), 500
    try:
        dims = int(request.args.get('dims', 3))
        congress = int(request.args.get('congress', 119))
        chamber = request.args.get('chamber', 'house')
        rc_limit_param = request.args.get('rc_limit')
        rc_limit = int(rc_limit_param) if rc_limit_param is not None else None
        min_votes = int(request.args.get('min_votes', 5))
        exclude_procedural = _is_truthy(request.args.get('exclude_procedural', 'true'))
        scope = request.args.get('scope')
        subject_param = request.args.get('subject')
        subjects = [s.strip() for s in subject_param.split(',')] if subject_param else []

        with get_db_session() as session:
            # Rollcalls + bill meta
            rc_q = (
                session.query(
                    Rollcall.rollcall_id,
                    Rollcall.date,
                    Rollcall.question,
                    Rollcall.bill_id,
                    Bill.title,
                    Bill.policy_area,
                )
                .join(Bill, Rollcall.bill_id == Bill.bill_id)
                .filter(Rollcall.congress == congress, Rollcall.chamber == chamber)
                .filter(Bill.congress == congress, Bill.chamber == chamber)
                .filter(Bill.bill_id.like(f"%-{congress}"))
            )
            if subjects and scope in ('policy_area', 'subject_term'):
                if scope == 'policy_area':
                    rc_q = rc_q.filter(Bill.policy_area.in_(subjects))
                else:
                    rc_q = rc_q.join(BillSubject, BillSubject.bill_id == Bill.bill_id).filter(BillSubject.subject_term.in_(subjects))
            rc_q = rc_q.order_by(Rollcall.date.desc())
            if rc_limit:
                rc_q = rc_q.limit(rc_limit)
            rc_rows = rc_q.all()
            if not rc_rows:
                return jsonify({'error': 'No roll calls found for scope'}), 404
            rc_ids_all = [r.rollcall_id for r in rc_rows]
            rc_meta = {r.rollcall_id: {
                'rollcall_id': r.rollcall_id,
                'date': r.date.isoformat() if r.date else None,
                'question': r.question,
                'bill_id': r.bill_id,
                'title': r.title,
                'policy_area': r.policy_area,
            } for r in rc_rows}

            # Preload subject terms for these bills
            bill_ids_for_subjects = [m['bill_id'] for m in rc_meta.values() if m.get('bill_id')]
            subj_rows = []
            subj_map = {}
            if bill_ids_for_subjects:
                subj_rows = session.query(BillSubject.bill_id, BillSubject.subject_term) \
                                  .filter(BillSubject.bill_id.in_(bill_ids_for_subjects)).all()
                for b_id, term in subj_rows:
                    if term:
                        subj_map.setdefault(b_id, []).append(term)

            # Votes
            vq = session.query(Vote.rollcall_id, Vote.member_id_bioguide, Vote.vote_code) \
                     .join(Rollcall, Vote.rollcall_id == Rollcall.rollcall_id) \
                     .join(Member, Vote.member_id_bioguide == Member.member_id_bioguide) \
                     .filter(Vote.rollcall_id.in_(rc_ids_all)) \
                     .filter(Vote.vote_code.in_(['Yea','Nay']))
            if chamber == 'house':
                vq = vq.filter(Member.district.isnot(None))
            if exclude_procedural:
                vq = vq.filter(
                    or_(
                        Rollcall.question.is_(None),
                        and_(
                            ~Rollcall.question.ilike('%rule%'),
                            ~Rollcall.question.ilike('%previous question%'),
                            ~Rollcall.question.ilike('%recommit%'),
                            ~Rollcall.question.ilike('%motion to table%'),
                            ~Rollcall.question.ilike('%quorum%'),
                            ~Rollcall.question.ilike('%adjourn%'),
                            ~Rollcall.question.ilike('%suspend the rules%')
                        )
                    )
                )
            votes_rows = vq.all()

            # Members meta for labeling
            mem_rows = session.query(Member.member_id_bioguide, Member.first, Member.last, Member.party).filter(
                Member.district.isnot(None) if chamber == 'house' else Member.district.is_(None)
            ).all()
            mem_meta = {m.member_id_bioguide: {
                'name': f"{m.first or ''} {m.last or ''}".strip(),
                'party': m.party
            } for m in mem_rows}

        # Build matrix
        rc_index = {rc_id: i for i, rc_id in enumerate(rc_ids_all)}
        member_ids = sorted({row.member_id_bioguide for row in votes_rows if row.member_id_bioguide in mem_meta})
        if not member_ids:
            return jsonify({'error': 'No member votes found'}), 404
        mem_index = {mid: i for i, mid in enumerate(member_ids)}
        M = np.zeros((len(member_ids), len(rc_ids_all)), dtype=np.float32)
        counts = np.zeros(len(member_ids), dtype=np.int32)
        for rc_id, mid, code in votes_rows:
            i = mem_index.get(mid)
            j = rc_index.get(rc_id)
            if i is None or j is None:
                continue
            M[i, j] = 1.0 if code == 'Yea' else -1.0
            counts[i] += 1
        keep = counts >= min_votes
        if not np.any(keep):
            return jsonify({'error': 'No members meet min_votes threshold'}), 400
        M = M[keep]
        kept_member_ids = [mid for mid in member_ids if keep[mem_index[mid]]]
        # Drop empty columns
        nonzero_cols_mask = (M != 0).any(axis=0)
        if not np.any(nonzero_cols_mask):
            return jsonify({'error': 'No usable roll calls after filters'}), 400
        kept_rc_ids = [rc for rc, m in zip(rc_ids_all, nonzero_cols_mask) if m]
        M = M[:, nonzero_cols_mask]
        # Center
        row_sums = M.sum(axis=1, keepdims=True)
        row_counts = (M != 0).sum(axis=1, keepdims=True)
        with np.errstate(invalid='ignore', divide='ignore'):
            row_means = np.divide(row_sums, row_counts, out=np.zeros_like(row_sums), where=row_counts!=0)
        M_centered = np.nan_to_num(M - row_means, nan=0.0)

        max_rank = int(min(M_centered.shape) - 1)
        if max_rank < 2:
            return jsonify({'error': 'Insufficient variation for SVD'}), 400
        n_comp = min(max(2, dims), min(10, max_rank))
        svd = TruncatedSVD(n_components=n_comp, random_state=42)
        Z = svd.fit_transform(M_centered)  # n_samples x n_comp
        VT = svd.components_  # n_comp x n_features (= kept rollcalls)

        # Compute member scores per component
        member_scores = Z  # rows align with kept_member_ids

        # Helper: subject enrichment for top RCs by |loading|
        def enrich_subjects(rc_list_with_w, limit=5):
            # Aggregate by policy_area and subject_term
            pos_pa, neg_pa = {}, {}
            pos_st, neg_st = {}, {}
            # Map bill_id -> subject terms
            bill_ids = list({rc_meta[rc_id]['bill_id'] for rc_id, _ in rc_list_with_w if rc_meta.get(rc_id)})
            subj_map = {}
            if bill_ids:
                with get_db_session() as session:
                    rows = session.query(BillSubject.bill_id, BillSubject.subject_term).filter(BillSubject.bill_id.in_(bill_ids)).all()
                    for b_id, term in rows:
                        if term:
                            subj_map.setdefault(b_id, []).append(term)
            for rc_id, w in rc_list_with_w:
                meta = rc_meta.get(rc_id)
                if not meta:
                    continue
                pa = meta.get('policy_area')
                terms = subj_map.get(meta.get('bill_id'), [])
                target_pa = pos_pa if w > 0 else neg_pa
                target_st = pos_st if w > 0 else neg_st
                target_pa[pa] = target_pa.get(pa, 0.0) + abs(w)
                for t in terms:
                    target_st[t] = target_st.get(t, 0.0) + abs(w)
            def topd(d):
                return [ {'name': k or '(Unknown)', 'score': round(v, 3)} for k, v in sorted(d.items(), key=lambda x: x[1], reverse=True)[:limit] ]
            return topd(pos_pa), topd(neg_pa), topd(pos_st), topd(neg_st)

        # Helper: party split for given rc ids
        def party_split_for_rc(rc_ids):
            if not rc_ids:
                return {}
            with get_db_session() as session:
                q = text("""
                    SELECT v.rollcall_id,
                           UPPER(SUBSTRING(m.party,1,1)) AS p,
                           v.vote_code,
                           COUNT(*) AS c
                    FROM votes v
                    JOIN members m ON m.member_id_bioguide = v.member_id_bioguide
                    WHERE v.rollcall_id IN :rc_ids AND v.vote_code IN ('Yea','Nay')
                    GROUP BY v.rollcall_id, p, v.vote_code
                """)
                rows = session.execute(q, {'rc_ids': tuple(rc_ids)}).fetchall()
            out = {}
            for r in rows:
                rc = r.rollcall_id
                p = r.p or ''
                code = r.vote_code
                c = int(r.c or 0)
                d = out.setdefault(rc, {'D': {'Yea':0,'Nay':0}, 'R': {'Yea':0,'Nay':0}})
                if p in d:
                    d[p][code] += c
            # Convert to percentages
            for rc, d in out.items():
                for p in ('D','R'):
                    tot = d[p]['Yea'] + d[p]['Nay']
                    if tot>0:
                        d[p]['yea_pct'] = round(100*d[p]['Yea']/tot,1)
                        d[p]['nay_pct'] = round(100*d[p]['Nay']/tot,1)
            return out

        components = []
        topN = 8
        for k in range(n_comp):
            load = VT[k]  # length = len(kept_rc_ids)
            # top pos/neg by weight
            idx_sorted_pos = np.argsort(-load)[:topN]
            idx_sorted_neg = np.argsort(load)[:topN]
            top_pos = [(kept_rc_ids[i], float(load[i])) for i in idx_sorted_pos]
            top_neg = [(kept_rc_ids[i], float(load[i])) for i in idx_sorted_neg]
            # subject enrichment
            pa_pos, pa_neg, st_pos, st_neg = enrich_subjects(top_pos+top_neg)
            # party splits
            splits = party_split_for_rc([rc for rc,_ in (top_pos+top_neg)])
            def rc_detail(lst):
                arr = []
                for rc_id, w in lst:
                    m = rc_meta.get(rc_id, {})
                    s = splits.get(rc_id, {})
                    arr.append({
                        'rollcall_id': rc_id,
                        'weight': round(w, 4),
                        'question': m.get('question'),
                        'date': m.get('date'),
                        'bill_id': m.get('bill_id'),
                        'title': m.get('title'),
                        'policy_area': m.get('policy_area'),
                        'party_split': s
                    })
                return arr
            # member extremes
            scores = member_scores[:, k]
            order_pos = np.argsort(-scores)[:topN]
            order_neg = np.argsort(scores)[:topN]
            members_pos = [{
                'id': kept_member_ids[i],
                'name': mem_meta.get(kept_member_ids[i], {}).get('name', kept_member_ids[i]),
                'party': mem_meta.get(kept_member_ids[i], {}).get('party'),
                'score': round(float(scores[i]), 4)
            } for i in order_pos]
            members_neg = [{
                'id': kept_member_ids[i],
                'name': mem_meta.get(kept_member_ids[i], {}).get('name', kept_member_ids[i]),
                'party': mem_meta.get(kept_member_ids[i], {}).get('party'),
                'score': round(float(scores[i]), 4)
            } for i in order_neg]

            components.append({
                'index': k+1,
                'top_rollcalls_pos': rc_detail(top_pos),
                'top_rollcalls_neg': rc_detail(top_neg),
                'policy_area_pos': pa_pos,
                'policy_area_neg': pa_neg,
                'subject_term_pos': st_pos,
                'subject_term_neg': st_neg,
                'members_pos': members_pos,
                'members_neg': members_neg
            })

        return jsonify({'dims': n_comp, 'components': components})
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
            
            # Sort members by last name, then first name (ignoring accents)
            member_data.sort(key=lambda x: (
                normalize_for_sorting(x['name'].split()[-1]), 
                normalize_for_sorting(x['name'].split()[0])
            ))
            
            return jsonify(member_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bills')
@cache.cached(timeout=300)  # Cache for 5 minutes
def get_bills():
    """Get House bills only with their details - optimized with caching and efficient queries."""
    try:
        with get_db_session() as session:
            # Single optimized query using JOINs to avoid N+1 problem
            from sqlalchemy import func
            
            # Subquery for cosponsor counts
            cosponsor_subquery = session.query(
                Cosponsor.bill_id,
                func.count(Cosponsor.member_id_bioguide).label('cosponsor_count')
            ).group_by(Cosponsor.bill_id).subquery()
            
            # Subquery for latest action per bill (with unique action per bill)
            latest_action_subquery = session.query(
                Action.bill_id,
                Action.action_date,
                Action.action_code,
                func.row_number().over(
                    partition_by=Action.bill_id,
                    order_by=Action.action_date.desc()
                ).label('rn')
            ).subquery()
            
            # Filter to get only the most recent action per bill
            latest_action_filtered = session.query(
                latest_action_subquery.c.bill_id,
                latest_action_subquery.c.action_date,
                latest_action_subquery.c.action_code
            ).filter(latest_action_subquery.c.rn == 1).subquery()
            
            # Main query with all JOINs
            query = session.query(
                Bill.bill_id,
                Bill.title,
                Bill.congress,
                Bill.chamber,
                Bill.number,
                Bill.type,
                Bill.introduced_date,
                Bill.sponsor_bioguide,
                Member.first,
                Member.last,
                Member.party,
                cosponsor_subquery.c.cosponsor_count,
                latest_action_filtered.c.action_date,
                latest_action_filtered.c.action_code
            ).select_from(Bill)\
            .outerjoin(Member, Bill.sponsor_bioguide == Member.member_id_bioguide)\
            .outerjoin(cosponsor_subquery, Bill.bill_id == cosponsor_subquery.c.bill_id)\
            .outerjoin(latest_action_filtered, Bill.bill_id == latest_action_filtered.c.bill_id)\
            .filter(Bill.chamber == 'house')
            
            # Execute query and build response
            bill_data = []
            for row in query.all():
                sponsor_name = f"{row.first} {row.last}" if row.first and row.last else "Unknown"
                
                bill_data.append({
                    'id': row.bill_id,
                    'title': row.title or '',
                    'congress': row.congress,
                    'chamber': row.chamber.title() if row.chamber else 'House',
                    'number': row.number,
                    'type': row.type.upper() if row.type else '',
                    'sponsor': sponsor_name,
                    'sponsor_bioguide': row.sponsor_bioguide,
                    'sponsor_party': row.party,
                    'cosponsor_count': row.cosponsor_count or 0,
                    'introduced_date': row.introduced_date.isoformat() if row.introduced_date else None,
                    'last_action_date': row.action_date.isoformat() if row.action_date else None,
                    'last_action_code': row.action_code
                })
            
            # Sort bills by last action date descending (most recent first), then by bill number descending
            def sort_key(bill):
                date_str = bill.get('last_action_date') or '1900-01-01'
                bill_id = bill.get('id', '')
                
                # Extract bill number safely
                bill_num = 0
                if '-' in bill_id:
                    parts = bill_id.split('-')
                    if len(parts) > 1 and parts[1].isdigit():
                        bill_num = int(parts[1])
                
                # Return tuple for sorting: (date_for_comparison, bill_number_for_comparison)
                # We want both descending, so we'll use reverse=True and structure accordingly
                return (date_str, bill_num)
            
            # Sort with reverse=True to get both date and bill number in descending order
            bill_data.sort(key=sort_key, reverse=True)
            
            # Add cache metadata
            response_data = {
                'bills': bill_data,
                'cached': True,  # This will be False on first load, True on cached loads
                'count': len(bill_data),
                'cache_time': datetime.now().isoformat()
            }
            
            return jsonify(response_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cache/clear')
def clear_cache():
    """Clear all cached data - useful after data updates."""
    try:
        cache.clear()
        return jsonify({'message': 'Cache cleared successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/member-image/<member_id>')
@cache.cached(timeout=3600)  # Cache for 1 hour
def get_member_image(member_id):
    """Get member image with server-side caching and fallback to SVG avatar."""
    try:
        # Construct Congress.gov image URL
        congress_url = f"https://www.congress.gov/img/member/{member_id.lower()}_200.jpg"
        
        # Try to fetch the image with a proper User-Agent header
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.congress.gov/',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
        }
        
        response = requests.get(congress_url, headers=headers, timeout=10)
        
        if response.status_code == 200 and 'image' in response.headers.get('content-type', ''):
            # Successfully got the image
            return Response(
                response.content,
                mimetype=response.headers.get('content-type', 'image/jpeg'),
                headers={
                    'Cache-Control': 'public, max-age=3600',
                    'Content-Length': len(response.content)
                }
            )
    except Exception as e:
        print(f"Failed to fetch image for {member_id}: {e}")
    
    # Fallback to SVG avatar
    svg_avatar = '''<svg width="200" height="200" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
<circle cx="100" cy="100" r="100" fill="#6c757d"/>
<svg x="50" y="50" width="100" height="100" viewBox="0 0 24 24" fill="white">
<path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
</svg>
</svg>'''
    
    return Response(
        svg_avatar,
        mimetype='image/svg+xml',
        headers={
            'Cache-Control': 'public, max-age=3600'
        }
    )

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
        
        # Try to get cached analysis results
        cache_key = f"analysis_{congress}_{chamber}"
        cached_results = cache.get(cache_key)
        
        if cached_results:
            app.logger.info(f"Serving cached analysis for Congress {congress}, {chamber}")
            cached_results['cached'] = True
            cached_results['cache_retrieved_at'] = datetime.now().isoformat()
            return jsonify(cached_results)
        
        # If no cache, run analysis and cache the results
        app.logger.info(f"Running fresh analysis for Congress {congress}, {chamber}")
        # Calculate days since 119th Congress started (January 3, 2025)
        from datetime import date
        congress_start = date(2025, 1, 3)
        days_since_start = (date.today() - congress_start).days + 1  # +1 to include start date
        window_days = max(days_since_start, 30)  # Minimum 30 days for analysis
        app.logger.info(f"Using {window_days} day window since 119th Congress start ({congress_start})")
        results = run_simple_house_analysis(congress, chamber, window_days=window_days)
        
        # Cache results for 6 hours (21600 seconds)
        cache.set(cache_key, results, timeout=21600)
        
        results['cached'] = False
        results['generated_at'] = datetime.now().isoformat()
        
        return jsonify(results)
    except Exception as e:
        app.logger.error(f"Analysis error: {str(e)}")
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
        # Get query parameters for filtering
        party_filter = request.args.get('party', None)
        
        with get_db_session() as session:
            # Get House members with party filtering
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
        # Get query parameters for filtering
        party_filter = request.args.get('party', None)
        
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
            member_query = session.query(Member).filter(
                Member.member_id_bioguide.in_(member_ids)
            )
            
            # Apply party filter if specified (but always include the target member)
            if party_filter:
                member_query = member_query.filter(
                    or_(
                        Member.party == party_filter,
                        Member.member_id_bioguide == bioguide_id  # Always include target
                    )
                )
            
            members = member_query.all()
            
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

@app.route('/explainer/party-line-votes')
def party_line_explainer():
    """Party line votes explainer page."""
    return render_template('party_line_explainer.html')

@app.route('/api/caucus/<int:caucus_id>/network')
def get_caucus_network(caucus_id):
    """Get network graph data for a specific caucus showing sponsor/cosponsor relationships."""
    try:
        with get_db_session() as session:
            # Get caucus info
            caucus = session.query(Caucus).filter(Caucus.id == caucus_id).first()
            if not caucus:
                return jsonify({'error': 'Caucus not found'}), 404
            
            # Get all caucus members
            caucus_members = session.query(Member).join(
                CaucusMembership, Member.member_id_bioguide == CaucusMembership.member_id_bioguide
            ).filter(
                CaucusMembership.caucus_id == caucus_id,
                CaucusMembership.end_date.is_(None)  # Active memberships only
            ).all()
            
            caucus_member_ids = {m.member_id_bioguide for m in caucus_members}
            
            # Get all sponsor/cosponsor relationships involving caucus members
            # This includes both directions: caucus member as sponsor, and caucus member as cosponsor
            sponsor_relationships = session.query(Bill, Cosponsor, Member).join(
                Cosponsor, Bill.bill_id == Cosponsor.bill_id
            ).join(
                Member, Cosponsor.member_id_bioguide == Member.member_id_bioguide
            ).filter(
                or_(
                    Bill.sponsor_bioguide.in_(caucus_member_ids),  # Caucus member is sponsor
                    Cosponsor.member_id_bioguide.in_(caucus_member_ids)  # Caucus member is cosponsor
                )
            ).all()
            
            # Collect all unique members involved (caucus + distance 1)
            all_member_ids = set(caucus_member_ids)
            for bill, cosponsor, member in sponsor_relationships:
                all_member_ids.add(bill.sponsor_bioguide)
                all_member_ids.add(cosponsor.member_id_bioguide)
            
            # Get all involved members
            all_members = session.query(Member).filter(
                Member.member_id_bioguide.in_(all_member_ids)
            ).all()
            
            # Create nodes
            nodes = []
            for member in all_members:
                is_caucus_member = member.member_id_bioguide in caucus_member_ids
                
                # Different styling for caucus vs non-caucus members
                if is_caucus_member:
                    color = caucus.color if caucus.color else '#dc3545'  # Use caucus color or default red
                    size = 25
                    border_width = 3
                else:
                    # Color by party for non-caucus members
                    if member.party == 'D':
                        color = '#1f77b4'  # Blue
                    elif member.party == 'R':
                        color = '#ff7f0e'  # Orange
                    else:
                        color = '#2ca02c'  # Green
                    size = 15
                    border_width = 1
                
                nodes.append({
                    'id': member.member_id_bioguide,
                    'label': f"{member.first} {member.last}",
                    'title': f"{member.first} {member.last} ({member.party}-{member.state})",
                    'color': color,
                    'size': size,
                    'borderWidth': border_width,
                    'party': member.party,
                    'state': member.state,
                    'district': member.district,
                    'is_caucus_member': is_caucus_member
                })
            
            # Create edges (sponsor -> cosponsor relationships)
            edges = []
            edge_counts = {}  # Track multiple relationships between same pair
            
            for bill, cosponsor, member in sponsor_relationships:
                sponsor_id = bill.sponsor_bioguide
                cosponsor_id = cosponsor.member_id_bioguide
                
                if sponsor_id != cosponsor_id:  # Avoid self-loops
                    edge_key = f"{sponsor_id}-{cosponsor_id}"
                    
                    if edge_key not in edge_counts:
                        edge_counts[edge_key] = {
                            'count': 0,
                            'bills': []
                        }
                    
                    edge_counts[edge_key]['count'] += 1
                    edge_counts[edge_key]['bills'].append({
                        'id': bill.bill_id,
                        'title': bill.title,
                        'type': bill.type.upper(),
                        'number': bill.number
                    })
            
            # Create edge objects
            for edge_key, edge_data in edge_counts.items():
                sponsor_id, cosponsor_id = edge_key.split('-')
                
                # Edge width based on number of relationships
                width = min(1 + edge_data['count'] * 0.5, 5)  # Cap at width 5
                
                edges.append({
                    'from': sponsor_id,
                    'to': cosponsor_id,
                    'width': width,
                    'value': edge_data['count'],
                    'title': f"{edge_data['count']} sponsor/cosponsor relationship(s)",
                    'bills': edge_data['bills'][:5]  # Limit to first 5 bills for tooltip
                })
            
            return jsonify({
                'caucus': {
                    'id': caucus.id,
                    'name': caucus.name,
                    'short_name': caucus.short_name,
                    'color': caucus.color
                },
                'nodes': nodes,
                'edges': edges,
                'stats': {
                    'caucus_members': len(caucus_member_ids),
                    'total_members': len(all_member_ids),
                    'relationships': len(edges)
                }
            })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/caucus/<int:caucus_id>/network')
def caucus_network_page(caucus_id):
    """Render the caucus network visualization page."""
    try:
        with get_db_session() as session:
            caucus = session.query(Caucus).filter(Caucus.id == caucus_id).first()
            if not caucus:
                return "Caucus not found", 404
            
            return render_template('caucus_network.html', caucus=caucus)
    except Exception as e:
        return f"Error: {str(e)}", 500


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
            
            # Get sponsored bills ordered by date introduced descending (most recent first)
            sponsored_bills = session.query(Bill).filter(
                Bill.sponsor_bioguide == bioguide_id
            ).order_by(Bill.introduced_date.desc()).all()
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
                    
                    # Calculate cross-party vote status
                    is_cross_party = False
                    if vote.vote_code in ['Yea', 'Nay']:
                        # Get all votes for this rollcall with member party info
                        all_votes = session.query(Vote, Member.party).join(
                            Member, Vote.member_id_bioguide == Member.member_id_bioguide
                        ).filter(
                            Vote.rollcall_id == vote.rollcall_id,
                            Vote.vote_code.in_(['Yea', 'Nay']),
                            Member.district.isnot(None)  # House members only
                        ).all()
                        
                        # Count party votes - handle various party name formats
                        party_votes = {}
                        for v, party in all_votes:
                            # Normalize party names
                            if party in ['Republican', 'R']:
                                normalized_party = 'Republican'
                            elif party in ['Democratic', 'Democrat', 'D']:
                                normalized_party = 'Democratic'
                            else:
                                normalized_party = party  # Keep as-is for other parties
                            
                            if normalized_party not in party_votes:
                                party_votes[normalized_party] = {'Yea': 0, 'Nay': 0}
                            party_votes[normalized_party][v.vote_code] += 1
                        
                        # Determine party majority positions
                        # Normalize member party name
                        if member.party in ['Republican', 'R']:
                            member_party = 'Republican'
                        elif member.party in ['Democratic', 'Democrat', 'D']:
                            member_party = 'Democratic'
                        else:
                            member_party = member.party
                        
                        if member_party in party_votes:
                            party_yea = party_votes[member_party]['Yea']
                            party_nay = party_votes[member_party]['Nay']
                            
                            # Party majority position
                            if party_yea > party_nay:
                                party_majority_vote = 'Yea'
                            elif party_nay > party_yea:
                                party_majority_vote = 'Nay'
                            else:
                                party_majority_vote = None  # Tie
                            
                            # Check if member voted against party majority
                            if party_majority_vote and vote.vote_code != party_majority_vote:
                                is_cross_party = True
                            
                            # Debug logging for Marie Perez or frequent cross-voters
                            if member.last in ['Perez', 'Ocasio-Cortez', 'Massie'] or is_cross_party:
                                app.logger.info(f"DEBUG Cross-party for {member.first} {member.last} ({member.party} -> {member_party}) on {vote.rollcall_id}:")
                                app.logger.info(f"  Member vote: {vote.vote_code}")
                                app.logger.info(f"  Party breakdown: {party_votes}")
                                app.logger.info(f"  Party majority: {party_majority_vote}")
                                app.logger.info(f"  Is cross-party: {is_cross_party}")
                                app.logger.info(f"  Total votes analyzed: {len(all_votes)}")
                    
                    recent_votes_data.append({
                        'rollcall_id': vote.rollcall_id,
                        'vote_code': vote.vote_code,
                        'question': rollcall.question,
                        'date': rollcall.date.isoformat() if rollcall.date else None,
                        'bill_id': rollcall.bill_id,
                        'bill_title': bill_title,
                        'is_cross_party': is_cross_party
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
                    'is_true_blue_democrat': is_true_blue_democrat,
                    # Contact information
                    'email': member.email,
                    'phone': member.phone,
                    'website': member.website,
                    'dc_office': member.dc_office,
                    'actblue_url': member.actblue_url
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
            
            # Optimized query to get cosponsors with member details in one query
            cos_query = session.query(Cosponsor, Member).join(
                Member, Cosponsor.member_id_bioguide == Member.member_id_bioguide
            ).filter(Cosponsor.bill_id == bill_id).all()
            
            cos_rows = []
            for cosponsor, member in cos_query:
                # Skip cosponsors with invalid/missing member data
                if not member or not member.first or not member.last:
                    continue
                    
                cos_rows.append({
                    'member_id': cosponsor.member_id_bioguide,
                    'member_name': f"{member.first} {member.last}",
                    'party': member.party or '',
                    'state': member.state or '',
                    'district': member.district,
                    'date': cosponsor.date,
                    'is_original': cosponsor.is_original
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

@app.route('/actblue-management')
def actblue_management_page():
    """ActBlue URL management page (dev mode only)."""
    return render_template('actblue_management.html')

@app.route('/caucus/<int:caucus_id>')
def caucus_info_page(caucus_id):
    """Render the caucus information page."""
    try:
        with get_db_session() as session:
            caucus = session.query(Caucus).filter(Caucus.id == caucus_id).first()
            if not caucus:
                return render_template('caucus_info.html', error='Caucus not found', caucus=None, members=[])
            
            # Get active members of this caucus
            memberships = session.query(CaucusMembership).join(Member).filter(
                CaucusMembership.caucus_id == caucus_id,
                CaucusMembership.end_date.is_(None)
            ).all()
            
            members_data = []
            for membership in memberships:
                member = membership.member
                members_data.append({
                    'id': member.member_id_bioguide,
                    'name': f"{member.first} {member.last}",
                    'party': member.party,
                    'state': member.state,
                    'district': member.district,
                    'start_date': membership.start_date.isoformat() if membership.start_date else None,
                    'notes': membership.notes
                })
            
            # Sort members by last name, then first name
            members_data.sort(key=lambda x: (x['name'].split()[-1], x['name'].split()[0]))
            
            return render_template('caucus_info.html', caucus=caucus, members=members_data)
            
    except Exception as e:
        return render_template('caucus_info.html', error=str(e), caucus=None, members=[])

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
            
            # Sort caucus members by last name, then first name (ignoring accents)
            member_data.sort(key=lambda x: (
                normalize_for_sorting(x['member_name'].split()[-1]), 
                normalize_for_sorting(x['member_name'].split()[0])
            ))
            
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

# ActBlue Management API (Dev Mode)
@app.route('/api/actblue/members')
def get_members_for_actblue():
    """Get Democratic members for ActBlue URL management."""
    try:
        with get_db_session() as session:
            # Get Democratic House members only
            members = session.query(Member).filter(
                Member.district.isnot(None),  # House members only
                Member.party.in_(['D', 'Democrat', 'Democratic'])
            ).order_by(Member.state, Member.district).all()
            
            members_data = []
            for member in members:
                members_data.append({
                    'bioguide_id': member.member_id_bioguide,
                    'name': f"{member.first} {member.last}",
                    'state': member.state,
                    'district': member.district,
                    'actblue_url': member.actblue_url
                })
            
            return jsonify({'members': members_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/actblue/update', methods=['POST'])
def update_actblue_url():
    """Update ActBlue URL for a member."""
    try:
        data = request.get_json()
        bioguide_id = data.get('bioguide_id')
        actblue_url = data.get('actblue_url', '').strip()
        
        if not bioguide_id:
            return jsonify({'error': 'bioguide_id is required'}), 400
        
        with get_db_session() as session:
            member = session.query(Member).filter(
                Member.member_id_bioguide == bioguide_id
            ).first()
            
            if not member:
                return jsonify({'error': 'Member not found'}), 404
            
            member.actblue_url = actblue_url if actblue_url else None
            session.commit()
            
            return jsonify({
                'success': True,
                'message': f'ActBlue URL updated for {member.first} {member.last}',
                'actblue_url': member.actblue_url
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/docs')
@app.route('/docs/')
def docs_index():
    """Serve the documentation index page."""
    return render_template('docs_index.html')

@app.route('/docs/<path:filename>')
def docs_file(filename):
    """Serve documentation files."""
    try:
        # Security: only allow .md files and prevent directory traversal
        if not filename.endswith('.md') or '..' in filename:
            return "File not found", 404
        
        file_path = os.path.join('docs', filename)
        if not os.path.exists(file_path):
            return "File not found", 404
        
        # Read and convert markdown to HTML
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Simple markdown to HTML conversion (basic)
        html_content = convert_markdown_to_html(content)
        
        return render_template('docs_viewer.html', 
                             content=html_content, 
                             filename=filename,
                             title=get_doc_title(content))
    except Exception as e:
        return f"Error reading file: {str(e)}", 500

def convert_markdown_to_html(markdown_text):
    """Convert markdown to HTML with basic formatting."""
    # Basic markdown conversion
    html = markdown_text
    
    # Headers
    html = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    
    # Bold and italic
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html)
    
    # Code blocks
    html = re.sub(r'```sql\n(.*?)\n```', r'<pre><code class="sql">\1</code></pre>', html, flags=re.DOTALL)
    html = re.sub(r'```(.*?)\n(.*?)\n```', r'<pre><code class="\1">\2</code></pre>', html, flags=re.DOTALL)
    
    # Inline code
    html = re.sub(r'`(.*?)`', r'<code>\1</code>', html)
    
    # Links
    html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)
    
    # Lists
    html = re.sub(r'^- (.*?)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'^(\d+)\. (.*?)$', r'<li>\2</li>', html, flags=re.MULTILINE)
    
    # Wrap lists in ul/ol tags
    html = re.sub(r'(<li>.*?</li>)', r'<ul>\1</ul>', html, flags=re.DOTALL)
    
    # Paragraphs
    html = re.sub(r'\n\n', r'</p><p>', html)
    html = '<p>' + html + '</p>'
    
    # Clean up empty paragraphs
    html = re.sub(r'<p></p>', '', html)
    
    return html

def get_doc_title(content):
    """Extract title from markdown content."""
    # Look for first # header
    match = re.search(r'^# (.*?)$', content, re.MULTILINE)
    if match:
        return match.group(1)
    return "Documentation"

# -----------------------------
# Subjects summary endpoints
# -----------------------------

def _is_truthy(val: str) -> bool:
    if val is None:
        return False
    return str(val).lower() in ("1", "true", "yes", "on")

@app.route('/api/subjects/summary')
def subjects_summary_api():
    """Return cross-party votes and percentages per subject for D and R.

    Cross-party definition: for a given roll call and party, a vote that
    goes against that party's majority (ties are ignored for that party/roll call).

    Query params:
      - congress: int (default 119)
      - scope: 'policy_area' | 'subject_term' (default 'policy_area')
      - min_votes: int (default 20)  [applied to combined party totals]
      - chamber: 'house' | 'senate' (default 'house')
      - exclude_procedural: bool (default true)
    """
    try:
        congress = int(request.args.get('congress', 119))
        scope = request.args.get('scope', 'policy_area')
        min_votes = int(request.args.get('min_votes', 20))
        chamber = request.args.get('chamber', 'house')
        exclude_procedural = _is_truthy(request.args.get('exclude_procedural', 'true'))

        if scope not in ('policy_area', 'subject_term'):
            scope = 'policy_area'

        with get_db_session() as session:
            subject_expr = 'b.policy_area' if scope == 'policy_area' else 's.subject_term'
            join_subject = '' if scope == 'policy_area' else 'LEFT JOIN bill_subjects s ON s.bill_id = b.bill_id'
            subject_not_null = ' AND b.policy_area IS NOT NULL' if scope == 'policy_area' else ' AND s.subject_term IS NOT NULL'

            procedural_filter = ''
            if exclude_procedural:
                procedural_filter = (
                    " AND ("
                    " r.question IS NULL OR ("
                    " r.question NOT LIKE '%rule%' AND"
                    " r.question NOT LIKE '%previous question%' AND"
                    " r.question NOT LIKE '%recommit%' AND"
                    " r.question NOT LIKE '%motion to table%' AND"
                    " r.question NOT LIKE '%quorum%' AND"
                    " r.question NOT LIKE '%adjourn%' AND"
                    " r.question NOT LIKE '%suspend the rules%'"
                    ") )"
                )

            # Pull per-vote rows with subject, party and vote code
            query = f"""
                SELECT r.rollcall_id AS rc_id,
                       {subject_expr} AS subject,
                       m.party AS party,
                       v.vote_code AS vote_code
                FROM votes v
                JOIN rollcalls r ON v.rollcall_id = r.rollcall_id
                JOIN bills b ON r.bill_id = b.bill_id
                {join_subject}
                JOIN members m ON v.member_id_bioguide = m.member_id_bioguide
                WHERE b.congress = :congress
                  AND b.chamber = :chamber
                  AND b.bill_id LIKE CONCAT('%-', :congress)
                  AND v.vote_code IN ('Yea','Nay')
                  {subject_not_null}
                  {procedural_filter}
            """

            rows = session.execute(text(query), {'congress': congress, 'chamber': chamber}).fetchall()

            # First pass: party-majority by (rollcall, party, subject)
            from collections import defaultdict
            counts = defaultdict(lambda: {'Yea': 0, 'Nay': 0})  # key: (rc_id, party_norm, subject)
            normalized_rows = []
            for rc_id, subject, party, vote_code in rows:
                if not subject:
                    continue
                # Normalize party to D/R where possible
                p = (party or '').upper()
                if p in ('DEM', 'DEMOCATIC', 'DEMOCRATIC', 'D'):
                    p = 'D'
                elif p in ('REP', 'REPUBLICAN', 'R'):
                    p = 'R'
                else:
                    # Ignore other parties in cross-party calc
                    continue
                counts[(rc_id, p, subject)][vote_code] += 1
                normalized_rows.append((rc_id, subject, p, vote_code))

            majority = {}
            for key, d in counts.items():
                if d['Yea'] > d['Nay']:
                    majority[key] = 'Yea'
                elif d['Nay'] > d['Yea']:
                    majority[key] = 'Nay'
                else:
                    majority[key] = None  # tie -> ignore

            # Second pass: accumulate cross-party counts per (subject, party)
            agg = defaultdict(lambda: {'D': {'cross': 0, 'total': 0}, 'R': {'cross': 0, 'total': 0}})
            for rc_id, subject, p, vote_code in normalized_rows:
                maj = majority.get((rc_id, p, subject))
                if not maj:
                    continue  # skip ties for that party/roll call
                agg[subject][p]['total'] += 1
                if vote_code != maj:
                    agg[subject][p]['cross'] += 1

            # Build list with cross-party percentages; enforce combined min_votes
            items = []
            for subject, data in agg.items():
                votes_combined = data['D']['total'] + data['R']['total']
                if votes_combined < min_votes:
                    continue
                def pct(c, t):
                    return round((c / t) * 100, 1) if t else None
                d_pct = pct(data['D']['cross'], data['D']['total'])
                r_pct = pct(data['R']['cross'], data['R']['total'])
                gap = None
                if d_pct is not None and r_pct is not None:
                    gap = round(abs(d_pct - r_pct), 1)
                items.append({
                    'subject': subject,
                    'd_cross_pct': d_pct,
                    'd_cross': data['D']['cross'],
                    'd_total': data['D']['total'],
                    'r_cross_pct': r_pct,
                    'r_cross': data['R']['cross'],
                    'r_total': data['R']['total'],
                    'gap': gap,
                    'votes': votes_combined
                })

            # Sort by gap desc, then votes desc
            items.sort(key=lambda x: ((x['gap'] is not None), (x['gap'] or -1), x['votes']), reverse=True)
            return jsonify({'congress': congress, 'scope': scope, 'chamber': chamber, 'min_votes': min_votes, 'exclude_procedural': exclude_procedural, 'items': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/subjects')
def subjects_summary_page():
    """Render an HTML table of subjects and party splits."""
    try:
        # Defaults mirror the API
        return render_template('subjects.html')
    except Exception as e:
        return f"Error: {str(e)}", 500

# -----------------------------
# Reference data: Policy Areas
# -----------------------------

@app.route('/api/policy-areas')
def api_policy_areas():
    """Return list of available policy areas for a given congress/chamber.

    Query params: congress (default 119), chamber (default 'house'),
    exclude_procedural (default true), min_votes (default 5)
    """
    try:
        congress = int(request.args.get('congress', 119))
        chamber = request.args.get('chamber', 'house')
        exclude_procedural = _is_truthy(request.args.get('exclude_procedural', 'true'))
        min_votes = int(request.args.get('min_votes', 5))
        with get_db_session() as session:
            proc = (
                " AND (r.question IS NULL OR ("
                " r.question NOT LIKE '%rule%' AND"
                " r.question NOT LIKE '%previous question%' AND"
                " r.question NOT LIKE '%recommit%' AND"
                " r.question NOT LIKE '%motion to table%' AND"
                " r.question NOT LIKE '%quorum%' AND"
                " r.question NOT LIKE '%adjourn%' AND"
                " r.question NOT LIKE '%suspend the rules%'"
                "))"
            ) if exclude_procedural else ""

            # Only include policy areas where at least one member has >= min_votes Yea/Nay votes
            query = f"""
                SELECT rc.policy_area, rc.vote_count
                FROM (
                    SELECT b.policy_area AS policy_area, COUNT(DISTINCT r.rollcall_id) AS vote_count
                    FROM bills b
                    JOIN rollcalls r ON r.bill_id = b.bill_id
                    WHERE b.congress = :congress
                      AND b.chamber = :chamber
                      AND b.bill_id LIKE CONCAT('%-', :congress)
                      AND b.policy_area IS NOT NULL AND b.policy_area <> ''
                      {proc}
                    GROUP BY b.policy_area
                ) rc
                JOIN (
                    SELECT t.policy_area
                    FROM (
                        SELECT b.policy_area AS policy_area, v.member_id_bioguide AS member_id, COUNT(*) AS member_votes
                        FROM votes v
                        JOIN rollcalls r ON v.rollcall_id = r.rollcall_id
                        JOIN bills b ON r.bill_id = b.bill_id
                        JOIN members m ON v.member_id_bioguide = m.member_id_bioguide
                        WHERE b.congress = :congress
                          AND b.chamber = :chamber
                          AND b.bill_id LIKE CONCAT('%-', :congress)
                          AND v.vote_code IN ('Yea','Nay')
                          {proc}
                        GROUP BY b.policy_area, v.member_id_bioguide
                    ) t
                    GROUP BY t.policy_area
                    HAVING MAX(t.member_votes) >= :min_votes
                ) q ON q.policy_area = rc.policy_area
                ORDER BY rc.vote_count DESC, rc.policy_area ASC
            """
            rows = session.execute(text(query), {'congress': congress, 'chamber': chamber, 'min_votes': min_votes}).fetchall()
            items = [{'name': row.policy_area, 'count': int(row.vote_count or 0)} for row in rows]
            return jsonify({'congress': congress, 'chamber': chamber, 'exclude_procedural': exclude_procedural, 'min_votes': min_votes, 'count': len(items), 'items': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/subject-terms')
def api_subject_terms():
    """Return list of subject terms ordered by number of roll calls (votes) desc.

    Query params: congress (default 119), chamber (default 'house'),
    exclude_procedural (default true), min_votes (default 5)
    """
    try:
        congress = int(request.args.get('congress', 119))
        chamber = request.args.get('chamber', 'house')
        exclude_procedural = _is_truthy(request.args.get('exclude_procedural', 'true'))
        min_votes = int(request.args.get('min_votes', 5))
        with get_db_session() as session:
            proc = (
                " AND (r.question IS NULL OR ("
                " r.question NOT LIKE '%rule%' AND"
                " r.question NOT LIKE '%previous question%' AND"
                " r.question NOT LIKE '%recommit%' AND"
                " r.question NOT LIKE '%motion to table%' AND"
                " r.question NOT LIKE '%quorum%' AND"
                " r.question NOT LIKE '%adjourn%' AND"
                " r.question NOT LIKE '%suspend the rules%'"
                "))"
            ) if exclude_procedural else ""

            query = f"""
                SELECT rc.subject_term, rc.vote_count
                FROM (
                    SELECT s.subject_term AS subject_term, COUNT(DISTINCT r.rollcall_id) AS vote_count
                    FROM bill_subjects s
                    JOIN bills b ON b.bill_id = s.bill_id
                    JOIN rollcalls r ON r.bill_id = b.bill_id
                    WHERE b.congress = :congress
                      AND b.chamber = :chamber
                      AND b.bill_id LIKE CONCAT('%-', :congress)
                      AND s.subject_term IS NOT NULL AND s.subject_term <> ''
                      {proc}
                    GROUP BY s.subject_term
                ) rc
                JOIN (
                    SELECT t.subject_term
                    FROM (
                        SELECT s.subject_term AS subject_term, v.member_id_bioguide AS member_id, COUNT(*) AS member_votes
                        FROM votes v
                        JOIN rollcalls r ON v.rollcall_id = r.rollcall_id
                        JOIN bills b ON r.bill_id = b.bill_id
                        JOIN bill_subjects s ON s.bill_id = b.bill_id
                        JOIN members m ON v.member_id_bioguide = m.member_id_bioguide
                        WHERE b.congress = :congress
                          AND b.chamber = :chamber
                          AND b.bill_id LIKE CONCAT('%-', :congress)
                          AND s.subject_term IS NOT NULL AND s.subject_term <> ''
                          AND v.vote_code IN ('Yea','Nay')
                          {proc}
                        GROUP BY s.subject_term, v.member_id_bioguide
                    ) t
                    GROUP BY t.subject_term
                    HAVING MAX(t.member_votes) >= :min_votes
                ) q ON q.subject_term = rc.subject_term
                ORDER BY rc.vote_count DESC, rc.subject_term ASC
            """
            rows = session.execute(text(query), {'congress': congress, 'chamber': chamber, 'min_votes': min_votes}).fetchall()
            items = [{'name': row.subject_term, 'count': int(row.vote_count or 0)} for row in rows]
            return jsonify({'congress': congress, 'chamber': chamber, 'exclude_procedural': exclude_procedural, 'min_votes': min_votes, 'count': len(items), 'items': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# -----------------------------
# Clusters (quick MVP)
# -----------------------------

@app.route('/api/clusters')
def api_clusters():
    """Compute quick vote-pattern clusters for members (House by default).

    Returns 2D SVD coordinates and KMeans cluster labels.

    Params:
      - congress: int (default 119)
      - chamber: 'house' | 'senate' (default 'house')
      - rc_limit: max roll calls to include (default 400, newest by date)
      - min_votes: min votes a member must have among included RCs (default 50)
      - k: number of clusters for KMeans (default 5)
      - exclude_procedural: bool (default true)
      - scope: 'policy_area' | 'subject_term' (optional)
      - subject: comma-separated list of subjects to filter roll calls (optional)
    """
    if not _SKLEARN_AVAILABLE:
        return jsonify({'error': 'scikit-learn not available in this runtime'}), 500
    try:
        congress = int(request.args.get('congress', 119))
        chamber = request.args.get('chamber', 'house')
        rc_limit_param = request.args.get('rc_limit')  # if omitted, include all
        rc_limit = int(rc_limit_param) if rc_limit_param is not None else None
        min_votes = int(request.args.get('min_votes', 5))
        k = int(request.args.get('k', 5))
        exclude_procedural = _is_truthy(request.args.get('exclude_procedural', 'true'))
        scope = request.args.get('scope')  # None, 'policy_area', or 'subject_term'
        subject_param = request.args.get('subject')
        subjects = [s.strip() for s in subject_param.split(',')] if subject_param else []

        with get_db_session() as session:
            # 1) Get recent rollcalls for scope (ORM for portability)
            rc_q = session.query(Rollcall.rollcall_id, Rollcall.date, Rollcall.question) \
                          .join(Bill, Rollcall.bill_id == Bill.bill_id) \
                          .filter(Rollcall.congress == congress, Rollcall.chamber == chamber) \
                          .filter(Bill.congress == congress, Bill.chamber == chamber) \
                          .filter(Bill.bill_id.like(f"%-{congress}"))

            # Optional: filter by subject(s)
            if subjects and scope in ('policy_area', 'subject_term'):
                if scope == 'policy_area':
                    rc_q = rc_q.filter(Bill.policy_area.in_(subjects))
                else:
                    rc_q = rc_q.join(BillSubject, BillSubject.bill_id == Bill.bill_id).filter(BillSubject.subject_term.in_(subjects))

            rc_q = rc_q.order_by(Rollcall.date.desc())
            if rc_limit:
                rc_q = rc_q.limit(rc_limit)
            rc_rows = rc_q.all()
            rc_ids = [row.rollcall_id for row in rc_rows]
            if not rc_ids:
                return jsonify({'error': 'No roll calls found for scope', 'detail': {'subjects': subjects, 'scope': scope}}), 404

            # 2) Fetch votes (Yea/Nay only) for those rollcalls, house members only if chamber=house
            procedural_filter = ''
            if exclude_procedural:
                procedural_filter = (
                    " AND ("
                    " r.question IS NULL OR ("
                    " r.question NOT LIKE '%rule%' AND"
                    " r.question NOT LIKE '%previous question%' AND"
                    " r.question NOT LIKE '%recommit%' AND"
                    " r.question NOT LIKE '%motion to table%' AND"
                    " r.question NOT LIKE '%quorum%' AND"
                    " r.question NOT LIKE '%adjourn%' AND"
                    " r.question NOT LIKE '%suspend the rules%'"
                    ") )"
                )

            # Use ORM for IN list and optional procedural filter
            vq = session.query(Vote.rollcall_id, Vote.member_id_bioguide, Vote.vote_code) \
                     .join(Rollcall, Vote.rollcall_id == Rollcall.rollcall_id) \
                     .join(Member, Vote.member_id_bioguide == Member.member_id_bioguide) \
                     .filter(Vote.rollcall_id.in_(rc_ids)) \
                     .filter(Vote.vote_code.in_(['Yea','Nay']))
            if chamber == 'house':
                vq = vq.filter(Member.district.isnot(None))
            if exclude_procedural:
                vq = vq.filter(
                    or_(
                        Rollcall.question.is_(None),
                        and_(
                            ~Rollcall.question.ilike('%rule%'),
                            ~Rollcall.question.ilike('%previous question%'),
                            ~Rollcall.question.ilike('%recommit%'),
                            ~Rollcall.question.ilike('%motion to table%'),
                            ~Rollcall.question.ilike('%quorum%'),
                            ~Rollcall.question.ilike('%adjourn%'),
                            ~Rollcall.question.ilike('%suspend the rules%')
                        )
                    )
                )
            votes_rows = vq.all()

            # 3) Member metadata
            # Fetch only needed fields and detach into plain dict to avoid detached-instance errors
            members_rows = session.query(
                Member.member_id_bioguide, Member.first, Member.last, Member.party, Member.state, Member.district
            ).filter(
                Member.district.isnot(None) if chamber == 'house' else Member.district.is_(None)
            ).all()
            members = {
                row.member_id_bioguide: {
                    'first': row.first or '',
                    'last': row.last or '',
                    'party': row.party,
                    'state': row.state,
                    'district': row.district
                }
                for row in members_rows
            }

        # Build index maps
        rc_index = {rc_id: i for i, rc_id in enumerate(rc_ids)}
        member_ids = sorted({row.member_id_bioguide for row in votes_rows if row.member_id_bioguide in members})
        if not member_ids:
            return jsonify({'error': 'No member votes found'}), 404
        mem_index = {mid: i for i, mid in enumerate(member_ids)}

        # Matrix: rows=members, cols=rollcalls, values in {-1,0,+1}
        M = np.zeros((len(member_ids), len(rc_ids)), dtype=np.float32)
        counts = np.zeros(len(member_ids), dtype=np.int32)
        for rc_id, mid, code in votes_rows:
            if mid not in mem_index:
                continue
            i = mem_index[mid]
            j = rc_index.get(rc_id)
            if j is None:
                continue
            val = 1.0 if code == 'Yea' else -1.0
            M[i, j] = val
            counts[i] += 1

        # Filter members with too few votes
        keep = counts >= min_votes
        if not np.any(keep):
            return jsonify({'error': 'No members meet min_votes threshold', 'detail': {'min_votes': int(min_votes), 'members_with_votes': int((counts>0).sum())}}), 400
        M = M[keep]
        kept_member_ids = [mid for mid in member_ids if keep[mem_index[mid]]]

        # Drop columns (rollcalls) with no data after member filter
        nonzero_cols_mask = (M != 0).any(axis=0)
        if not np.any(nonzero_cols_mask):
            return jsonify({'error': 'No usable roll calls after filters', 'detail': {'rc_count': int(len(rc_ids)), 'min_votes': int(min_votes)}}), 400
        M = M[:, nonzero_cols_mask]

        # Center per member (zero mean across present votes) to reduce baseline bias
        row_sums = M.sum(axis=1, keepdims=True)
        row_counts = (M != 0).sum(axis=1, keepdims=True)
        with np.errstate(invalid='ignore', divide='ignore'):
            row_means = np.divide(row_sums, row_counts, out=np.zeros_like(row_sums), where=row_counts!=0)
        M_centered = M - row_means
        # Fill remaining zeros for stability
        M_centered = np.nan_to_num(M_centered, nan=0.0)

        # SVD reduce to up to 10 components, but ensure at least 2
        max_rank = int(min(M_centered.shape) - 1)
        if max_rank < 2:
            return jsonify({'error': 'Insufficient variation for SVD', 'detail': {'rows': int(M_centered.shape[0]), 'cols': int(M_centered.shape[1])}}), 400
        comps = min(10, max_rank)
        svd = TruncatedSVD(n_components=comps, random_state=42)
        Z = svd.fit_transform(M_centered)

        # KMeans on reduced space
        km = KMeans(n_clusters=max(2, k), n_init=10, random_state=42)
        labels = km.fit_predict(Z)

        # Normalize first 3 components to [0,1] for plotting
        k_dims = min(3, Z.shape[1])
        Zk = Z[:, :k_dims]
        mins = Zk.min(axis=0)
        maxs = Zk.max(axis=0)
        denom = np.where((maxs - mins) == 0, 1, (maxs - mins))
        Znorm = (Zk - mins) / denom
        
        # Add small jitter to identical coordinates to prevent overlapping points
        np.random.seed(42)  # For reproducible jitter
        jitter_scale = 0.015  # 1.5% of the coordinate range
        for dim in range(k_dims):
            # Find unique values in this dimension
            unique_vals, inverse_indices = np.unique(Znorm[:, dim], return_inverse=True)
            # For each unique value, add small random jitter to all points with that value
            for i, val in enumerate(unique_vals):
                mask = inverse_indices == i
                if np.sum(mask) > 1:  # Only jitter if there are multiple points with same value
                    # Use member index as additional seed for more deterministic jitter
                    member_indices = np.where(mask)[0]
                    jitter = np.zeros_like(member_indices, dtype=float)
                    for j, member_idx in enumerate(member_indices):
                        np.random.seed(42 + member_idx + dim * 1000)  # Deterministic but varied
                        jitter[j] = np.random.normal(0, jitter_scale)
                    Znorm[mask, dim] += jitter
                    # Ensure jittered values stay within [0,1] bounds
                    Znorm[mask, dim] = np.clip(Znorm[mask, dim], 0, 1)
        
        # Normalized location of 0 on each axis (if within range)
        zeros = (0 - mins) / denom
        zeros = np.clip(zeros, 0, 1)

        # Load caucus membership sets for badges
        caucus_data = load_caucus_data()

        # Build response
        items = []
        for idx, mid in enumerate(kept_member_ids):
            m = members.get(mid)
            # Badge flags
            fc = mid in caucus_data.get('freedom_caucus', set())
            pc = mid in caucus_data.get('progressive_caucus', set())
            bd = mid in caucus_data.get('blue_dog_coalition', set())
            maga = mid in caucus_data.get('maga_republicans', set())
            cbc = mid in caucus_data.get('congressional_black_caucus', set())
            tb = mid in caucus_data.get('true_blue_democrats', set())
            items.append({
                'id': mid,
                'name': (f"{m['first']} {m['last']}".strip() if m else mid),
                'party': (m['party'] if m else None),
                'state': (m['state'] if m else None),
                'district': (int(m['district']) if (m and m['district'] is not None) else None),
                'x': float(Znorm[idx, 0]) if Znorm.shape[1] >= 1 else 0.0,
                'y': float(Znorm[idx, 1]) if Znorm.shape[1] >= 2 else 0.0,
                'z': float(Znorm[idx, 2]) if Znorm.shape[1] >= 3 else None,
                'cluster': int(labels[idx]),
                'badges': {
                    'fc': fc,
                    'pc': pc,
                    'bd': bd,
                    'maga': maga,
                    'cbc': cbc,
                    'tb': tb
                }
            })

        return jsonify({
            'congress': congress,
            'chamber': chamber,
            'rc_limit': (rc_limit if rc_limit is not None else 'all'),
            'min_votes': min_votes,
            'k': k,
            'exclude_procedural': exclude_procedural,
            'scope': scope,
            'subjects': subjects,
            'count': len(items),
            'items': items,
            'norm_zeros': {
                'x0': float(zeros[0]) if k_dims >= 1 else None,
                'y0': float(zeros[1]) if k_dims >= 2 else None,
                'z0': float(zeros[2]) if k_dims >= 3 else None
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/clusters')
def clusters_page():
    """Simple scatter visualization for clusters using the API."""
    try:
        return render_template('clusters.html')
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/clusters/report')
def clusters_report_page():
    """Comprehensive report page for cluster analysis."""
    try:
        return render_template('clusters_report.html')
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/cross-party-analysis')
def cross_party_analysis_page():
    """Cross-party analysis page showing coordinated cross-party votes."""
    try:
        return render_template('cross_party_analysis.html')
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/api/clusters/report')
def api_clusters_report():
    """Generate comprehensive report data for cluster analysis.
    
    Returns combined data from clusters, SVD components, and cluster summaries.
    """
    try:
        # Get parameters
        k = int(request.args.get('k', 5))
        exclude_procedural = _is_truthy(request.args.get('exclude_procedural', 'true'))
        scope = request.args.get('scope')
        subject_param = request.args.get('subject')
        subjects = [s.strip() for s in subject_param.split(',')] if subject_param else []
        svd_dims = int(request.args.get('svd_dims', 2))
        
        # Get cluster data
        cluster_params = f'k={k}&exclude_procedural={exclude_procedural}'
        if subjects and scope:
            cluster_params += f'&scope={scope}&subject={",".join(subjects)}'
        
        # Use the current request's host and port
        base_url = f"{request.scheme}://{request.host}"
        cluster_resp = requests.get(f'{base_url}/api/clusters?{cluster_params}')
        if cluster_resp.status_code != 200:
            return jsonify({'error': 'Failed to get cluster data'}), 500
        cluster_data = cluster_resp.json()
        
        # Get SVD components
        svd_params = f'dims={svd_dims}&exclude_procedural={exclude_procedural}'
        if subjects and scope:
            svd_params += f'&scope={scope}&subject={",".join(subjects)}'
        
        svd_resp = requests.get(f'{base_url}/api/svd/components?{svd_params}')
        svd_data = svd_resp.json() if svd_resp.status_code == 200 else {'components': []}
        
        # Get cluster summary
        summary_resp = requests.get(f'{base_url}/api/clusters/summary?{cluster_params}')
        summary_data = summary_resp.json() if summary_resp.status_code == 200 else {'clusters': []}
        
        # Get auto-k suggestion
        auto_k_resp = requests.get(f'{base_url}/api/clusters/auto-k?{cluster_params}')
        auto_k_data = auto_k_resp.json() if auto_k_resp.status_code == 200 else {}
        
        # Combine all data
        report_data = {
            'parameters': {
                'k': k,
                'exclude_procedural': exclude_procedural,
                'scope': scope,
                'subjects': subjects,
                'svd_dims': svd_dims
            },
            'cluster_data': cluster_data,
            'svd_components': svd_data.get('components', []),
            'cluster_summaries': summary_data.get('clusters', []),
            'auto_k_suggestion': auto_k_data,
            'generated_at': datetime.now().isoformat()
        }
        
        return jsonify(report_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cross-party-analysis')
def api_cross_party_analysis():
    """Get votes where coordinated cross-party voting changed the outcome."""
    try:
        with get_db_session() as session:
            # Get all House members
            members = session.query(Member).filter(
                Member.district.isnot(None)  # House members only
            ).all()
            
            # Get all rollcalls for 119th Congress House
            rollcalls = session.query(Rollcall).filter(
                Rollcall.congress == 119,
                Rollcall.chamber == 'house'
            ).all()
            
            # Get all votes
            rollcall_ids = [rc.rollcall_id for rc in rollcalls]
            votes = session.query(Vote).filter(
                Vote.rollcall_id.in_(rollcall_ids)
            ).all()
            
            # Build vote matrix
            vote_matrix = defaultdict(dict)
            for vote in votes:
                vote_matrix[vote.rollcall_id][vote.member_id_bioguide] = vote.vote_code
            
            # Build member parties lookup
            member_parties = {member.member_id_bioguide: member.party for member in members}
            
            # Pre-calculate party positions for each rollcall
            rollcall_party_positions = {}
            for rollcall_id, rollcall_votes in vote_matrix.items():
                party_votes = {'D': {'Yea': 0, 'Nay': 0}, 'R': {'Yea': 0, 'Nay': 0}}
                
                for member_id, vote_code in rollcall_votes.items():
                    if vote_code in ['Yea', 'Nay']:
                        party = member_parties.get(member_id)
                        if party in ['D', 'R']:
                            party_votes[party][vote_code] += 1
                
                # Determine party position for each rollcall
                rollcall_party_positions[rollcall_id] = {}
                for party in ['D', 'R']:
                    if party_votes[party]['Yea'] > party_votes[party]['Nay']:
                        rollcall_party_positions[rollcall_id][party] = 'Yea'
                    elif party_votes[party]['Nay'] > party_votes[party]['Yea']:
                        rollcall_party_positions[rollcall_id][party] = 'Nay'
                    else:
                        rollcall_party_positions[rollcall_id][party] = 'Tie'
            
            # Analyze coordinated votes
            coordinated_votes = []
            
            for rollcall_id, rollcall_votes in vote_matrix.items():
                # Get rollcall details
                rollcall = next((rc for rc in rollcalls if rc.rollcall_id == rollcall_id), None)
                if not rollcall:
                    continue
                
                # Count total votes for each position
                total_yea = sum(1 for v in rollcall_votes.values() if v == 'Yea')
                total_nay = sum(1 for v in rollcall_votes.values() if v == 'Nay')
                
                # Check each party for coordinated cross-party voting
                for party in ['D', 'R']:
                    if rollcall_id not in rollcall_party_positions or party not in rollcall_party_positions[rollcall_id]:
                        continue
                        
                    party_position = rollcall_party_positions[rollcall_id][party]
                    if party_position == 'Tie':
                        continue
                    
                    # Find all party members who voted against party position
                    party_cross_voters = []
                    for member_id, vote in rollcall_votes.items():
                        if (vote in ['Yea', 'Nay'] and 
                            member_parties.get(member_id) == party and 
                            vote != party_position):
                            
                            # Get member details
                            member = next((m for m in members if m.member_id_bioguide == member_id), None)
                            if member:
                                party_cross_voters.append({
                                    'member_id': member_id,
                                    'name': f"{member.first} {member.last}",
                                    'state': member.state,
                                    'district': member.district,
                                    'vote': vote
                                })
                    
                    # Check if this was coordinated and decisive
                    if len(party_cross_voters) >= 2:  # At least 2 party members cross-voted together
                        # Calculate what the vote would have been if all party members voted party line
                        if party_position == 'Yea':
                            hypothetical_yea = total_yea + len(party_cross_voters)
                            hypothetical_nay = total_nay - len(party_cross_voters)
                        else:  # party_position == 'Nay'
                            hypothetical_yea = total_yea - len(party_cross_voters)
                            hypothetical_nay = total_nay + len(party_cross_voters)
                        
                        # Check if the outcome would have been different
                        current_outcome = 'Yea' if total_yea > total_nay else 'Nay'
                        hypothetical_outcome = 'Yea' if hypothetical_yea > hypothetical_nay else 'Nay'
                        
                        if current_outcome != hypothetical_outcome:
                            # Get bill information if available
                            bill_info = None
                            if rollcall.bill_id:
                                bill = session.query(Bill).filter(Bill.bill_id == rollcall.bill_id).first()
                                if bill:
                                    bill_info = {
                                        'bill_id': bill.bill_id,
                                        'title': bill.title,
                                        'type': bill.type,
                                        'number': bill.number
                                    }
                            
                            coordinated_votes.append({
                                'rollcall_id': rollcall_id,
                                'date': rollcall.date.isoformat() if rollcall.date else None,
                                'question': rollcall.question,
                                'bill_info': bill_info,
                                'party': party,
                                'party_position': party_position,
                                'party_cross_voters': party_cross_voters,
                                'total_yea': total_yea,
                                'total_nay': total_nay,
                                'current_outcome': current_outcome,
                                'hypothetical_outcome': hypothetical_outcome,
                                'margin': abs(total_yea - total_nay)
                            })
            
            # Sort by date (most recent first)
            coordinated_votes.sort(key=lambda x: x['date'] or '', reverse=True)
            
            return jsonify({
                'success': True,
                'total_coordinated_votes': len(coordinated_votes),
                'votes': coordinated_votes
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/clusters/auto-k')
def api_clusters_auto_k():
    """Suggest an optimal k based on clustering metrics (silhouette/CH/DB).

    Params mirror /api/clusters: congress, chamber, rc_limit (optional), min_votes (default 5),
    exclude_procedural, scope, subject.
    Returns suggested_k and metrics for k=2..k_max.
    """
    if not _SKLEARN_AVAILABLE:
        return jsonify({'error': 'scikit-learn not available in this runtime'}), 500
    try:
        congress = int(request.args.get('congress', 119))
        chamber = request.args.get('chamber', 'house')
        rc_limit_param = request.args.get('rc_limit')
        rc_limit = int(rc_limit_param) if rc_limit_param is not None else None
        min_votes = int(request.args.get('min_votes', 5))
        exclude_procedural = _is_truthy(request.args.get('exclude_procedural', 'true'))
        scope = request.args.get('scope')
        subject_param = request.args.get('subject')
        subjects = [s.strip() for s in subject_param.split(',')] if subject_param else []

        # Build the same vote matrix as /api/clusters
        with get_db_session() as session:
            rc_q = (
                session.query(Rollcall.rollcall_id, Rollcall.date, Rollcall.question)
                .join(Bill, Rollcall.bill_id == Bill.bill_id)
                .filter(Rollcall.congress == congress, Rollcall.chamber == chamber)
                .filter(Bill.congress == congress, Bill.chamber == chamber)
                .filter(Bill.bill_id.like(f"%-{congress}"))
            )
            if subjects and scope in ('policy_area', 'subject_term'):
                if scope == 'policy_area':
                    rc_q = rc_q.filter(Bill.policy_area.in_(subjects))
                else:
                    rc_q = rc_q.join(BillSubject, BillSubject.bill_id == Bill.bill_id).filter(BillSubject.subject_term.in_(subjects))
            rc_q = rc_q.order_by(Rollcall.date.desc())
            if rc_limit:
                rc_q = rc_q.limit(rc_limit)
            rc_rows = rc_q.all()
            rc_ids = [row.rollcall_id for row in rc_rows]
            if not rc_ids:
                return jsonify({'error': 'No roll calls found for scope', 'detail': {'subjects': subjects, 'scope': scope}}), 404

            vq = session.query(Vote.rollcall_id, Vote.member_id_bioguide, Vote.vote_code) \
                     .join(Rollcall, Vote.rollcall_id == Rollcall.rollcall_id) \
                     .join(Member, Vote.member_id_bioguide == Member.member_id_bioguide) \
                     .filter(Vote.rollcall_id.in_(rc_ids)) \
                     .filter(Vote.vote_code.in_(['Yea','Nay']))
            if chamber == 'house':
                vq = vq.filter(Member.district.isnot(None))
            if exclude_procedural:
                vq = vq.filter(
                    or_(
                        Rollcall.question.is_(None),
                        and_(
                            ~Rollcall.question.ilike('%rule%'),
                            ~Rollcall.question.ilike('%previous question%'),
                            ~Rollcall.question.ilike('%recommit%'),
                            ~Rollcall.question.ilike('%motion to table%'),
                            ~Rollcall.question.ilike('%quorum%'),
                            ~Rollcall.question.ilike('%adjourn%'),
                            ~Rollcall.question.ilike('%suspend the rules%')
                        )
                    )
                )
            votes_rows = vq.all()

            members_rows = session.query(
                Member.member_id_bioguide
            ).filter(
                Member.district.isnot(None) if chamber == 'house' else Member.district.is_(None)
            ).all()
            all_member_ids = {row.member_id_bioguide for row in members_rows}

        # Build matrix
        rc_index = {rc_id: i for i, rc_id in enumerate(rc_ids)}
        member_ids = sorted({row.member_id_bioguide for row in votes_rows if row.member_id_bioguide in all_member_ids})
        if not member_ids:
            return jsonify({'error': 'No member votes found'}), 404
        mem_index = {mid: i for i, mid in enumerate(member_ids)}
        import numpy as _np
        M = _np.zeros((len(member_ids), len(rc_ids)), dtype=_np.float32)
        counts = _np.zeros(len(member_ids), dtype=_np.int32)
        for rc_id, mid, code in votes_rows:
            i = mem_index.get(mid)
            j = rc_index.get(rc_id)
            if i is None or j is None:
                continue
            M[i, j] = 1.0 if code == 'Yea' else -1.0
            counts[i] += 1
        keep = counts >= min_votes
        if not _np.any(keep):
            return jsonify({'error': 'No members meet min_votes threshold', 'detail': {'min_votes': int(min_votes), 'members_with_votes': int((counts>0).sum())}}), 400
        M = M[keep]
        # Drop empty columns
        nonzero_cols_mask = (M != 0).any(axis=0)
        if not _np.any(nonzero_cols_mask):
            return jsonify({'error': 'No usable roll calls after filters'}), 400
        M = M[:, nonzero_cols_mask]
        # Center per member
        row_sums = M.sum(axis=1, keepdims=True)
        row_counts = (M != 0).sum(axis=1, keepdims=True)
        with _np.errstate(invalid='ignore', divide='ignore'):
            row_means = _np.divide(row_sums, row_counts, out=_np.zeros_like(row_sums), where=row_counts!=0)
        M_centered = _np.nan_to_num(M - row_means, nan=0.0)
        max_rank = int(min(M_centered.shape) - 1)
        if max_rank < 2:
            return jsonify({'error': 'Insufficient variation for SVD', 'detail': {'rows': int(M_centered.shape[0]), 'cols': int(M_centered.shape[1])}}), 400
        comps = min(10, max_rank)
        svd = TruncatedSVD(n_components=comps, random_state=42)
        Z = svd.fit_transform(M_centered)

        # Evaluate k from 2..kmax (bounded by samples)
        n_samples = Z.shape[0]
        kmax = max(3, min(10, n_samples - 1))
        results = []
        best_k = None
        best_sil = -1
        for k in range(2, kmax+1):
            km = KMeans(n_clusters=k, n_init=10, random_state=42)
            labels = km.fit_predict(Z)
            # Skip degenerate case where any cluster is empty (unlikely with KMeans) or all labels same
            if len(set(labels)) < 2:
                continue
            sil = silhouette_score(Z, labels)
            ch = calinski_harabasz_score(Z, labels)
            db = davies_bouldin_score(Z, labels)
            results.append({'k': k, 'silhouette': float(sil), 'calinski_harabasz': float(ch), 'davies_bouldin': float(db)})
            if sil > best_sil:
                best_sil = sil
                best_k = k

        if not results:
            return jsonify({'error': 'Could not compute metrics for any k'}), 400

        # Prefer smallest k within 95% of best silhouette to avoid over-segmentation
        sil_best = max(r['silhouette'] for r in results)
        candidates = [r['k'] for r in results if r['silhouette'] >= 0.95 * sil_best]
        suggested_k = min(candidates) if candidates else best_k

        return jsonify({'suggested_k': int(suggested_k), 'metrics': results, 'kmax': int(kmax), 'params': {
            'congress': congress,
            'chamber': chamber,
            'rc_limit': rc_limit if rc_limit is not None else 'all',
            'min_votes': min_votes,
            'exclude_procedural': exclude_procedural,
            'scope': scope,
            'subjects': subjects
        }})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def generate_cluster_description(cid, size, parts, states, badge_counts, pa_pos, st_pos, top_rc, means, in_total_votes, out_total_votes):
    """Generate nuanced cluster descriptions based on multiple factors."""
    
    # Calculate party composition
    total_members = sum(parts.values())
    dem_pct = (parts.get('D', 0) / total_members * 100) if total_members > 0 else 0
    rep_pct = (parts.get('R', 0) / total_members * 100) if total_members > 0 else 0
    
    # Determine primary party
    if dem_pct > 60:
        party_dominant = "Democratic"
    elif rep_pct > 60:
        party_dominant = "Republican"
    elif dem_pct > rep_pct:
        party_dominant = "Democratic-leaning"
    elif rep_pct > dem_pct:
        party_dominant = "Republican-leaning"
    else:
        party_dominant = "Bipartisan"
    
    # Analyze caucus composition
    caucus_indicators = []
    if badge_counts.get('fc', 0) > 0:
        caucus_indicators.append("Freedom Caucus")
    if badge_counts.get('pc', 0) > 0:
        caucus_indicators.append("Progressive")
    if badge_counts.get('bd', 0) > 0:
        caucus_indicators.append("Blue Dog")
    if badge_counts.get('maga', 0) > 0:
        caucus_indicators.append("MAGA")
    if badge_counts.get('cbc', 0) > 0:
        caucus_indicators.append("CBC")
    if badge_counts.get('tb', 0) > 0:
        caucus_indicators.append("True Blue")
    
    # Analyze policy areas (top 3)
    policy_areas = [pa['name'] for pa in pa_pos[:3] if pa['score'] > 0.1]
    
    # Analyze subject terms (top 3)
    subject_terms = [st['name'] for st in st_pos[:3] if st['score'] > 0.1]
    
    # Analyze voting behavior from anchor roll calls
    voting_behavior = []
    if top_rc:
        avg_delta = sum(rc[1] for rc in top_rc[:3]) / min(3, len(top_rc))
        if avg_delta > 0.3:
            voting_behavior.append("highly cohesive")
        elif avg_delta > 0.2:
            voting_behavior.append("cohesive")
        else:
            voting_behavior.append("moderately cohesive")
    
    # Analyze geographic concentration
    if states:
        top_state_count = max(states.values())
        state_concentration = top_state_count / total_members if total_members > 0 else 0
        if state_concentration > 0.3:
            top_states = sorted(states.items(), key=lambda x: x[1], reverse=True)[:2]
            voting_behavior.append(f"geographically concentrated in {', '.join([s[0] for s in top_states])}")
    
    # Build description components
    description_parts = []
    
    # Size and party
    description_parts.append(f"{party_dominant} cluster of {size} members")
    
    # Caucus composition
    if caucus_indicators:
        if len(caucus_indicators) == 1:
            description_parts.append(f"with {caucus_indicators[0]} representation")
        else:
            description_parts.append(f"with {', '.join(caucus_indicators[:2])} representation")
    
    # Policy focus
    if policy_areas:
        if len(policy_areas) == 1:
            description_parts.append(f"focused on {policy_areas[0]}")
        else:
            description_parts.append(f"focused on {policy_areas[0]} and {policy_areas[1]}")
    
    # Subject focus (if different from policy areas)
    if subject_terms and not any(st in ' '.join(policy_areas).lower() for st in subject_terms):
        description_parts.append(f"with emphasis on {subject_terms[0]}")
    
    # Voting behavior
    if voting_behavior:
        description_parts.append(f"({', '.join(voting_behavior)})")
    
    # Combine into final description
    description = " ".join(description_parts)
    
    # Ensure description isn't too long
    if len(description) > 120:
        # Truncate but keep it meaningful
        words = description.split()
        truncated = []
        char_count = 0
        for word in words:
            if char_count + len(word) + 1 > 120:
                break
            truncated.append(word)
            char_count += len(word) + 1
        description = " ".join(truncated) + "..."
    
    return description

@app.route('/api/clusters/summary')
def api_clusters_summary():
    """Summarize clusters: size/party/caucus, SVD means, anchor roll calls, exemplars.

    Params: congress, chamber, rc_limit (optional), min_votes (default 5), exclude_procedural,
    scope, subject, k (required).
    """
    if not _SKLEARN_AVAILABLE:
        return jsonify({'error': 'scikit-learn not available in this runtime'}), 500
    try:
        congress = int(request.args.get('congress', 119))
        chamber = request.args.get('chamber', 'house')
        rc_limit_param = request.args.get('rc_limit')
        rc_limit = int(rc_limit_param) if rc_limit_param is not None else None
        min_votes = int(request.args.get('min_votes', 5))
        exclude_procedural = _is_truthy(request.args.get('exclude_procedural', 'true'))
        scope = request.args.get('scope')
        subject_param = request.args.get('subject')
        subjects = [s.strip() for s in subject_param.split(',')] if subject_param else []
        k = int(request.args.get('k', 5))

        with get_db_session() as session:
            # Rollcalls + bill meta
            rc_q = (
                session.query(
                    Rollcall.rollcall_id,
                    Rollcall.date,
                    Rollcall.question,
                    Rollcall.bill_id,
                    Bill.title,
                    Bill.policy_area,
                )
                .join(Bill, Rollcall.bill_id == Bill.bill_id)
                .filter(Rollcall.congress == congress, Rollcall.chamber == chamber)
                .filter(Bill.congress == congress, Bill.chamber == chamber)
                .filter(Bill.bill_id.like(f"%-{congress}"))
            )
            if subjects and scope in ('policy_area', 'subject_term'):
                if scope == 'policy_area':
                    rc_q = rc_q.filter(Bill.policy_area.in_(subjects))
                else:
                    rc_q = rc_q.join(BillSubject, BillSubject.bill_id == Bill.bill_id).filter(BillSubject.subject_term.in_(subjects))
            rc_q = rc_q.order_by(Rollcall.date.desc())
            if rc_limit:
                rc_q = rc_q.limit(rc_limit)
            rc_rows = rc_q.all()
            if not rc_rows:
                return jsonify({'error': 'No roll calls found for scope'}), 404
            rc_ids_all = [r.rollcall_id for r in rc_rows]
            rc_meta = {r.rollcall_id: {
                'rollcall_id': r.rollcall_id,
                'date': r.date.isoformat() if r.date else None,
                'question': r.question,
                'bill_id': r.bill_id,
                'title': r.title,
                'policy_area': r.policy_area,
            } for r in rc_rows}

            # Votes
            vq = session.query(Vote.rollcall_id, Vote.member_id_bioguide, Vote.vote_code) \
                     .join(Rollcall, Vote.rollcall_id == Rollcall.rollcall_id) \
                     .join(Member, Vote.member_id_bioguide == Member.member_id_bioguide) \
                     .filter(Vote.rollcall_id.in_(rc_ids_all)) \
                     .filter(Vote.vote_code.in_(['Yea','Nay']))
            if chamber == 'house':
                vq = vq.filter(Member.district.isnot(None))
            if exclude_procedural:
                vq = vq.filter(
                    or_(
                        Rollcall.question.is_(None),
                        and_(
                            ~Rollcall.question.ilike('%rule%'),
                            ~Rollcall.question.ilike('%previous question%'),
                            ~Rollcall.question.ilike('%recommit%'),
                            ~Rollcall.question.ilike('%motion to table%'),
                            ~Rollcall.question.ilike('%quorum%'),
                            ~Rollcall.question.ilike('%adjourn%'),
                            ~Rollcall.question.ilike('%suspend the rules%')
                        )
                    )
                )
            votes_rows = vq.all()

            # Members meta
            mem_rows = session.query(
                Member.member_id_bioguide, Member.first, Member.last, Member.party, Member.state
            ).filter(
                Member.district.isnot(None) if chamber == 'house' else Member.district.is_(None)
            ).all()
            mem_meta = {m.member_id_bioguide: {
                'name': f"{m.first or ''} {m.last or ''}".strip(),
                'party': m.party,
                'state': m.state
            } for m in mem_rows}

            # Preload subject terms for these bills
            bill_ids_for_subjects = [m['bill_id'] for m in rc_meta.values() if m.get('bill_id')]
            subj_map = {}
            if bill_ids_for_subjects:
                subj_rows = session.query(BillSubject.bill_id, BillSubject.subject_term) \
                                  .filter(BillSubject.bill_id.in_(bill_ids_for_subjects)).all()
                for b_id, term in subj_rows:
                    if term:
                        subj_map.setdefault(b_id, []).append(term)

        # Build matrix
        rc_index = {rc_id: i for i, rc_id in enumerate(rc_ids_all)}
        member_ids = sorted({row.member_id_bioguide for row in votes_rows if row.member_id_bioguide in mem_meta})
        if not member_ids:
            return jsonify({'error': 'No member votes found'}), 404
        mem_index = {mid: i for i, mid in enumerate(member_ids)}
        M = np.zeros((len(member_ids), len(rc_ids_all)), dtype=np.float32)
        counts = np.zeros(len(member_ids), dtype=np.int32)
        for rc_id, mid, code in votes_rows:
            i = mem_index.get(mid)
            j = rc_index.get(rc_id)
            if i is None or j is None:
                continue
            M[i, j] = 1.0 if code == 'Yea' else -1.0
            counts[i] += 1
        keep = counts >= min_votes
        if not np.any(keep):
            return jsonify({'error': 'No members meet min_votes threshold'}), 400
        M = M[keep]
        kept_member_ids = [mid for mid in member_ids if keep[mem_index[mid]]]
        # Drop empty columns
        nonzero_cols_mask = (M != 0).any(axis=0)
        if not np.any(nonzero_cols_mask):
            return jsonify({'error': 'No usable roll calls after filters'}), 400
        kept_rc_ids = [rc for rc, m in zip(rc_ids_all, nonzero_cols_mask) if m]
        M = M[:, nonzero_cols_mask]
        # Center
        row_sums = M.sum(axis=1, keepdims=True)
        row_counts = (M != 0).sum(axis=1, keepdims=True)
        with np.errstate(invalid='ignore', divide='ignore'):
            row_means = np.divide(row_sums, row_counts, out=np.zeros_like(row_sums), where=row_counts!=0)
        M_centered = np.nan_to_num(M - row_means, nan=0.0)

        max_rank = int(min(M_centered.shape) - 1)
        if max_rank < 2:
            return jsonify({'error': 'Insufficient variation for SVD'}), 400
        comps = min(10, max_rank)
        svd = TruncatedSVD(n_components=comps, random_state=42)
        Z = svd.fit_transform(M_centered)

        # Cluster
        n_samples = Z.shape[0]
        if n_samples < 2:
            return jsonify({'error': 'Not enough members to cluster', 'detail': {'n_samples': int(n_samples)}}), 400
        k = max(2, min(k, n_samples))
        km = KMeans(n_clusters=k, n_init=10, random_state=42)
        labels = km.fit_predict(Z)

        # Cluster summaries
        caucus_data = load_caucus_data()
        clusters = []
        for cid in range(k):
            idx = [i for i, lab in enumerate(labels) if lab == cid]
            size = len(idx)
            parts = {'D': 0, 'R': 0, 'other': 0}
            states = {}
            badge_counts = {'fc':0,'pc':0,'bd':0,'maga':0,'cbc':0,'tb':0}
            for i in idx:
                mid = kept_member_ids[i]
                p = (mem_meta.get(mid, {}).get('party') or '')
                key = 'D' if p.upper().startswith('D') else 'R' if p.upper().startswith('R') else 'other'
                parts[key] += 1
                st = mem_meta.get(mid, {}).get('state')
                if st:
                    states[st] = states.get(st, 0) + 1
                # badges
                if mid in caucus_data.get('freedom_caucus', set()): badge_counts['fc'] += 1
                if mid in caucus_data.get('progressive_caucus', set()): badge_counts['pc'] += 1
                if mid in caucus_data.get('blue_dog_coalition', set()): badge_counts['bd'] += 1
                if mid in caucus_data.get('maga_republicans', set()): badge_counts['maga'] += 1
                if mid in caucus_data.get('congressional_black_caucus', set()): badge_counts['cbc'] += 1
                if mid in caucus_data.get('true_blue_democrats', set()): badge_counts['tb'] += 1

            # SVD means (first 3 components if available)
            Zc = Z[idx]
            means = {'x': float(Zc[:,0].mean()) if Zc.shape[1] >=1 else 0.0,
                     'y': float(Zc[:,1].mean()) if Zc.shape[1] >=2 else 0.0,
                     'z': float(Zc[:,2].mean()) if Zc.shape[1] >=3 else None}

            # Anchor roll calls: largest |Δ Yea%| vs others
            # compute per RC yea counts for cluster and others
            # Re-fetch votes for efficiency could be heavy; we can iterate over votes_rows
            rc_counts = {rc: {'in_yea':0,'in_tot':0,'out_yea':0,'out_tot':0} for rc in kept_rc_ids}
            # map kept_member_ids index to cluster membership quickly
            in_cluster = set(idx)
            # Build map of member index by id for quick checks
            mid_to_i = {mid: i for i, mid in enumerate(kept_member_ids)}
            for rc_id, mid, code in votes_rows:
                if rc_id not in rc_counts:
                    continue
                i = mid_to_i.get(mid)
                if i is None:
                    continue
                inc = i in in_cluster
                key_yea = 'in_yea' if inc else 'out_yea'
                key_tot = 'in_tot' if inc else 'out_tot'
                if code in ('Yea','Nay'):
                    rc_counts[rc_id][key_tot] += 1
                    if code == 'Yea':
                        rc_counts[rc_id][key_yea] += 1
            deltas = []
            for rc, cts in rc_counts.items():
                if cts['in_tot'] >= 10 and cts['out_tot'] >= 10:  # min sample
                    in_pct = cts['in_yea']/cts['in_tot'] if cts['in_tot'] else 0
                    out_pct = cts['out_yea']/cts['out_tot'] if cts['out_tot'] else 0
                    deltas.append((rc, abs(in_pct - out_pct), in_pct, out_pct))
            deltas.sort(key=lambda x: x[1], reverse=True)
            top_rc = deltas[:8]
            # Subject enrichment: compare in-cluster vs out-of-cluster vote volume by policy area and subject term
            in_total_votes = sum(cts['in_tot'] for cts in rc_counts.values())
            out_total_votes = sum(cts['out_tot'] for cts in rc_counts.values())
            pa_in, pa_out = {}, {}
            st_in, st_out = {}, {}
            for rc, cts in rc_counts.items():
                meta = rc_meta.get(rc, {})
                pa = meta.get('policy_area')
                if pa:
                    pa_in[pa] = pa_in.get(pa, 0) + cts['in_tot']
                    pa_out[pa] = pa_out.get(pa, 0) + cts['out_tot']
                b_id = meta.get('bill_id')
                if b_id:
                    for term in subj_map.get(b_id, []):
                        st_in[term] = st_in.get(term, 0) + cts['in_tot']
                        st_out[term] = st_out.get(term, 0) + cts['out_tot']
            import math as _math
            def top_scores(in_map, out_map, in_tot, out_tot, limit=6):
                scores = []
                for key in set(list(in_map.keys()) + list(out_map.keys())):
                    a = in_map.get(key, 0)
                    b = out_map.get(key, 0)
                    # log-odds style contrast with +1 smoothing
                    s = _math.log((a + 1) / (in_tot + 1)) - _math.log((b + 1) / (out_tot + 1))
                    scores.append((key, s))
                scores.sort(key=lambda x: x[1], reverse=True)
                pos = [{'name': k or '(Unknown)', 'score': round(float(s), 3)} for k, s in scores[:limit]]
                neg = [{'name': k or '(Unknown)', 'score': round(float(s), 3)} for k, s in scores[-limit:][::-1]]
                return pos, neg
            pa_pos, pa_neg = top_scores(pa_in, pa_out, in_total_votes, out_total_votes)
            st_pos, st_neg = top_scores(st_in, st_out, in_total_votes, out_total_votes)
            
            # Generate nuanced cluster description
            cluster_description = generate_cluster_description(
                cid, size, parts, states, badge_counts, pa_pos, st_pos, 
                top_rc, means, in_total_votes, out_total_votes
            )
            # decorate rc details
            def rc_rows(lst):
                out = []
                for rc, d, in_p, out_p in lst:
                    m = rc_meta.get(rc, {})
                    out.append({
                        'rollcall_id': rc,
                        'delta': round(float(d),3),
                        'in_yea_pct': round(float(in_p*100),1),
                        'out_yea_pct': round(float(out_p*100),1),
                        'question': m.get('question'),
                        'date': m.get('date'),
                        'bill_id': m.get('bill_id'),
                        'title': m.get('title'),
                        'policy_area': m.get('policy_area')
                    })
                return out

            # Exemplars (closest to centroid) and edge (farthest)
            centroid = Zc.mean(axis=0)
            from numpy.linalg import norm as _norm
            dists = [(_norm(Z[i]-centroid), i) for i in idx]
            dists.sort()
            exemplars = [{
                'id': kept_member_ids[i],
                'name': mem_meta.get(kept_member_ids[i], {}).get('name', kept_member_ids[i]),
                'party': mem_meta.get(kept_member_ids[i], {}).get('party')
            } for _, i in dists[:5]]
            edges = [{
                'id': kept_member_ids[i],
                'name': mem_meta.get(kept_member_ids[i], {}).get('name', kept_member_ids[i]),
                'party': mem_meta.get(kept_member_ids[i], {}).get('party')
            } for _, i in dists[-5:]]

            top_states = sorted(states.items(), key=lambda x: x[1], reverse=True)[:5]
            clusters.append({
                'id': cid,
                'size': size,
                'party': parts,
                'caucuses': badge_counts,
                'svd_means': means,
                'anchor_rollcalls': rc_rows(top_rc),
                'policy_area_pos': pa_pos,
                'policy_area_neg': pa_neg,
                'subject_term_pos': st_pos,
                'subject_term_neg': st_neg,
                'exemplars': exemplars,
                'edge_members': edges,
                'top_states': [{'state': s, 'count': c} for s,c in top_states],
                'description': cluster_description
            })

        return jsonify({'clusters': clusters, 'k': k})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/subjects/bills')
def subjects_bills_page():
    """List bills with votes for a given subject.

    Query params: subject (required), scope=policy_area|subject_term, congress=119,
    chamber=house, exclude_procedural=true|false
    """
    try:
        subject = request.args.get('subject')
        if not subject:
            return f"Error: missing subject", 400
        scope = request.args.get('scope', 'policy_area')
        congress = int(request.args.get('congress', 119))
        chamber = request.args.get('chamber', 'house')
        exclude_procedural = _is_truthy(request.args.get('exclude_procedural', 'true'))

        if scope not in ('policy_area', 'subject_term'):
            scope = 'policy_area'

        with get_db_session() as session:
            join_subject = ''
            where_subject = ''
            if scope == 'policy_area':
                where_subject = ' AND b.policy_area = :subject'
            else:
                join_subject = ' JOIN bill_subjects s ON s.bill_id = b.bill_id'
                where_subject = ' AND s.subject_term = :subject'

            procedural_filter = ''
            if exclude_procedural:
                procedural_filter = (
                    " AND ("
                    " r.question IS NULL OR ("
                    " r.question NOT LIKE '%rule%' AND"
                    " r.question NOT LIKE '%previous question%' AND"
                    " r.question NOT LIKE '%recommit%' AND"
                    " r.question NOT LIKE '%motion to table%' AND"
                    " r.question NOT LIKE '%quorum%' AND"
                    " r.question NOT LIKE '%adjourn%' AND"
                    " r.question NOT LIKE '%suspend the rules%'"
                    ") )"
                )

            query = f"""
                SELECT b.bill_id, b.title, b.policy_area,
                       COUNT(DISTINCT r.rollcall_id) AS rollcall_count
                FROM bills b
                JOIN rollcalls r ON r.bill_id = b.bill_id
                {join_subject}
                WHERE b.congress = :congress
                  AND b.chamber = :chamber
                  AND b.bill_id LIKE CONCAT('%-', :congress)
                  {where_subject}
                  {procedural_filter}
                GROUP BY b.bill_id, b.title, b.policy_area
                HAVING rollcall_count > 0
                ORDER BY rollcall_count DESC, b.title ASC
                LIMIT 500
            """

            rows = session.execute(
                text(query),
                {'subject': subject, 'congress': congress, 'chamber': chamber}
            ).fetchall()

            bills = [{
                'bill_id': row.bill_id,
                'title': row.title,
                'policy_area': row.policy_area,
                'rollcall_count': int(row.rollcall_count or 0)
            } for row in rows]

            return render_template('subject_bills.html',
                                   subject=subject,
                                   scope=scope,
                                   congress=congress,
                                   chamber=chamber,
                                   exclude_procedural=exclude_procedural,
                                   bills=bills)
    except Exception as e:
        return f"Error: {str(e)}", 500

# Bill Status Tracking Endpoints
@app.route('/api/bill/<bill_id>/status')
def get_bill_status(bill_id):
    """Get comprehensive status for a specific bill."""
    try:
        with get_db_session() as session:
            # Get all actions for the bill
            actions_query = """
                SELECT action_code, action_date, text, committee_code
                FROM actions 
                WHERE bill_id = :bill_id
                ORDER BY action_date ASC
            """
            
            actions = session.execute(text(actions_query), {'bill_id': bill_id}).fetchall()
            
            if not actions:
                return jsonify({'error': 'Bill not found or no actions recorded'}), 404
            
            # Get bill basic info
            bill_query = """
                SELECT bill_id, title, congress, chamber, sponsor_bioguide, policy_area
                FROM bills 
                WHERE bill_id = :bill_id
            """
            
            bill = session.execute(text(bill_query), {'bill_id': bill_id}).fetchone()
            
            if not bill:
                return jsonify({'error': 'Bill not found'}), 404
            
            # Determine current status
            action_codes = [action.action_code for action in actions]
            
            if 'ENACTED' in action_codes:
                current_status = 'ENACTED'
            elif 'VETOED' in action_codes:
                current_status = 'VETOED'
            elif 'PASSED_HOUSE' in action_codes and 'PASSED_SENATE' in action_codes:
                current_status = 'PASSED_BOTH_CHAMBERS'
            elif 'PASSED_HOUSE' in action_codes:
                current_status = 'PASSED_HOUSE_ONLY'
            elif 'PASSED_SENATE' in action_codes:
                current_status = 'PASSED_SENATE_ONLY'
            elif 'INTRODUCED' in action_codes:
                current_status = 'INTRODUCED'
            else:
                current_status = 'IN_PROGRESS'
            
            # Get specific action dates
            def get_action_date(action_code):
                for action in actions:
                    if action.action_code == action_code:
                        return action.action_date.isoformat() if action.action_date else None
                return None
            
            status_data = {
                'bill_id': bill_id,
                'title': bill.title,
                'congress': bill.congress,
                'chamber': bill.chamber,
                'sponsor_bioguide': bill.sponsor_bioguide,
                'policy_area': bill.policy_area,
                'status': current_status,
                'actions': [{
                    'action_code': action.action_code,
                    'action_date': action.action_date.isoformat() if action.action_date else None,
                    'text': action.text,
                    'committee_code': action.committee_code
                } for action in actions],
                'introduced_date': get_action_date('INTRODUCED'),
                'house_pass_date': get_action_date('PASSED_HOUSE'),
                'senate_pass_date': get_action_date('PASSED_SENATE'),
                'enacted_date': get_action_date('ENACTED'),
                'vetoed_date': get_action_date('VETOED'),
                'is_law': current_status == 'ENACTED',
                'passed_both_chambers': current_status in ['PASSED_BOTH_CHAMBERS', 'ENACTED']
            }
            
            return jsonify(status_data)
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bills/enacted/<int:congress>')
def get_enacted_bills(congress):
    """Get all bills enacted into law for a Congress."""
    try:
        with get_db_session() as session:
            query = """
                SELECT DISTINCT b.bill_id, b.title, b.sponsor_bioguide, b.policy_area,
                       MAX(CASE WHEN a.action_code = 'ENACTED' THEN a.action_date END) as enacted_date
                FROM bills b
                JOIN actions a ON b.bill_id = a.bill_id
                WHERE b.congress = :congress
                  AND b.chamber = 'house'
                  AND b.bill_id LIKE CONCAT('%-', :congress)
                  AND a.action_code = 'ENACTED'
                GROUP BY b.bill_id
                ORDER BY enacted_date DESC
            """
            
            results = session.execute(text(query), {'congress': congress}).fetchall()
            bills = [{
                'bill_id': result.bill_id,
                'title': result.title,
                'sponsor_bioguide': result.sponsor_bioguide,
                'policy_area': result.policy_area,
                'enacted_date': result.enacted_date.isoformat() if result.enacted_date else None
            } for result in results]
            
            return jsonify(bills)
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bills/passed-both/<int:congress>')
def get_bills_passed_both(congress):
    """Get bills that passed both chambers for a Congress."""
    try:
        with get_db_session() as session:
            query = """
                SELECT DISTINCT b.bill_id, b.title, b.sponsor_bioguide, b.policy_area,
                       MAX(CASE WHEN a.action_code = 'PASSED_HOUSE' THEN a.action_date END) as house_pass_date,
                       MAX(CASE WHEN a.action_code = 'PASSED_SENATE' THEN a.action_date END) as senate_pass_date
                FROM bills b
                JOIN actions a ON b.bill_id = a.bill_id
                 WHERE b.congress = :congress
                  AND b.chamber = 'house'
                  AND b.bill_id LIKE CONCAT('%-', :congress)
                  AND a.action_code IN ('PASSED_HOUSE', 'PASSED_SENATE')
                GROUP BY b.bill_id
                HAVING house_pass_date IS NOT NULL 
                   AND senate_pass_date IS NOT NULL
                ORDER BY house_pass_date DESC
            """
            
            results = session.execute(text(query), {'congress': congress}).fetchall()
            bills = [{
                'bill_id': result.bill_id,
                'title': result.title,
                'sponsor_bioguide': result.sponsor_bioguide,
                'policy_area': result.policy_area,
                'house_pass_date': result.house_pass_date.isoformat() if result.house_pass_date else None,
                'senate_pass_date': result.senate_pass_date.isoformat() if result.senate_pass_date else None
            } for result in results]
            
            return jsonify(bills)
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bills/house-only/<int:congress>')
def get_bills_passed_house_only(congress):
    """Get bills that passed House only for a Congress."""
    try:
        with get_db_session() as session:
            query = """
                SELECT DISTINCT b.bill_id, b.title, b.sponsor_bioguide, b.policy_area,
                       MAX(CASE WHEN a.action_code = 'PASSED_HOUSE' THEN a.action_date END) as house_pass_date
                FROM bills b
                JOIN actions a ON b.bill_id = a.bill_id
                WHERE b.congress = :congress
                  AND b.chamber = 'house'
                  AND b.bill_id LIKE CONCAT('%-', :congress)
                  AND a.action_code = 'PASSED_HOUSE'
                  AND NOT EXISTS (
                      SELECT 1 FROM actions a2 
                      WHERE a2.bill_id = b.bill_id 
                        AND a2.action_code = 'PASSED_SENATE'
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM actions a3 
                      WHERE a3.bill_id = b.bill_id 
                        AND a3.action_code = 'ENACTED'
                  )
                GROUP BY b.bill_id
                ORDER BY house_pass_date DESC
            """
            
            results = session.execute(text(query), {'congress': congress}).fetchall()
            bills = [{
                'bill_id': result.bill_id,
                'title': result.title,
                'sponsor_bioguide': result.sponsor_bioguide,
                'policy_area': result.policy_area,
                'house_pass_date': result.house_pass_date.isoformat() if result.house_pass_date else None
            } for result in results]
            
            return jsonify(bills)
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bills/in-progress/<int:congress>')
def get_bills_in_progress(congress):
    """Get bills that are in progress (not passed, enacted, or vetoed) for a Congress."""
    try:
        with get_db_session() as session:
            query = """
                SELECT DISTINCT b.bill_id, b.title, b.sponsor_bioguide, b.policy_area, b.introduced_date
                FROM bills b
                WHERE b.congress = :congress
                  AND b.chamber = 'house'
                  AND b.bill_id LIKE CONCAT('%-', :congress)
                  AND NOT EXISTS (
                      SELECT 1 FROM actions a 
                      WHERE a.bill_id = b.bill_id 
                        AND a.action_code IN ('ENACTED', 'VETOED', 'PASSED_HOUSE', 'PASSED_SENATE')
                  )
                ORDER BY b.introduced_date DESC
                LIMIT 100
            """
            
            results = session.execute(text(query), {'congress': congress}).fetchall()
            bills = [{
                'bill_id': result.bill_id,
                'title': result.title,
                'sponsor_bioguide': result.sponsor_bioguide,
                'policy_area': result.policy_area,
                'introduced_date': result.introduced_date.isoformat() if result.introduced_date else None
            } for result in results]
            
            return jsonify(bills)
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# HTML page route for in-progress bills
@app.route('/bills/in-progress/<int:congress>')
def bills_in_progress_page(congress):
    """HTML page showing bills that are still in progress."""
    try:
        with get_db_session() as session:
            query = """
                SELECT DISTINCT b.bill_id, b.title, b.sponsor_bioguide, b.policy_area, b.introduced_date
                FROM bills b
                WHERE b.congress = :congress
                  AND b.chamber = 'house'
                  AND b.bill_id LIKE CONCAT('%-', :congress)
                  AND NOT EXISTS (
                      SELECT 1 FROM actions a 
                      WHERE a.bill_id = b.bill_id 
                        AND a.action_code IN ('ENACTED', 'VETOED', 'PASSED_HOUSE', 'PASSED_SENATE')
                  )
                ORDER BY b.introduced_date DESC
                LIMIT 100
            """
            results = session.execute(text(query), {'congress': congress}).fetchall()
            bills = [{
                'bill_id': result.bill_id,
                'title': result.title,
                'sponsor_bioguide': result.sponsor_bioguide,
                'policy_area': result.policy_area,
                'introduced_date': result.introduced_date.isoformat() if result.introduced_date else None,
                # Ensure template fields exist (None if not applicable)
                'house_pass_date': None,
                'senate_pass_date': None,
                'enacted_date': None
            } for result in results]
            return render_template('bills_list.html',
                                   title='Bills In Progress',
                                   subtitle='Not yet passed, enacted, or vetoed',
                                   bills=bills,
                                   congress=congress)
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/api/bills/total-passed-both/<int:congress>')
def get_bills_total_passed_both(congress):
    """Get all bills that passed both chambers (enacted + not enacted) for a Congress."""
    try:
        with get_db_session() as session:
            query = """
                SELECT DISTINCT b.bill_id, b.title, b.sponsor_bioguide, b.policy_area,
                       MAX(CASE WHEN a.action_code = 'PASSED_HOUSE' THEN a.action_date END) as house_pass_date,
                       MAX(CASE WHEN a.action_code = 'PASSED_SENATE' THEN a.action_date END) as senate_pass_date,
                       MAX(CASE WHEN a.action_code = 'ENACTED' THEN a.action_date END) as enacted_date
                FROM bills b
                JOIN actions a ON b.bill_id = a.bill_id
                 WHERE b.congress = :congress
                  AND b.chamber = 'house'
                  AND b.bill_id LIKE CONCAT('%-', :congress)
                  AND a.action_code IN ('PASSED_HOUSE', 'PASSED_SENATE')
                GROUP BY b.bill_id
                HAVING house_pass_date IS NOT NULL 
                   AND senate_pass_date IS NOT NULL
                ORDER BY enacted_date DESC NULLS LAST, house_pass_date DESC
            """
            
            results = session.execute(text(query), {'congress': congress}).fetchall()
            bills = [{
                'bill_id': result.bill_id,
                'title': result.title,
                'sponsor_bioguide': result.sponsor_bioguide,
                'policy_area': result.policy_area,
                'house_pass_date': result.house_pass_date.isoformat() if result.house_pass_date else None,
                'house_pass_date': result.house_pass_date.isoformat() if result.house_pass_date else None,
                'senate_pass_date': result.senate_pass_date.isoformat() if result.senate_pass_date else None,
                'enacted_date': result.enacted_date.isoformat() if result.enacted_date else None
            } for result in results]
            
            return jsonify(bills)
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# HTML page routes for bill lists
@app.route('/bills/enacted/<int:congress>')
def bills_enacted_page(congress):
    """HTML page showing enacted bills."""
    try:
        with get_db_session() as session:
            query = """
                SELECT DISTINCT b.bill_id, b.title, b.sponsor_bioguide, b.policy_area,
                       MAX(CASE WHEN a.action_code = 'ENACTED' THEN a.action_date END) as enacted_date
                FROM bills b
                JOIN actions a ON b.bill_id = a.bill_id
                WHERE b.congress = :congress
                  AND b.chamber = 'house'
                  AND b.bill_id LIKE CONCAT('%-', :congress)
                  AND a.action_code = 'ENACTED'
                GROUP BY b.bill_id
                ORDER BY enacted_date DESC
            """
            
            results = session.execute(text(query), {'congress': congress}).fetchall()
            bills = [{
                'bill_id': result.bill_id,
                'title': result.title,
                'sponsor_bioguide': result.sponsor_bioguide,
                'policy_area': result.policy_area,
                'enacted_date': result.enacted_date.isoformat() if result.enacted_date else None
            } for result in results]
            
            return render_template('bills_list.html', 
                                title='Enacted Bills',
                                subtitle='Bills signed into law',
                                bills=bills,
                                congress=congress)
            
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/bills/passed-both/<int:congress>')
def bills_passed_both_page(congress):
    """HTML page showing bills passed both chambers (not enacted)."""
    try:
        with get_db_session() as session:
            query = """
                SELECT DISTINCT b.bill_id, b.title, b.sponsor_bioguide, b.policy_area,
                       MAX(CASE WHEN a.action_code = 'PASSED_HOUSE' THEN a.action_date END) as house_pass_date,
                       MAX(CASE WHEN a.action_code = 'PASSED_SENATE' THEN a.action_date END) as senate_pass_date
                FROM bills b
                JOIN actions a ON b.bill_id = a.bill_id
                 WHERE b.congress = :congress
                  AND b.chamber = 'house'
                  AND b.bill_id LIKE CONCAT('%-', :congress)
                  AND a.action_code IN ('PASSED_HOUSE', 'PASSED_SENATE')
                GROUP BY b.bill_id
                HAVING house_pass_date IS NOT NULL 
                   AND senate_pass_date IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM actions a2 
                      WHERE a2.bill_id = b.bill_id 
                        AND a2.action_code = 'ENACTED'
                  )
                ORDER BY house_pass_date DESC
            """
            
            results = session.execute(text(query), {'congress': congress}).fetchall()
            bills = [{
                'bill_id': result.bill_id,
                'title': result.title,
                'sponsor_bioguide': result.sponsor_bioguide,
                'policy_area': result.policy_area,
                'house_pass_date': result.house_pass_date.isoformat() if result.house_pass_date else None,
                'senate_pass_date': result.senate_pass_date.isoformat() if result.senate_pass_date else None
            } for result in results]
            
            return render_template('bills_list.html', 
                                title='Bills Passed Both Chambers',
                                subtitle='Awaiting presidential action',
                                bills=bills,
                                congress=congress,
                                show_conres_note=True)
            
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/bills/house-only/<int:congress>')
def bills_house_only_page(congress):
    """HTML page showing bills passed House only."""
    try:
        with get_db_session() as session:
            query = """
                SELECT DISTINCT b.bill_id, b.title, b.sponsor_bioguide, b.policy_area,
                       MAX(CASE WHEN a.action_code = 'PASSED_HOUSE' THEN a.action_date END) as house_pass_date
                FROM bills b
                JOIN actions a ON b.bill_id = a.bill_id
                WHERE b.congress = :congress
                  AND b.chamber = 'house'
                  AND b.bill_id LIKE CONCAT('%-', :congress)
                  AND a.action_code = 'PASSED_HOUSE'
                  AND NOT EXISTS (
                      SELECT 1 FROM actions a2 
                      WHERE a2.bill_id = b.bill_id 
                        AND a2.action_code = 'PASSED_SENATE'
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM actions a3 
                      WHERE a3.bill_id = b.bill_id 
                        AND a3.action_code = 'ENACTED'
                  )
                GROUP BY b.bill_id
                ORDER BY house_pass_date DESC
            """
            
            results = session.execute(text(query), {'congress': congress}).fetchall()
            bills = [{
                'bill_id': result.bill_id,
                'title': result.title,
                'sponsor_bioguide': result.sponsor_bioguide,
                'policy_area': result.policy_area,
                'house_pass_date': result.house_pass_date.isoformat() if result.house_pass_date else None
            } for result in results]
            
            return render_template('bills_list.html', 
                                title='Bills Passed House Only',
                                subtitle='Awaiting Senate action',
                                bills=bills,
                                congress=congress)
            
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/bills/total-passed-both/<int:congress>')
def bills_total_passed_both_page(congress):
    """HTML page showing all bills that passed both chambers."""
    try:
        with get_db_session() as session:
            query = """
                SELECT DISTINCT b.bill_id, b.title, b.sponsor_bioguide, b.policy_area,
                       MAX(CASE WHEN a.action_code = 'PASSED_HOUSE' THEN a.action_date END) as house_pass_date,
                       MAX(CASE WHEN a.action_code = 'PASSED_SENATE' THEN a.action_date END) as senate_pass_date,
                       MAX(CASE WHEN a.action_code = 'ENACTED' THEN a.action_date END) as enacted_date
                FROM bills b
                JOIN actions a ON b.bill_id = a.bill_id
                 WHERE b.congress = :congress
                  AND b.chamber = 'house'
                  AND b.bill_id LIKE CONCAT('%-', :congress)
                  AND a.action_code IN ('PASSED_HOUSE', 'PASSED_SENATE')
                GROUP BY b.bill_id
                HAVING house_pass_date IS NOT NULL 
                   AND senate_pass_date IS NOT NULL
                ORDER BY enacted_date DESC NULLS LAST, house_pass_date DESC
            """
            
            results = session.execute(text(query), {'congress': congress}).fetchall()
            bills = [{
                'bill_id': result.bill_id,
                'title': result.title,
                'sponsor_bioguide': result.sponsor_bioguide,
                'policy_area': result.policy_area,
                'house_pass_date': result.house_pass_date.isoformat() if result.house_pass_date else None,
                'senate_pass_date': result.senate_pass_date.isoformat() if result.senate_pass_date else None,
                'enacted_date': result.enacted_date.isoformat() if result.enacted_date else None
            } for result in results]
            
            return render_template('bills_list.html', 
                                title='All Bills Passed Both Chambers',
                                subtitle='Enacted + Pending presidential action',
                                bills=bills,
                                congress=congress,
                                show_conres_note=True)
            
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/api/bills/status-summary/<int:congress>')
def get_bills_status_summary(congress):
    """Get summary of bill statuses for a Congress."""
    try:
        with get_db_session() as session:
            query = """
                SELECT bill_status, COUNT(*) as bill_count
                FROM (
                    SELECT 
                        CASE 
                            WHEN MAX(CASE WHEN a.action_code = 'ENACTED' THEN 1 END) = 1 THEN 'ENACTED'
                            WHEN MAX(CASE WHEN a.action_code = 'VETOED' THEN 1 END) = 1 THEN 'VETOED'
                            WHEN MAX(CASE WHEN a.action_code = 'PASSED_HOUSE' THEN 1 END) = 1 
                                 AND MAX(CASE WHEN a.action_code = 'PASSED_SENATE' THEN 1 END) = 1 THEN 'PASSED_BOTH_CHAMBERS'
                            WHEN MAX(CASE WHEN a.action_code = 'PASSED_HOUSE' THEN 1 END) = 1 THEN 'PASSED_HOUSE_ONLY'
                            ELSE 'IN_PROGRESS'
                        END as bill_status
                    FROM bills b
                    LEFT JOIN actions a ON b.bill_id = a.bill_id
                    WHERE b.congress = :congress
                      AND b.chamber = 'house'
                      AND b.bill_id LIKE CONCAT('%-', :congress)
                    GROUP BY b.bill_id
                ) as status_subquery
                GROUP BY bill_status
                ORDER BY bill_count DESC
            """
            
            results = session.execute(text(query), {'congress': congress}).fetchall()
            summary = [{'bill_status': result.bill_status, 'bill_count': result.bill_count} for result in results]
            
            # Add total passed both chambers count (exclude H.Con.Res. by relying on adjusted PASSED_BOTH_CHAMBERS)
            total_passed_both = 0
            for item in summary:
                if item['bill_status'] in ['ENACTED', 'PASSED_BOTH_CHAMBERS']:
                    total_passed_both += item['bill_count']
            
            # Add the total to the summary
            summary.append({
                'bill_status': 'TOTAL_PASSED_BOTH_CHAMBERS',
                'bill_count': total_passed_both
            })
            
            return jsonify(summary)
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/bill-status-test/<int:congress>')
def debug_bill_status_test(congress):
    """Debug endpoint to test bill status logic on a few bills."""
    try:
        with get_db_session() as session:
            # Test with a few bills to see what's happening
            query = """
                SELECT b.bill_id,
                       MAX(CASE WHEN a.action_code = 'ENACTED' THEN 1 END) as has_enacted,
                       MAX(CASE WHEN a.action_code = 'PASSED_HOUSE' THEN 1 END) as has_passed_house,
                       MAX(CASE WHEN a.action_code = 'PASSED_SENATE' THEN 1 END) as has_passed_senate,
                       CASE 
                           WHEN MAX(CASE WHEN a.action_code = 'ENACTED' THEN 1 END) = 1 THEN 'ENACTED'
                           WHEN MAX(CASE WHEN a.action_code = 'VETOED' THEN 1 END) = 1 THEN 'VETOED'
                           WHEN MAX(CASE WHEN a.action_code = 'PASSED_HOUSE' THEN 1 END) = 1 
                                AND MAX(CASE WHEN a.action_code = 'PASSED_SENATE' THEN 1 END) = 1 THEN 'PASSED_BOTH_CHAMBERS'
                           WHEN MAX(CASE WHEN a.action_code = 'PASSED_HOUSE' THEN 1 END) = 1 THEN 'PASSED_HOUSE_ONLY'
                           ELSE 'IN_PROGRESS'
                       END as calculated_status
                FROM bills b
                LEFT JOIN actions a ON b.bill_id = a.bill_id
                WHERE b.congress = :congress
                  AND (a.action_code IN ('ENACTED', 'PASSED_HOUSE', 'PASSED_SENATE') OR a.action_code IS NULL)
                GROUP BY b.bill_id
                HAVING has_enacted = 1 OR has_passed_house = 1 OR has_passed_senate = 1
                ORDER BY has_enacted DESC, has_passed_house DESC, has_passed_senate DESC
                LIMIT 10
            """
            
            results = session.execute(text(query), {'congress': congress}).fetchall()
            debug_data = [{
                'bill_id': result.bill_id,
                'has_enacted': result.has_enacted,
                'has_passed_house': result.has_passed_house,
                'has_passed_senate': result.has_passed_senate,
                'calculated_status': result.calculated_status
            } for result in results]
            
            return jsonify(debug_data)
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/bills-needing-updates/<int:congress>')
def debug_bills_needing_updates(congress):
    """Debug endpoint to see which bills need updates."""
    try:
        with get_db_session() as session:
            query = """
                SELECT bill_id, last_updated, policy_area, sponsor_bioguide 
                FROM bills 
                WHERE congress = :congress 
                AND chamber = 'house'
                AND (policy_area IS NULL OR sponsor_bioguide IS NULL OR last_updated IS NULL OR last_updated < DATE_SUB(NOW(), INTERVAL 7 DAY))
                ORDER BY bill_id ASC
                LIMIT 20
            """
            
            results = session.execute(text(query), {'congress': congress}).fetchall()
            debug_data = [{
                'bill_id': result.bill_id,
                'last_updated': result.last_updated.isoformat() if result.last_updated else None,
                'policy_area': result.policy_area,
                'sponsor_bioguide': result.sponsor_bioguide
            } for result in results]
            
            return jsonify(debug_data)
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Allow overriding host/port via environment for local dev without touching prod defaults
    host = os.environ.get('HOST') or os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.environ.get('PORT') or os.environ.get('FLASK_RUN_PORT', 5000))
    debug_env = os.environ.get('FLASK_DEBUG')
    debug = True if debug_env is None else str(debug_env).lower() in ('1', 'true', 'yes')
    app.run(debug=debug, host=host, port=port)
