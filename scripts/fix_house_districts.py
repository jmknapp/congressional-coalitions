import sys, xml.etree.ElementTree as ET, requests
sys.path.insert(0, 'src')
from src.utils.database import get_db_session
from scripts.setup_db import Member

def tagname(e):
    return e.tag.split('}')[-1].lower()

r = requests.get('https://clerk.house.gov/xml/lists/MemberData.xml', timeout=30)
r.raise_for_status()
root = ET.fromstring(r.content)

updates = 0
with get_db_session() as s:
    for mem in root.iter():
        if tagname(mem) != 'member':
            continue
        bid = (mem.get('bioguideID') or mem.get('bioguideId') or '').strip()
        if not bid:
            continue

        # state
        state = ''
        for c in mem:
            if tagname(c) in ('state', 'statepostal'):
                state = (c.text or '').strip() or state

        # district from role@stateDistrict / district variants
        role = None
        for c in mem:
            if tagname(c) == 'role':
                role = c
                break

        dist_txt = ''
        if role is not None:
            dist_txt = (role.get('stateDistrict') or role.get('statedistrict') or role.get('district') or '').strip()

        t = dist_txt.lower()
        if t in ('at large', 'at-large', 'al', '00', '0'):
            dist = 1
        else:
            dist = int(''.join(ch for ch in t if ch.isdigit()) or '1') if dist_txt else 1

        m = s.query(Member).filter(Member.member_id_bioguide == bid).first()
        if m and state:
            if m.district is None or m.district != dist or m.state != state:
                m.state = state
                m.district = dist
                updates += 1

    s.commit()

print('house_district_updates:', updates)
