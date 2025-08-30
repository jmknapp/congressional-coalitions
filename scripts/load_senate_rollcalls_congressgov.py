#!/usr/bin/env python3
import os, sys, time, requests, datetime
sys.path.insert(0,'src')
from src.utils.database import get_db_session
from scripts.setup_db import Rollcall, Vote

API=os.environ.get('CONGRESS_GOV_API_KEY') or ''
BASE='https://api.congress.gov/v3'
CONGRESS=119

def norm(c:str):
    c=(c or '').strip().lower()
    if c in ('yea','aye','yes','y'): return 'Yea'
    if c in ('nay','no','n'): return 'Nay'
    if c in ('present','present - announced'): return 'Present'
    return None

def upsert_vote(congress:int, session:int, roll:int):
    url=f'{BASE}/senate-vote/{congress}/{session}/{roll}?api_key={API}'
    r=requests.get(url, timeout=30)
    if r.status_code!=200: return 0,0
    j=r.json().get('senateVote') or {}
    rcnum=int(j.get('rollNumber') or j.get('rollnumber') or roll)
    rc_id=f'rc-{rcnum}-{congress}'
    question=j.get('question')
    dt=j.get('date')
    rc_date=None
    for fmt in ('%Y-%m-%d','%m/%d/%Y','%B %d, %Y'):
        try: rc_date=datetime.datetime.strptime((dt or '')[:19], fmt).date(); break
        except: pass
    bill_id=None
    bill=j.get('bill') or {}
    btype=(bill.get('type') or '').lower()
    bnum=bill.get('number')
    if btype and str(bnum or '').isdigit(): bill_id=f'{btype}-{int(bnum)}-{congress}'
    members=j.get('members') or j.get('memberVotes') or []
    inserted_rc=0; inserted_votes=0
    with get_db_session() as s:
        if not s.query(Rollcall).filter(Rollcall.rollcall_id==rc_id).first():
            s.add(Rollcall(rollcall_id=rc_id, congress=congress, chamber='senate',
                           session=session, rc_number=rcnum, question=question,
                           bill_id=bill_id, date=rc_date))
            s.flush()
            inserted_rc=1
        for m in members:
            bid=m.get('bioguideId') or m.get('bioguideID') or m.get('bioguide_id')
            v=norm(m.get('vote') or m.get('voteCast') or m.get('vote_cast') or m.get('value') or m.get('vote_position'))
            if not bid or not v: continue
            if not s.query(Vote).filter(Vote.rollcall_id==rc_id, Vote.member_id_bioguide==bid).first():
                s.add(Vote(rollcall_id=rc_id, member_id_bioguide=bid, vote_code=v))
                inserted_votes+=1
        s.commit()
    return inserted_rc, inserted_votes

def list_and_ingest(congress:int):
    total_rc=total_votes=0
    for session in (1,2):
        for roll in range(1, 1600):
            rc, vv = upsert_vote(congress, session, roll)
            if rc or vv: total_rc+=rc; total_votes+=vv
            else:
                if roll%50==0:
                    pass
    print('senate inserted rc:', total_rc, 'votes:', total_votes)

def main():
    if not API:
        print('Missing CONGRESS_GOV_API_KEY')
        sys.exit(1)
    list_and_ingest(CONGRESS)

if __name__ == '__main__':
    main()
