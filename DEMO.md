# DenialDesk — Running and demoing the app

DenialDesk is a standalone web app: one process serves the API and the UI.

## Run it

```bash
make install        # one time: Python + frontend deps
make demo           # wipe data/dev.db, create tables, seed Lakeside Family Practice
make run            # build the UI and serve everything at http://localhost:8000
```

Sign in with a demo account (the login screen has one-click buttons in dev mode). All use password `DenialDesk-Demo1` — synthetic data only.

| Account | Role | What they see |
|---|---|---|
| admin@lakesidefp.com | Clinic admin | Dashboard, claims, upload, requests, statements, team, access log |
| staff@lakesidefp.com | Clinic staff | Same, without team/access log |
| ops@denialdesk.com | DenialDesk admin | Overview, review queue, all claims, deadlines, practices, analytics, billing, users |
| reviewer@denialdesk.com | Appeals reviewer | Review queue, all claims, deadlines |

Hot-reload dev: `uvicorn denialdesk.api.main:app --reload` and `cd frontend && npm run dev` (http://localhost:5173).

## Walkthrough

1. **Clinic** — sign in as the clinic admin. Dashboard shows dollars recovered/submitted and open requests.
2. **Upload** — *Upload denials*, drop `data/sample_claims.csv` (synthetic). Watch parse → AI analysis → results. Unwinnable claims are declined with a reason; the rest get an AI-written appeal.
3. **Claim detail** — open any claim: denial analysis, win odds, the appeal letter, documents to attach, activity timeline, PDF download.
4. **Ops** — sign out, sign in as ops. *Review queue*: read the letter, edit if needed, **Approve & submit** (nothing goes to a payer without this).
5. **Outcome** — on a submitted claim, record the outcome (paid / denied), then confirm recovery to make it billable.
6. **Billing** — *Billing → Generate statement* for the month; download the PDF.
7. **Onboarding gate** — create a new clinic via *Create an account* on the login page. It can't upload until an ops admin marks the BAA and service agreement signed and activates it (*Practices*).

## Notes

- Without `ANTHROPIC_API_KEY` in `.env`, letters fall back to a short generic template.
- Real PHI must not be loaded until the go-live gate in `deploy/GO_LIVE_CHECKLIST.md` is complete. Built-in login has no MFA; swap in a managed IdP before go-live.
