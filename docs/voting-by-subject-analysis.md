# Voting Patterns by Bill Subject — Ideas and Implementation Plan

This document outlines practical analyses that connect voting behavior to bill subjects using the existing schema (`bills`, `bill_subjects`, `rollcalls`, `votes`, `members`). It balances quick wins with deeper methods you can iterate toward.

## Scope & Data Assumptions
- Default scope: House, 119th Congress.
- Subjects: use `bills.policy_area` (broad) and `bill_subjects.subject_term` (granular). Support both.
- Vote coding: treat `Yea=1`, `Nay=0`; exclude `Present` and `Not Voting` from rate calculations.
- Procedural vs substantive: optionally exclude procedural votes (see filter below) to avoid inflating partisanship.

## Quick Wins
- Party split by subject: for each subject, compute Democratic vs Republican Yea rates and the partisan gap.
- Cross‑party outliers: per subject, members whose Yea rate deviates most from their party’s subject mean.
- Caucus cohesion by subject: within each caucus, fraction voting with the caucus majority for that subject.

## Deeper Analyses
- Subject‑conditioned party line index: percent of members voting with their party within each subject; compare to overall.
- Member subject profiles: vector of Yea rates across subjects; use cosine similarity to surface issue‑based coalitions.
- Sponsor party effect: for each subject, difference in support when sponsor is D vs R (difference‑in‑means).
- Procedural vs substantive comparison: recompute metrics after removing procedural votes to reveal real divergences.

## Statistical Tests / Models
- Significance per subject: chi‑square or Fisher’s exact test on Party × Vote for each subject; report p‑value and Cramér’s V.
- Vote prediction: logistic regression (target=Yea) with features: member party, sponsor party, subject dummies, caucus flags; interpret subject coefficients with CIs.
- Subject‑specific ideal points: per‑subject member×rollcall matrix; 1D SVD to see how the ideological ordering shifts by issue.

## Visuals
- Heatmap: subjects (rows) × parties/caucuses (cols) showing Yea rate or cohesion.
- Small multiples: bar pairs per subject (D vs R Yea %), with confidence intervals.
- Network by subject: vote‑similarity or co‑sponsorship graph filtered by subject to expose cross‑party clusters.

## Procedural Vote Filter (optional)
Flag votes as procedural if rollcall `question` contains any of:
- "providing for consideration", "rule", "ordering the previous question", 
- "motion to recommit", "motion to table", "quorum", "adjourn", "suspend the rules".
Make this toggleable in the UI and endpoints.

## Data Prep (joins)
```
votes v
  JOIN rollcalls r ON v.rollcall_id = r.rollcall_id
  JOIN bills b     ON r.bill_id = b.bill_id
  LEFT JOIN bill_subjects s ON s.bill_id = b.bill_id
  JOIN members m  ON v.member_id_bioguide = m.member_id_bioguide
WHERE b.congress = 119 AND b.chamber = 'house'
  AND v.vote_code IN ('Yea','Nay')
```

## SQL Sketches

Party split by `subject_term` (portable AVG form):
```
SELECT s.subject_term,
       m.party,
       SUM(CASE WHEN v.vote_code='Yea' THEN 1 ELSE 0 END) / 
       NULLIF(SUM(CASE WHEN v.vote_code IN ('Yea','Nay') THEN 1 ELSE 0 END),0) AS yea_rate,
       COUNT(*) AS votes
FROM votes v
JOIN rollcalls r ON v.rollcall_id = r.rollcall_id
JOIN bills b     ON r.bill_id = b.bill_id
JOIN bill_subjects s ON s.bill_id = b.bill_id
JOIN members m   ON v.member_id_bioguide = m.member_id_bioguide
WHERE b.congress = 119 AND b.chamber='house'
GROUP BY s.subject_term, m.party
HAVING votes >= 20
ORDER BY votes DESC;
```

