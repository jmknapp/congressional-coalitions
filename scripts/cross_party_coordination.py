#!/usr/bin/env python3
import sys
import os
import argparse
import itertools
import math
from collections import defaultdict, Counter

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import get_db_session
from scripts.setup_db import Member, Vote, Rollcall


def load_votes(congress: int = 119, chamber: str = "house"):
    """Load rollcall votes for the specified Congress/chamber.

    Returns:
    - rc_votes: dict[rollcall_id] -> list of (member_id, party, vote_code in {Yea,Nay})
    - members: dict[member_id] -> {party, name}
    """
    with get_db_session() as session:
        members = {
            m.member_id_bioguide: {
                'party': (m.party or ''),
                'name': f"{m.first or ''} {m.last or ''}".strip()
            }
            for m in session.query(Member).all()
        }

        rc_ids = [
            rc.rollcall_id
            for rc in session.query(Rollcall.rollcall_id)
                .filter(Rollcall.congress == congress, Rollcall.chamber == chamber)
                .all()
        ]

        votes = (
            session.query(Vote.rollcall_id, Vote.member_id_bioguide, Vote.vote_code)
            .filter(Vote.rollcall_id.in_(rc_ids))
            .all()
        )

    rc_votes = defaultdict(list)
    for rc_id, mid, code in votes:
        if code not in ('Yea', 'Nay'):
            continue
        party = members.get(mid, {}).get('party')
        if party not in ('D', 'R'):
            continue
        rc_votes[rc_id].append((mid, party, code))

    return rc_votes, members


def party_majorities(votes_for_rc):
    """Compute each party's majority vote ('Yea'/'Nay'/None for tie) for a rollcall."""
    out = {'D': None, 'R': None}
    for p in ('D', 'R'):
        yea = sum(1 for _, party, c in votes_for_rc if party == p and c == 'Yea')
        nay = sum(1 for _, party, c in votes_for_rc if party == p and c == 'Nay')
        if yea > nay:
            out[p] = 'Yea'
        elif nay > yea:
            out[p] = 'Nay'
        else:
            out[p] = None
    return out


def crossovers(votes_for_rc, majorities):
    """Return sets of member_ids who voted against their party majority on a rollcall."""
    d_cross, r_cross = set(), set()
    for mid, p, c in votes_for_rc:
        maj = majorities[p]
        if maj is None:
            continue
        if c != maj:
            (d_cross if p == 'D' else r_cross).add(mid)
    return d_cross, r_cross


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def scenario1_balanced_swaps(
    rc_votes: dict,
    members: dict,
    min_size: int = 3,
    min_occurrences: int = 2,
    jaccard_threshold: float = 0.7,
):
    """Balanced cross-party swaps recurring over multiple rollcalls.

    Finds rollcalls where |D_cross| == |R_cross| >= min_size, then groups rollcalls
    whose D and R crossover compositions are similar (by Jaccard) across occurrences.
    Outputs recurring cores (intersection) and the rollcalls.
    """
    candidates = []  # (rc_id, dset, rset)
    for rc_id, rows in rc_votes.items():
        maj = party_majorities(rows)
        dset, rset = crossovers(rows, maj)
        if len(dset) >= min_size and len(dset) == len(rset):
            candidates.append((rc_id, frozenset(dset), frozenset(rset)))

    buckets = []  # each: { 'rcs': [ids], 'd': set(core), 'r': set(core) }
    for rc_id, dset, rset in candidates:
        placed = False
        for b in buckets:
            if jaccard(set(dset), b['d']) >= jaccard_threshold and jaccard(set(rset), b['r']) >= jaccard_threshold:
                b['rcs'].append(rc_id)
                b['d'] &= set(dset)  # tighten core
                b['r'] &= set(rset)
                placed = True
                break
        if not placed:
            buckets.append({'rcs': [rc_id], 'd': set(dset), 'r': set(rset)})

    results = []
    for b in buckets:
        if len(b['rcs']) >= min_occurrences:
            dem_core = sorted(b['d'])
            rep_core = sorted(b['r'])
            results.append({
                'occurrences': len(b['rcs']),
                'rollcalls': sorted(b['rcs']),
                'size_each_side': len(dem_core),
                'dem_core': dem_core,
                'rep_core': rep_core,
                'dem_core_names': [members[mid]['name'] for mid in dem_core],
                'rep_core_names': [members[mid]['name'] for mid in rep_core],
            })

    return sorted(results, key=lambda x: (-x['occurrences'], -x['size_each_side']))


