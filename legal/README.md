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

## Approval

**Approved by Charlie on 27 Nov 2026** for the web app and derlin.app, after a check against:

- **UK GDPR (Articles 13 and 14, the ICO's privacy notice checklist):** who runs it and how to contact them; what's collected, why, and the lawful basis for each; legitimate interests explained; who else gets it; transfers outside the UK and their safeguards; how long it's kept; every right, including complaining to the ICO; what's required versus optional; data from other sources (Google, other members' tags); no automated decisions. All covered.
- **Google sign-in verification (OAuth consent screen):** the policy is on the same domain as the homepage (derlin.app/privacy), says which Google data is used (email, name, picture) and why, how to delete it, and has the Limited Use statement. Covered. Derlin only asks for basic scopes, so no security assessment is needed.
- **Apple App Store (5.1.1, 1.2) and Google Play (User Data, UGC, account deletion):** the policy and terms themselves are covered (data, uses, third parties, retention, deletion, rules for posts, a way to report). The apps need a few app features first: see **Before the app stores** below.

This is still not legal advice: a solicitor's review is worth it before a paid or large launch.

## Before the app stores

These are app features the store rules need, not changes to the wording (update the wording when they land):

- **Delete your account in the app.** Apple requires it inside the app; Google Play also needs a web page where people can ask for deletion (derlin.app/privacy's email instructions can do for that).
- **Block another member.** Both stores require it for apps where members post content (with Report, which PR 65 adds).
- **Sign in with Apple**, on the iPhone app, because it offers Google sign-in.
- **Store privacy forms:** Apple's privacy labels and Google Play's Data safety form, filled in from `privacy.md`.

## Choices the owner made

Picked as sensible defaults and approved by Charlie on 27 Nov 2026:

- **Who runs it:** "Charlie, an individual based in the United Kingdom". The app stores and Google's verification may want a full legal name and a postal address: add them here when needed.
- **ICO fee:** individuals who process personal data for a service may need to pay the ICO's yearly data protection fee (about £52). Check with the ICO's self-assessment at ico.org.uk/fee.
- **Minimum age:** 13 (the UK's age for consenting to online services). Sign-up asks for the birth year and turns away anyone certainly under 13.
- **Under-18s (ICO Children's Code):** Charlie chose (27 Nov 2026) that members aged 13 to 17 start with **Share my sightings off**; they can switch it on themselves. Only the birth year is kept, in the account's private metadata (not on the profile other members can read). A year can't tell if this year's birthday has passed, so anyone who may still be 17 counts as under 18. Members who joined before this aren't asked and keep their setting.
- **Deletion:** by email to hello@derlin.app, done within 30 days; backups clear within a further 30.
- **Inactive accounts:** kept until deleted (no automatic clean-up).
- **Law:** England and Wales.
- **Contact:** hello@derlin.app must be working before these go live on derlin.app.
