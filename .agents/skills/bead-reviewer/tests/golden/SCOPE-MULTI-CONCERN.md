# Expected Finding: SCOPE-MULTI-CONCERN

**Fixture**: `fixtures/SCOPE-MULTI-CONCERN.json`
**Pattern**: SCOPE-MULTI-CONCERN — Multi-concern requiring separate review sessions
**Expected severity**: Critical
**Expected finding excerpt**: The bead combines two concerns — backend search API (requiring Platform team sign-off) and frontend search UI (requiring separate UX stakeholder review and design QA) — each with independent review gates and different domain experts. The description explicitly states "two separate work streams" with independent stakeholder review requirements.
**Anti-pattern code in finding**: [SCOPE-MULTI-CONCERN]
**Minimum required in output**: A Critical finding referencing SCOPE-MULTI-CONCERN, citing text such as "two separate work streams" or "independent review gates" or "separate UX stakeholder review", noting that the bead combines concerns each requiring their own stakeholder review and domain expertise.
