# Privacy policy and terms of use

- [`privacy.md`](privacy.md): the privacy policy.
- [`terms.md`](terms.md): the terms of use.

The app shows both, unchanged, in **Settings > Privacy and terms** and at the bottom of the sign-in screen (`legal_expanders()` in `app.py`). They're plain Markdown so the derlin.app landing page can show the same text at `/privacy` and `/terms`.

**These are a plain-English starting point written from what the app actually does, not legal advice.** Before a public launch (and before the app stores or Google's sign-in verification), have them checked, for example against the ICO's guidance for small organisations (ico.org.uk) or by a solicitor.

## Keep them true

Update them in the same change whenever the app starts collecting something new, shares it differently or uses a new service (and bump **Last updated**). In particular:

- **Moving hosting off Streamlit Cloud** (launch plan step 4): replace Streamlit in the list of services.
- **New third-party services** (analytics, email sending, a new AI model run elsewhere): add them to "Who else handles your information".
- **Messaging or friends**: say who can see messages and how to report someone.
- **An in-app "delete my account" button**: point the policy to it instead of only the email address.

## Choices the owner made (or should check)

These were picked as sensible defaults on 27 Nov 2026. Change the text if any is wrong:

- **Who runs it:** "Charlie, an individual based in the United Kingdom". The app stores and Google's verification may want a full legal name and a postal address: add them here when needed.
- **ICO fee:** individuals who process personal data for a service may need to pay the ICO's yearly data protection fee (about £52). Check with the ICO's self-assessment at ico.org.uk/fee.
- **Minimum age:** 13 (the UK's age for consenting to online services).
- **Deletion:** by email to hello@derlin.app, done within 30 days; backups clear within a further 30.
- **Inactive accounts:** kept until deleted (no automatic clean-up).
- **Law:** England and Wales.
- **Contact:** hello@derlin.app must be working before these go live on derlin.app.
