# Expected Finding: SCOPE-EPIC

**Fixture**: `fixtures/SCOPE-EPIC.json`
**Pattern**: SCOPE-EPIC — Epic-scope packed into single bead without children
**Expected severity**: Critical
**Expected finding excerpt**: The bead description packs three independent feature domains — authentication (OAuth, MFA, SSO), billing (Stripe integration, subscription management, invoice generation), and notifications (email, SMS, in-app) — into a single bead. Each domain requires separate UAT sessions and independent stakeholder sign-off. The connective phrases "And also" and "As well as" signal scope accumulation.
**Anti-pattern code in finding**: [SCOPE-EPIC]
**Minimum required in output**: A Critical finding referencing SCOPE-EPIC, citing phrases such as "And also" or "As well as" or the enumeration of multiple separate feature areas (authentication, billing, notifications), noting that the bead packs epic-level scope requiring separate review sessions.
