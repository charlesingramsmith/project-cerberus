# The Derlin landing page (derlin.app)

A one-page website that says what the app is and has an **Open the app** button. It lives in
this repo and GitHub Pages hosts it for free, with HTTPS (which `.app` addresses require).

- `scripts/landing_page.html` is the home page's template; `site/style.css` has the styles.
- The privacy policy and terms (derlin.app/privacy, derlin.app/terms) come from
  `legal/privacy.md` and `legal/terms.md`, in `scripts/legal_page.html`.
- After changing any of these, run `python scripts/build_site.py`: it fills in the logo and
  hand-drawn icons and writes the pages in `site/` (a test fails if you forget).
- When a change to `site/` reaches `main`, the **Landing page** workflow
  (`.github/workflows/pages.yml`) publishes it. You can also run it by hand from the
  repo's **Actions** tab.

## One-time setup

### 1. Turn on GitHub Pages
1. Open the repo on GitHub, then **Settings** > **Pages** (left-hand menu).
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. Go to the **Actions** tab, click **Landing page**, then **Run workflow** > **Run workflow**.
   After a minute it shows a green tick and the page is live at
   `https://charlesingramsmith.github.io/project-cerberus/`.

### 2. Point derlin.app at GitHub (in Porkbun)
DNS records are the address book that tells browsers which computer serves `derlin.app`.

1. Sign in at porkbun.com, go to **Domain Management**, and click **DNS** under derlin.app.
2. Delete Porkbun's parking records (an **ALIAS** record pointing at `pixie.porkbun.com` and
   a **CNAME** for `*`), if they're there.
3. Add four **A** records. Leave **Host** empty each time, and use these **Answer**s:
   `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`.
4. Add one **CNAME** record: **Host** `www`, **Answer** `charlesingramsmith.github.io`.

### 3. Tell GitHub the address
1. Back in **Settings** > **Pages**, type `derlin.app` under **Custom domain** and **Save**.
2. GitHub checks the DNS (a few minutes, sometimes up to an hour). When it says
   "DNS check successful", tick **Enforce HTTPS** once it lets you (its certificate can take
   up to a day; until then `.app` pages won't open, because they need HTTPS).

## When the app moves
The button points at `APP_URL` in `scripts/build_site.py`. When the app gets its own
hosting (launch plan step 4), change it there and rebuild.