def scenario2_periodic_co_cross(
    rc_votes: dict,
    members: dict,
    party: str = 'D',
    min_pair_occurrences: int = 3,
    min_group_size: int = 3,
    min_group_occurrences: int = 3,
):
    """Coordinated cross-party voting within a party.

    Builds a co-cross graph among members of one party based on number of rollcalls
    where the pair both crossed against their party majority. Extracts connected
    components with sufficient co-support, and keeps groups that co-cross together
    on enough rollcalls (>= min_group_occurrences) with internal support threshold
    ceil(0.6*group_size).
    """
    pair_counts = Counter()
    rc_cross_sets = []  # (rc_id, set(member_ids who crossed))

    for rc_id, rows in rc_votes.items():
        maj = party_majorities(rows)
        if maj[party] is None:
            continue
        cross_set = sorted([mid for mid, p, c in rows if p == party and c != maj[party]])
        if len(cross_set) < 2:
            continue
        rc_cross_sets.append((rc_id, set(cross_set)))
        for a, b in itertools.combinations(cross_set, 2):
            pair_counts[tuple(sorted((a, b)))] += 1

    # Build graph from strong pairs
    adj = defaultdict(set)
    for (a, b), cnt in pair_counts.items():
        if cnt >= min_pair_occurrences:
            adj[a].add(b)
            adj[b].add(a)

    # Connected components as candidate groups
    visited = set()
    groups = []
    for node in adj:
        if node in visited:
            continue
        comp = set()
        stack = [node]
        while stack:
            u = stack.pop()
            if u in visited:
                continue
            visited.add(u)
            comp.add(u)
            stack.extend(v for v in adj[u] if v not in visited)
        if len(comp) >= min_group_size:
            groups.append(comp)

    # For each group, count rollcalls where >= ceil(0.6 * |group|) co-crossed
    results = []
    for comp in groups:
        threshold = math.ceil(0.6 * len(comp))
        hits = [rc_id for rc_id, s in rc_cross_sets if len(comp & s) >= threshold]
        if len(hits) >= min_group_occurrences:
            members_sorted = sorted(comp)
            results.append({
                'party': party,
                'size': len(comp),
                'support_threshold': threshold,
                'occurrences': len(hits),
                'members': members_sorted,
                'member_names': [members[mid]['name'] for mid in members_sorted],
                'rollcalls': sorted(hits),
            })

    return sorted(results, key=lambda x: (-x['occurrences'], -x['size']))


def main():
    ap = argparse.ArgumentParser(description='Cross-party coordination analysis')
    ap.add_argument('--congress', type=int, default=119)
    ap.add_argument('--chamber', type=str, default='house', choices=['house', 'senate'])
    ap.add_argument('--min-balanced-size', type=int, default=3)
    ap.add_argument('--min-balanced-occ', type=int, default=2)
    ap.add_argument('--balanced-jaccard', type=float, default=0.7)
    ap.add_argument('--min-pair-occ', type=int, default=3)
    ap.add_argument('--min-group-size', type=int, default=3)
    ap.add_argument('--min-group-occ', type=int, default=3)
    args = ap.parse_args()

    rc_votes, members = load_votes(args.congress, args.chamber)

    print('\n=== Scenario 1: Balanced cross-party swaps (recurring compositions) ===')
    s1 = scenario1_balanced_swaps(
        rc_votes,
        members,
        min_size=args.min_balanced_size,
        min_occurrences=args.min_balanced_occ,
        jaccard_threshold=args.balanced_jaccard,
    )
    if not s1:
        print('No recurring balanced swap groups found with current thresholds.')
    else:
        for i, g in enumerate(s1, 1):
            print(f"\nGroup #{i}: occurrences={g['occurrences']}, size_each_side={g['size_each_side']}")
            print('  Dem core:', ', '.join(g['dem_core_names']))
            print('  Rep core:', ', '.join(g['rep_core_names']))
            print('  Rollcalls:', ', '.join(map(str, g['rollcalls'])))

    print('\n=== Scenario 2: Periodic coordinated cross-party voting within a party ===')
    for party in ('D', 'R'):
        s2 = scenario2_periodic_co_cross(
            rc_votes,
            members,
            party=party,
            min_pair_occurrences=args.min_pair_occ,
            min_group_size=args.min_group_size,
            min_group_occurrences=args.min_group_occ,
        )
        print(f"\nParty {party}:")
        if not s2:
            print('  No coordinated cross-party groups found with current thresholds.')
        else:
            for i, g in enumerate(s2, 1):
                print(
                    f"  Group #{i}: size={g['size']}, occurrences={g['occurrences']}, "
                    f"threshold={g['support_threshold']}"
                )
                print('    Members:', ', '.join(g['member_names']))
                print('    Rollcalls:', ', '.join(map(str, g['rollcalls'])))


if __name__ == '__main__':
    main()