Member outliers by subject (residual = member_rate − party_mean):
```
-- Party mean per subject
WITH party_stats AS (
  SELECT s.subject_term, m.party,
         SUM(v.vote_code='Yea')/SUM(v.vote_code IN ('Yea','Nay')) AS party_yea
  FROM votes v
  JOIN rollcalls r ON v.rollcall_id=r.rollcall_id
  JOIN bills b ON r.bill_id=b.bill_id
  JOIN bill_subjects s ON s.bill_id=b.bill_id
  JOIN members m ON v.member_id_bioguide=m.member_id_bioguide
  WHERE b.congress=119 AND b.chamber='house' AND v.vote_code IN ('Yea','Nay')
  GROUP BY s.subject_term, m.party
), member_stats AS (
  SELECT s.subject_term, v.member_id_bioguide,
         SUM(v.vote_code='Yea')/SUM(v.vote_code IN ('Yea','Nay')) AS member_yea,
         COUNT(*) AS n
  FROM votes v
  JOIN rollcalls r ON v.rollcall_id=r.rollcall_id
  JOIN bills b ON r.bill_id=b.bill_id
  JOIN bill_subjects s ON s.bill_id=b.bill_id
  WHERE b.congress=119 AND b.chamber='house' AND v.vote_code IN ('Yea','Nay')
  GROUP BY s.subject_term, v.member_id_bioguide
)
SELECT ms.subject_term, ms.member_id_bioguide, m.party,
       ms.member_yea - ps.party_yea AS residual,
       ms.n
FROM member_stats ms
JOIN members m ON m.member_id_bioguide=ms.member_id_bioguide
JOIN party_stats ps ON ps.subject_term=ms.subject_term AND ps.party=m.party
WHERE ms.n >= 8
ORDER BY ABS(residual) DESC
LIMIT 50;
```

Caucus cohesion by subject:
```
SELECT s.subject_term, c.short_name AS caucus,
       SUM(CASE WHEN v.vote_code = majority_vote.vote_code THEN 1 ELSE 0 END)/COUNT(*) AS cohesion,
       COUNT(*) AS votes
FROM votes v
JOIN rollcalls r ON v.rollcall_id=r.rollcall_id
JOIN bills b ON r.bill_id=b.bill_id
JOIN bill_subjects s ON s.bill_id=b.bill_id
JOIN caucus_memberships cm ON cm.member_id_bioguide = v.member_id_bioguide AND cm.end_date IS NULL
JOIN caucuses c ON c.id = cm.caucus_id
JOIN (
  SELECT r2.rollcall_id, 
         CASE WHEN SUM(v2.vote_code='Yea') >= SUM(v2.vote_code='Nay') THEN 'Yea' ELSE 'Nay' END AS vote_code
  FROM votes v2 JOIN rollcalls r2 ON v2.rollcall_id=r2.rollcall_id
  WHERE v2.vote_code IN ('Yea','Nay')
  GROUP BY r2.rollcall_id
) majority_vote ON majority_vote.rollcall_id = v.rollcall_id
WHERE b.congress=119 AND b.chamber='house' AND v.vote_code IN ('Yea','Nay')
GROUP BY s.subject_term, c.short_name
HAVING votes >= 20;
```

## API Endpoints (proposed)
- `GET /api/subjects/summary?scope=policy_area|subject_term&min_votes=20&exclude_procedural=true|false`
  - Returns: `[{subject, d_yea, r_yea, gap, votes, p_value, cramers_v}]`
- `GET /api/subjects/<subject>/detail?scope=...`
  - Returns: member outliers, top cross‑party roll calls, sponsor‑party effect.

## Caching & Performance
- Use Flask‑Caching (filesystem) to cache per‑subject aggregates for 10–30 minutes.
- Precompute nightly: materialize `member_subject_stats` (member_id, subject, n, yea_rate) to speed UI.
- Enforce minimum N (e.g., 20 votes per subject) to stabilize rates and stats.

## UI Integration
- Add a "By Subject" card/table on the dashboard.
- Subject detail page: header stats + recent key votes + outlier members.
- Subject chips on bill pages linking to the subject detail.
- Filters: toggle procedural exclusion; pick policy_area vs subject_term.

## Modeling Outline (Python)
```python
# y: 1 if Yea, 0 if Nay
# X: party (binary), sponsor_party, subject dummies, caucus flags, maybe member fixed effects
from sklearn.linear_model import LogisticRegression
import pandas as pd

X, y = make_features(votes_joined_df)  # one row per vote
model = LogisticRegression(max_iter=200)
model.fit(X, y)
coefs = pd.Series(model.coef_[0], index=X.columns)
# Interpret subject_* coefficients as subject effects controlling for party/caucus
```

## Guardrails
- Minimum observations per subject and per member‑subject cell.
- Present clear N with each percentage.
- Distinguish procedural vs substantive; report both when possible.
- Document that "Yea" does not always equal "support" (e.g., procedural votes).

## Roadmap
1) Ship subject summary (party split + gap, optional procedural filter).
2) Add subject detail with outliers and key votes.
3) Add caucus cohesion and sponsor‑party effect.
4) Add modeling view (logistic regression summary) and per‑subject ideal points.

---
This plan should fit easily into the current Flask app: add the two endpoints, a summary page, and a detail page, then cache the heavy aggregations.

