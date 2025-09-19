"""
Baseline vote prediction utilities.

Predict each member's probability of voting Yea on a bill given:
- sponsor party
- list of cosponsor bioguide IDs

This is a very simple heuristic baseline intended as a scaffold:
- Start from party-line prior (0.85 for sponsor party, 0.15 for other party)
- Adjust by cosponsor composition: more cross-party cosponsors increase cross-party support

Returned values are probabilities in [0,1] for each member.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from scripts.setup_db import Member, Cosponsor


def compute_cosponsor_party_counts(session: Session, bill_id: str) -> Tuple[int, int, int]:
    """
    Count cosponsors by party for a given bill_id.

    Returns: (num_dem, num_rep, num_ind)
    """
    cosponsors = session.query(Cosponsor).filter(Cosponsor.bill_id == bill_id).all()
    num_dem = 0
    num_rep = 0
    num_ind = 0
    if not cosponsors:
        return (0, 0, 0)
    member_party_cache: Dict[str, str] = {}
    for c in cosponsors:
        if c.member_id_bioguide in member_party_cache:
            party = member_party_cache[c.member_id_bioguide]
        else:
            m = session.query(Member).filter(Member.member_id_bioguide == c.member_id_bioguide).first()
            party = (m.party if m else None) or ''
            member_party_cache[c.member_id_bioguide] = party
        p = (party or '').upper()
        if p == 'D':
            num_dem += 1
        elif p == 'R':
            num_rep += 1
        else:
            num_ind += 1
    return (num_dem, num_rep, num_ind)


def predict_member_vote_probability(
    member_party: Optional[str],
    sponsor_party: Optional[str],
    cosponsor_counts: Tuple[int, int, int],
    is_sponsor: bool = False,
    is_cosponsor: bool = False
) -> float:
    """
    Simple probability model:
    - Base prior: if member party equals sponsor party → 0.85 else 0.15
    - Adjustment from cosponsors:
      Let cross_party_share be the share of cosponsors from the opposite party.
      Shift probability by 0.3 * (cross_party_share - 0.5) toward cross-party.
    - Clamp to [0.02, 0.98] to avoid extremes.
    """
    if not sponsor_party or not member_party:
        # Unknown party info → neutral baseline
        base = 0.5
    else:
        sp = sponsor_party.upper()
        mp = member_party.upper()
        base = 0.85 if sp == mp else 0.15

    num_dem, num_rep, num_ind = cosponsor_counts
    total = max(num_dem + num_rep + num_ind, 0)
    if total == 0:
        return max(0.02, min(0.98, base))

    # Compute cross-party share relative to sponsor party
    sp = (sponsor_party or '').upper()
    if sp == 'D':
        cross_party = num_rep
    elif sp == 'R':
        cross_party = num_dem
    else:
        # If sponsor independent/unknown, use balance between D and R
        cross_party = min(num_dem, num_rep)
    cross_party_share = cross_party / float(total)

    adjustment = 0.3 * (cross_party_share - 0.5)
    # Direct membership boosts
    direct_boost = 0.0
    if is_sponsor:
        direct_boost += 0.1
    if is_cosponsor:
        direct_boost += 0.15

    prob = base + adjustment + direct_boost
    # Same-party floor on strongly partisan bills (few cross-party cosponsors)
    # Compute cross-party share again for the floor logic
    sp = (sponsor_party or '').upper()
    num_dem, num_rep, num_ind = cosponsor_counts
    total = max(num_dem + num_rep + num_ind, 0)
    cross_party = 0
    if sp == 'D':
        cross_party = num_rep
    elif sp == 'R':
        cross_party = num_dem
    cross_party_share = (cross_party / float(total)) if total > 0 else 0.0
    # Strict party-line heuristic when cross-party cosponsors are very low
    if sponsor_party and member_party and cross_party_share <= 0.05:
        if sponsor_party.upper() == member_party.upper():
            # Same-party floor
            prob = max(prob, 0.92 if not is_cosponsor else 0.96)
        else:
            # Opposite-party ceiling; allow cross-party cosponsors to remain higher
            if not is_cosponsor:
                prob = min(prob, 0.08)
    prob = max(0.02, min(0.98, prob))
    return prob


def score_bill_members(
    session: Session,
    bill_id: str,
    chamber: Optional[str] = None
) -> List[Dict[str, object]]:
    """
    Score all active members in the relevant chamber for likelihood of Yea vote.

    Returns list of dicts: {member_id, name, party, state, chamber, probability_yea}
    """
    # Determine sponsor party
    # Join via Bill → Member
    from scripts.setup_db import Bill

    bill = session.query(Bill).filter(Bill.bill_id == bill_id).first()
    if not bill:
        raise ValueError(f"Bill not found: {bill_id}")
    sponsor_party: Optional[str] = None
    if bill.sponsor_bioguide:
        sponsor = session.query(Member).filter(Member.member_id_bioguide == bill.sponsor_bioguide).first()
        sponsor_party = sponsor.party if sponsor else None

    cosponsor_counts = compute_cosponsor_party_counts(session, bill_id)
    cosponsor_ids = set(
        c.member_id_bioguide for c in session.query(Cosponsor).filter(Cosponsor.bill_id == bill_id).all()
    )

    # Member-level cross-party cosponsorship propensity (0..1)
    member_cross_party_propensity = compute_member_cross_party_propensity(session)

    # Issue-based member Yea history on similar bills
    issue_history = compute_issue_based_history(session, bill_id)

    # Select target members: chamber filter if provided or from bill
    target_chamber = (chamber or bill.chamber or '').lower()
    query = session.query(Member)
    if target_chamber == 'house':
        query = query.filter(Member.district.isnot(None))
    elif target_chamber == 'senate':
        query = query.filter(Member.district.is_(None))

    members = query.all()
    results: List[Dict[str, object]] = []
    for m in members:
        is_sponsor = (bill.sponsor_bioguide == m.member_id_bioguide) if bill.sponsor_bioguide else False
        is_cosponsor = m.member_id_bioguide in cosponsor_ids
        p = predict_member_vote_probability(
            m.party, sponsor_party, cosponsor_counts,
            is_sponsor=is_sponsor, is_cosponsor=is_cosponsor
        )
        # Adjust by member cross-party propensity: more cross-party cosponsorship → more likely to defect
        propensity = float(member_cross_party_propensity.get(m.member_id_bioguide, 0.0))
        if sponsor_party and m.party:
            same_party = (sponsor_party.upper() == m.party.upper())
            # Only apply propensity when bill has non-trivial cross-party cosponsors
            num_dem, num_rep, num_ind = cosponsor_counts
            total = max(num_dem + num_rep + num_ind, 0)
            sp = (sponsor_party or '').upper()
            cross_party = num_rep if sp == 'D' else (num_dem if sp == 'R' else min(num_dem, num_rep))
            cross_share = (cross_party / float(total)) if total > 0 else 0.0
            if cross_share >= 0.15:
                # Scale in roughly [-0.10, +0.10]
                shift = 0.2 * (propensity - 0.5)
                # If same party, shift downward (toward defection); else shift upward (toward crossing)
                p = p - shift if same_party else p + shift
                p = max(0.02, min(0.98, p))

        # Issue-based adjustment: member's historical Yea rate for this bill's policy area/subjects
        hist = issue_history.get(m.member_id_bioguide)
        if hist is not None:
            # Blend toward historical rate with modest weight
            # Weight increases with sample size, capped
            n = min(hist.get('n', 0), 30)
            w = 0.15 * (n / 30.0)  # up to 0.15
            p = (1 - w) * p + w * float(hist.get('yea_rate', p))
            p = max(0.02, min(0.98, p))
        results.append({
            'member_id': m.member_id_bioguide,
            'name': f"{m.first} {m.last}",
            'party': m.party,
            'state': m.state,
            'chamber': 'House' if m.district is not None else 'Senate',
            'probability_yea': round(p, 4),
            'is_sponsor': is_sponsor,
            'is_cosponsor': is_cosponsor
        })
    return results


def rank_likely_defectors(
    scores: List[Dict[str, object]],
    sponsor_party: Optional[str]
) -> List[Dict[str, object]]:
    """
    Rank members by likelihood of defection from presumed party-line position.
    If sponsor is D → presume Ds Yea, Rs Nay; defectors are Ds with low p, Rs with high p.
    Returns list sorted by defection likelihood descending with a 'defection_score'.
    """
    result = []
    sp = (sponsor_party or '').upper()
    for s in scores:
        mp = (s.get('party') or '').upper()
        p = float(s.get('probability_yea', 0.5))
        if sp == 'D':
            def_score = (1.0 - p) if mp == 'D' else p
        elif sp == 'R':
            # Defection for Rs is voting Nay → 1-p; for non-Rs defection is voting Yea → p
            def_score = (1.0 - p) if mp == 'R' else p
        else:
            # Unknown sponsor party: defection relative to chamber party majority is undefined → use distance from 0.5
            def_score = abs(p - 0.5)
        s_out = dict(s)
        s_out['defection_score'] = round(def_score, 4)
        result.append(s_out)
    return sorted(result, key=lambda x: x['defection_score'], reverse=True)


def compute_member_cross_party_propensity(session: Session) -> Dict[str, float]:
    """
    For each member, compute the share of their cosponsorships that are cross-party
    relative to the sponsor's party on those bills. Returns values in [0,1].
    Members with no cosponsorships get 0.0.
    """
    from scripts.setup_db import Bill

    # Cache sponsor party per bill
    sponsor_party_by_bill: Dict[str, Optional[str]] = {}
    out: Dict[str, float] = {}

    cosponsors = session.query(Cosponsor).all()
    if not cosponsors:
        return out

    # Preload member party
    members = session.query(Member).all()
    party_by_member = {m.member_id_bioguide: (m.party or '').upper() for m in members}

    # Accumulators
    totals: Dict[str, int] = {}
    cross: Dict[str, int] = {}

    for c in cosponsors:
        mb = c.member_id_bioguide
        sponsor_party = sponsor_party_by_bill.get(c.bill_id)
        if sponsor_party is None and c.bill_id is not None:
            b = session.query(Bill).filter(Bill.bill_id == c.bill_id).first()
            if b and b.sponsor_bioguide:
                spm = session.query(Member).filter(Member.member_id_bioguide == b.sponsor_bioguide).first()
                sponsor_party = (spm.party if spm else '') or ''
            else:
                sponsor_party = ''
            sponsor_party_by_bill[c.bill_id] = sponsor_party
        mp = party_by_member.get(mb, '')
        if mp == '' or sponsor_party == '':
            continue
        totals[mb] = totals.get(mb, 0) + 1
        if mp != sponsor_party.upper():
            cross[mb] = cross.get(mb, 0) + 1

    for mb, t in totals.items():
        x = cross.get(mb, 0)
        out[mb] = x / float(t) if t > 0 else 0.0
    return out


def compute_issue_based_history(session: Session, bill_id: str) -> Dict[str, Dict[str, float]]:
    """
    For the given bill, identify its policy area and subjects, then compute for each member:
    - yea_rate on historical rollcalls attached to bills sharing the policy area or subjects
    Returns mapping: member_id -> { 'yea_rate': float, 'n': int }
    """
    from scripts.setup_db import Bill, Rollcall, Vote, BillSubject

    bill = session.query(Bill).filter(Bill.bill_id == bill_id).first()
    if not bill:
        return {}
    policy_area = (bill.policy_area or '').strip().lower()
    subjects = set(
        s.subject_term.strip().lower()
        for s in session.query(BillSubject).filter(BillSubject.bill_id == bill_id).all()
    )

    # Find similar bills: same policy area OR overlapping subjects
    similar_bill_ids: List[str] = []
    if policy_area:
        similar_bill_ids = [b.bill_id for b in session.query(Bill).filter(Bill.policy_area == bill.policy_area).all()]
    if subjects:
        by_subject = session.query(BillSubject).filter(BillSubject.subject_term.in_(list(subjects))).all()
        similar_bill_ids.extend(bs.bill_id for bs in by_subject)
    similar_bill_ids = list({bid for bid in similar_bill_ids if bid and bid != bill_id})

    if not similar_bill_ids:
        return {}

    # Collect rollcalls on those bills
    rcs = session.query(Rollcall).filter(Rollcall.bill_id.in_(similar_bill_ids)).all()
    if not rcs:
        return {}
    rc_ids = [rc.rollcall_id for rc in rcs]

    # Aggregate member yea rates
    votes = session.query(Vote).filter(Vote.rollcall_id.in_(rc_ids)).all()
    yea_counts: Dict[str, int] = {}
    total_counts: Dict[str, int] = {}
    for v in votes:
        if v.vote_code in ('Yea', 'Nay'):
            total_counts[v.member_id_bioguide] = total_counts.get(v.member_id_bioguide, 0) + 1
            if v.vote_code == 'Yea':
                yea_counts[v.member_id_bioguide] = yea_counts.get(v.member_id_bioguide, 0) + 1

    out: Dict[str, Dict[str, float]] = {}
    for mid, tot in total_counts.items():
        yea = yea_counts.get(mid, 0)
        out[mid] = {'yea_rate': yea / float(tot), 'n': tot}
    return out


