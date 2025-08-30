#!/usr/bin/env python3
"""
Member roster loader for 119th Congress.

- House roster: Clerk XML (MemberData.xml)
- Senate roster: Senate contact XML (senators_cfm.xml)

Inserts or updates rows in Members with real names, parties, states, districts, and bioguide IDs.
"""
import os
import sys
import logging
from datetime import date
from typing import Optional
import requests
import xml.etree.ElementTree as ET
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Add project root src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.utils.database import get_db_session
from scripts.setup_db import Member

logger = logging.getLogger(__name__)

HOUSE_XML_URL = "https://clerk.house.gov/xml/lists/MemberData.xml"
SENATE_XML_URL = "https://www.senate.gov/general/contact_information/senators_cfm.xml"

PARTY_MAP = {
    'Democratic': 'D', 'Democrat': 'D', 'D': 'D',
    'Republican': 'R', 'R': 'R',
    'Independent': 'I', 'I': 'I', 'Independent Democrat': 'I'
}

class MemberLoader:
    def __init__(self):
        self.session = requests.Session()
        # Set UA and retries for robustness
        self.session.headers.update({
            'User-Agent': 'Congressional-Coalitions/1.0 (+https://example.org)'
        })
        retry = Retry(
            total=5,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"]
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

    def _upsert_member(self, session, bioguide: str, first: str, last: str, party: Optional[str], state: str, district: Optional[int], overwrite: bool = False):
        existing = session.query(Member).filter(Member.member_id_bioguide == bioguide).first()
        if existing:
            changed = False
            if overwrite or (first and existing.first != first):
                existing.first = first; changed = True
            if overwrite or (last and existing.last != last):
                existing.last = last; changed = True
            if overwrite or (party and existing.party != party):
                existing.party = party; changed = True
            if overwrite or (state and existing.state != state):
                existing.state = state; changed = True
            # Only set district for House; leave None for Senate
            if overwrite or (existing.district != district):
                existing.district = district; changed = True
            if changed:
                session.flush()
            return False
        session.add(Member(
            member_id_bioguide=bioguide,
            icpsr=None,
            lis_id=None,
            first=first,
            last=last,
            party=party,
            state=state,
            district=district,
            start_date=date(2023, 1, 3),
            end_date=None
        ))
        return True

    def load_house(self, overwrite: bool = False) -> int:
        resp = self.session.get(HOUSE_XML_URL, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        inserted = 0
        # Handle possible namespaces by stripping them
        def strip_ns(tag: str) -> str:
            return tag.split('}')[-1] if '}' in tag else tag
        with get_db_session() as session:
            for elem in root.iter():
                if strip_ns(elem.tag).lower() != 'member':
                    continue
                # Nested structure: <member><member-info>...</member-info><statedistrict>..</statedistrict>...</member>
                member_info = None
                for child in elem:
                    if strip_ns(child.tag).lower() == 'member-info':
                        member_info = child
                        break
                def mi_text(*names: str) -> str:
                    if not member_info:
                        return ''
                    # search by tag names case-insensitively
                    for n in names:
                        node = member_info.find(n)
                        if node is not None and (node.text or '').strip():
                            return node.text.strip()
                        # fallback: iterate
                        for c in member_info:
                            if strip_ns(c.tag).lower() == n.lower():
                                return (c.text or '').strip()
                    return ''
                # bioguide
                bioguide = mi_text('bioguideId', 'bioguideID')
                if not bioguide:
                    # last resort: attribute (older formats)
                    bioguide = (elem.get('bioguideID') or elem.get('bioguideId') or '').strip()
                if not bioguide:
                    continue
                # names
                first = mi_text('firstName', 'firstname', 'officialFirstName', 'officialfirstname')
                last = mi_text('lastName', 'lastname', 'officialLastName', 'officiallastname')
                # state
                state = mi_text('stateCode', 'statecode', 'statePostal', 'statepostal', 'state')
                if not state and member_info is not None:
                    state_el = member_info.find('state')
                    if state_el is not None:
                        state = (state_el.get('postal-code') or state_el.get('stateCode') or '').strip()
                # party
                party_full = mi_text('partyName', 'partyname', 'party')
                party = PARTY_MAP.get(party_full, party_full[:1] if party_full else None)
                # district from <statedistrict>
                district_text = ''
                for c in elem:
                    if strip_ns(c.tag).lower() == 'statedistrict':
                        district_text = (c.text or '').strip()
                        break
                district: Optional[int] = None
                if district_text:
                    t = district_text.strip().lower()
                    if t in ('at large', 'at-large', 'al', '00', '0'):
                        district = 1
                    else:
                        try:
                            district = int(''.join(ch for ch in t if ch.isdigit()))
                        except ValueError:
                            district = 1
                # ensure state present
                if not state:
                    continue
                if self._upsert_member(session, bioguide, first, last, party, state, district, overwrite=overwrite):
                    inserted += 1
            session.commit()
        logger.info("Inserted %d new House members (others updated in-place)", inserted)
        return inserted

    def load_senate(self, overwrite: bool = False) -> int:
        resp = self.session.get(SENATE_XML_URL, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        inserted = 0
        def strip_ns(tag: str) -> str:
            return tag.split('}')[-1] if '}' in tag else tag
        with get_db_session() as session:
            for elem in root.iter():
                if strip_ns(elem.tag).lower() == 'member':
                    def get_text(e, name):
                        child = e.find(name)
                        if child is None:
                            for c in e:
                                if strip_ns(c.tag).lower() == name.lower():
                                    return (c.text or '').strip()
                            return ''
                        return (child.text or '').strip()
                    bioguide = (get_text(elem, 'bioguide_id') or get_text(elem, 'bioguideid')).strip()
                    if not bioguide:
                        continue
                    first = get_text(elem, 'first_name') or get_text(elem, 'firstname')
                    last = get_text(elem, 'last_name') or get_text(elem, 'lastname')
                    party_full = get_text(elem, 'party')
                    party = PARTY_MAP.get(party_full, party_full[:1] if party_full else None)
                    state = get_text(elem, 'state') or get_text(elem, 'state_code')
                    if not state:
                        continue
                    if self._upsert_member(session, bioguide, first, last, party, state, None, overwrite=overwrite):
                        inserted += 1
            session.commit()
        logger.info("Inserted %d new Senate members (others updated in-place)", inserted)
        return inserted
