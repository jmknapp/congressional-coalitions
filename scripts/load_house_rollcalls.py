#!/usr/bin/env python3
import sys, requests, xml.etree.ElementTree as ET, datetime, argparse
sys.path.insert(0,'src')
from src.utils.database import get_db_session
from scripts.setup_db import Rollcall, Vote

def norm(c):
    c=(c or '').strip().lower()
    if c in ('yea','aye','yes','y'): return 'Yea'
    if c in ('nay','no','n'): return 'Nay'
    if c in ('present','present - announced'): return 'Present'
    return None

def load_one(congress, year, num):
    url=f'https://clerk.house.gov/evs/{year}/roll{num:03d}.xml'
    r=requests.get(url,timeout=20)
    if r.status_code!=200: return False
    root=ET.fromstring(r.content)
    def get(p):
        n=root.find(p); 
        return (n.text or '').strip() if n is not None and n.text else ''
    rcnum=int(get('.//rollcall-num') or get('.//rollcall') or '0')
    if not rcnum: return True
    rc_id=f'rc-{rcnum}-{congress}'
    q=get('.//vote-question') or get('.//question')
    dt=get('.//vote-date') or get('.//date')
    rc_date=None
    for fmt in ('%B %d, %Y','%Y-%m-%d','%m/%d/%Y'):
        try: rc_date=datetime.datetime.strptime(dt,fmt).date(); break
        except: pass
    bill_id=None
    legis=(get('.//legis-num') or '').lower().replace('.','').replace(' ','')
    bt=''.join(ch for ch in legis if ch.isalpha()); bn=''.join(ch for ch in legis if ch.isdigit())
    if bt and bn: bill_id=f'{bt}-{int(bn)}-{congress}'
    members=[]
    # recorded-vote structure
    def tn(e): return e.tag.split('}')[-1].lower()
    for rv in root.findall('.//recorded-vote') + root.findall('.//recorded_vote'):
        leg=rv.find('legislator')
        bid=(leg.get('bioguide_id') if leg is not None else '') if leg is not None else ''
        v=norm(rv.findtext('vote') or '')
        if bid and v: members.append((bid,v))
    with get_db_session() as s:
        if not s.query(Rollcall).filter(Rollcall.rollcall_id==rc_id).first():
            s.add(Rollcall(rollcall_id=rc_id, congress=congress, chamber='house',
                           session=None, rc_number=rcnum, question=q, bill_id=bill_id, date=rc_date))
            s.flush()
        for bid,v in members:
            if not s.query(Vote).filter(Vote.rollcall_id==rc_id, Vote.member_id_bioguide==bid).first():
                s.add(Vote(rollcall_id=rc_id, member_id_bioguide=bid, vote_code=v))
        s.commit()
    return True

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--congress', type=int, required=True)
    ap.add_argument('--year', type=int, required=True)
    ap.add_argument('--max', type=int, default=1500)
    args=ap.parse_args()
    misses=0
    for i in range(1, args.max+1):
        ok=load_one(args.congress, args.year, i)
        if ok: misses=0
        else:
            misses+=1
            if misses>50: break

if __name__ == '__main__':
    main()
