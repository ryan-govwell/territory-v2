# Prospecting Agent — Technical Integration Brief

**Repo:** `territory-v2`  
**Date:** 2026-05-20  
**Purpose:** Discovery brief for a Claude instance designing the prospecting agent integration.  
**Status:** Read-only investigation — no feature code written yet.

---

## 1. Repo Structure

### What is this project?
- **Type:** Pure static-site HTML dashboard. No framework, no build tool, no Node.js.
- **Language:** Vanilla JS (ES6), inline CSS, HTML5.
- **Single file:** `index.html` (~83 KB) contains all CSS, JS, and HTML. There are no separate component files, modules, or bundled assets.
- **Deployment:** GitHub Pages (via `CNAME` → `territory.bd-at-govwell.com`). Served as a completely static site.
- **CDN dependencies loaded at runtime:**
  - Leaflet 1.9.4 (interactive map)
  - PapaParse 5.4.1 (CSV parsing)
  - D3 v7 (landing page USA map)
  - topojson-client 3 (USA map geometry)
  - Google Fonts (DM Sans)

### Account dashboard component
**File:** `index.html` (the entire codebase)  
The dashboard is a single-page app with two modes controlled by `IS_LANDING`:
- **Landing mode** (`/` with no `?state=`): D3 USA map + rep filter
- **Dashboard mode** (`?state=FL` etc.): Leaflet map + filterable account table

In dashboard mode, account data lives in two global JS arrays/objects:
- `allData` — flat array of account row objects loaded from `states/{CODE}/data.csv`
- `contactsByAccount` — object keyed by Account ID, loaded from `states/{CODE}/contacts.csv`

The table is rendered imperatively via `render()` → `renderTable()` which builds `<tr>` HTML strings and sets `tbody.innerHTML`.

### The magnifying glass button (prospecting trigger)
**Important disambiguation:** There are two magnifying glass icons in the UI. They are different things:

1. **Search bar** (`#search` input, line ~854): Filters the account table by name. Not the target.

2. **Google Search ext-btn** (line 1579): A per-row link in the `.ext-links` column that opens a Google search for the account. This is the button visually closest to what the prospecting trigger should be. **This is likely where the new AI prospecting button should live — as a sibling `ext-btn` in the same `.ext-links` container.**

Current Google Search button code (line 1579):
```html
<a class="ext-btn"
   href="https://www.google.com/search?q=${encodeURIComponent(r['Account Name'] + ' staff directory apply permit')}"
   target="_blank" rel="noopener" title="Search Google">
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
       stroke="currentColor" stroke-width="2.5"
       stroke-linecap="round" stroke-linejoin="round"
       color="var(--text-muted)">
    <circle cx="11" cy="11" r="7"/>
    <line x1="21" y1="21" x2="16.65" y2="16.65"/>
  </svg>
</a>
```

The new AI prospecting button should be a `<button class="ext-btn">` (not `<a>`) in the same `.ext-links` div, with a sparkle/AI icon and an `onclick` that triggers the agent call. The `.ext-links` div already has `onclick="event.stopPropagation()"` to prevent row selection.

### Existing contacts panel
**File:** `index.html`, function `buildContactPane(id)` (line ~1098)  
Called when the expand button (▶) on a row is clicked. Inserts a `<tr class="ct-detail">` immediately after the account row.

Contacts are grouped by function and rendered as:
```
[Function Header: "Building/Permitting/Inspections" | 3 contacts | last activity date]
  Full Name   |   Title   |   Last Activity
  Full Name   |   Title   |   Last Activity
[Function Header: "Planning & Zoning" | 2 contacts]
  ...
```

CSS class: `.ct-pane` > `.ct-grid` (2-column CSS grid of function sections).

---

## 2. Data Layer

### How account data is fetched
PapaParse with `download: true` fetches the CSV directly from the static file path:
```javascript
Papa.parse(`./states/${STATE_CODE}/data.csv?v=${CB}`, {
  download: true,
  header: true,
  skipEmptyLines: true,
  complete({ data }) {
    allData = data.map(r => ({ ...r, _sig: getSignal(r) }));
    render();
    loadContacts();
  },
  error() { /* show error message */ }
});
```
`CB` is a date-based cache buster: `new Date().toISOString().slice(0,10).replace(/-/g,'')`.

**No server state library** (no React Query, SWR, Redux, etc.). All data lives in plain global JS variables. No caching beyond browser HTTP cache.

### Account row shape
Each object in `allData` has these fields (from `data.csv`):
```
Account ID         — Salesforce 18-char ID (e.g. "001Hr000028ZbdJ")
Account Name       — e.g. "City Of Atlantic Beach, FL"
State              — e.g. "Florida"
Entity Type        — "Municipality" | "County" | "Township" | etc.
Owner              — Rep full name (e.g. "Ryan Minter")
Population         — string integer (e.g. "13345")
Account Status     — e.g. "Nurture" | "Open Opportunity" | ""
Tier               — "Tier S" | "Tier 1" | "Tier 2" | "Tier 3"
SQO Points         — numeric string
Lat, Lng           — float strings (empty if no geo match)
Starbridge Buyer ID — legacy UUID
Opp Status         — "Closed Won" | "Closed Lost" | ""
Stage              — Salesforce opportunity stage
Funnel Position    — "Mid Funnel" | "Top of Funnel" | ""
Sourced By, Discovery Call Date, Created Date, ARR, Previously Lost
Total Calls        — integer string
Last Call Date     — "YYYY-MM-DD" or ""
Calls - [Rep Name] — one column per rep, integer string or ""
Outreach ID        — numeric string (e.g. "874")
Salesforce ID      — may be present post-pipeline
_sig               — derived in JS: "won"|"mid"|"top"|"lost"|"touched"|"untouched"
```

### How contacts are associated with an account
Contacts CSV (`states/{CODE}/contacts.csv`) is loaded after accounts:
```javascript
function loadContacts() {
  Papa.parse(`./states/${STATE_CODE}/contacts.csv?v=${CB}`, {
    download: true, header: true, skipEmptyLines: true,
    complete({ data }) {
      contactsByAccount = {};
      data.forEach(c => {
        const id = c['Account ID'];
        if (!contactsByAccount[id]) {
          contactsByAccount[id] = { contacts: [], lastActivity: '', byFunction: {
            'Building/Permitting/Inspections': { contacts: [], lastActivity: '' },
            'Planning & Zoning':               { contacts: [], lastActivity: '' },
            'Code Enforcement':                { contacts: [], lastActivity: '' },
            'Other':                           { contacts: [], lastActivity: '' },
          }};
        }
        contactsByAccount[id].contacts.push(c);
        contactsByAccount[id].byFunction[c['Function']].contacts.push(c);
        // ... update lastActivity
      });
    },
    error() {}  // silent — contacts are optional
  });
}
```

Join key: `c['Account ID']` === `r['Account ID']` (Salesforce 18-char ID).

**No TypeScript** — no type definitions. Plain JS objects throughout.

### Function classification
The `Function` field on each contact row is a **pre-computed value** written into `contacts.csv` by `pipeline/process_contacts.py`. It is not derived at runtime.

Classification logic in `process_contacts.py` (title keyword matching):
- `Code Enforcement` — title contains "code enforcement" or "code compliance" (but not "building code")
- `Building/Permitting/Inspections` — title contains: building, permit, inspect, plans examiner, plan review, floodplain, construction code, cbo
- `Planning & Zoning` — title contains: planning, planner, zoning, growth management, community development, development services, land use, gis, geographic information
- `Other` — everything else

The four function values are hardcoded constants in both Python and JS. The UI filter maps them to short labels (bldg/plan/code/other).

---

## 3. Backend / API Layer

### ⚠️ CRITICAL: There is NO backend.

This is a 100% static-file site. No server-side code whatsoever:
- No `package.json`, no Node.js
- No `netlify.toml`, `vercel.json`, `wrangler.toml`
- No Cloudflare Workers, Lambda functions, or any serverless config
- No API routes, no proxy
- Deployment is GitHub Pages serving raw static files

**The Anthropic API cannot be called directly from the browser.** Two reasons:
1. CORS: `api.anthropic.com` does not allow cross-origin browser requests
2. Key exposure: embedding `ANTHROPIC_API_KEY` in client-side JS would expose it to anyone who opens DevTools

**A backend/proxy layer must be created as new infrastructure.** This does not exist in the repo today.

### Recommended proxy: Cloudflare Worker
Since the site is already on Cloudflare (custom domain `territory.bd-at-govwell.com`), a Cloudflare Worker is the natural fit:

- Deploy as a separate Worker at e.g. `https://territory-ai.{account}.workers.dev`
- `ANTHROPIC_API_KEY` stored as a Cloudflare Worker Secret (never in code)
- Worker receives POST from the browser, forwards to `https://api.anthropic.com/v1/messages`, streams or returns the response
- CORS headers added by the Worker to allow requests from the GitHub Pages domain
- ~20 lines of Worker code

Worker code would live in a new file at `workers/prospecting-agent.js` (or a separate Cloudflare project — both are viable).

---

## 4. Existing Patterns to Match

### Async action pattern
The only existing async patterns are both PapaParse-based (CSV loading on page init). There is **no existing pattern for a user-triggered async action** (button click → backend call → show result). This is the first such feature.

The closest analog is the Google Search ext-btn (opens a tab) — but that is synchronous navigation, not an async API call.

**The new pattern will need to be built from scratch**, matching the visual style of existing UI elements.

### Loading state
No spinners, skeleton loaders, or optimistic UI anywhere in the codebase. The only loading feedback is:
- The initial page renders instantly as landing (while CSVs load in background)
- Contacts panel expands immediately using already-loaded data (no async)

**Recommendation for new feature:** add a simple loading state to the `.ext-btn` trigger (spinner SVG swap or disabled state) and a modal/panel for the result.

### Error handling
Two patterns exist:
1. **Hard fail with visible message** — `data.csv` load failure replaces `.main` content with a red error message
2. **Silent skip** — `contacts.csv` load failure is swallowed entirely

For the prospecting agent, recommend a **visible inline error** in the result modal (e.g., "Search failed — check API connection") rather than silent failure, since the user has actively triggered the action.

---

## 5. Where New Code Should Live

Since this is a single-file app, all JS and CSS lives in `index.html`. New code should follow that convention unless the Worker is a separately deployed Cloudflare project.

| Piece | Recommended path | Notes |
|---|---|---|
| Cloudflare Worker (Anthropic proxy) | `workers/prospecting-agent.js` | Deployed separately via `wrangler` or Cloudflare dashboard; not served by GitHub Pages |
| Worker config | `workers/wrangler.toml` | Cloudflare Worker project config |
| Frontend trigger button | `index.html` line ~1579, inside `.ext-links` td | New `<button class="ext-btn" onclick="runProspectSearch(r)">` sibling of existing ext-btns |
| Frontend `runProspectSearch()` function | `index.html`, JS section | Calls Worker URL, handles loading/result/error states |
| Result modal HTML | `index.html`, body section | New `<div id="prospect-modal">` hidden by default |
| Result modal CSS | `index.html`, `<style>` block | Follow existing naming conventions (kebab-case, BEM-lite) |

### Naming conventions observed
- CSS: kebab-case (`.ext-btn`, `.ct-pane`, `.us-state-active`)
- JS functions: camelCase (`buildContactPane`, `renderTable`, `getSignal`)
- JS variables: camelCase (`allData`, `contactsByAccount`, `activeId`)
- No modules, no imports — all functions are global in the single script block
- Inline template literals for HTML generation (the `render()` / `renderTable()` pattern)

---

## 6. Environment and Secrets

### Current state
**Zero environment variables.** Everything is hardcoded:
- Salesforce org URL: `https://govwell.lightning.force.com` (hardcoded in row template)
- Outreach URL: `https://web.outreach.io` (hardcoded)
- State codes, rep names, geo coordinates: all hardcoded in JS constants
- No `.env` file, no `process.env` references, no secrets management

### Where to add ANTHROPIC_API_KEY
**Do not add it to `index.html` or any file committed to the repo.**

The key must live in the Cloudflare Worker environment:
1. In `workers/wrangler.toml`: reference it as a secret binding (not the value)
2. Set the actual value via Cloudflare dashboard → Workers → Settings → Variables → Secret:
   ```
   ANTHROPIC_API_KEY = sk-ant-...
   ```
3. In `workers/prospecting-agent.js`: access as `env.ANTHROPIC_API_KEY`

The **Worker URL** (e.g. `https://territory-ai.bd-at-govwell.workers.dev`) is safe to hardcode in `index.html` since it's not a secret.

---

## 7. Constraints and Gotchas

### CORS
The Worker must explicitly set CORS headers to allow requests from the GitHub Pages origin (`https://territory.bd-at-govwell.com` and `https://ryan-govwell.github.io`):
```
Access-Control-Allow-Origin: https://territory.bd-at-govwell.com
Access-Control-Allow-Methods: POST, OPTIONS
Access-Control-Allow-Headers: Content-Type
```
Also handle `OPTIONS` preflight requests.

### Content Security Policy
No CSP meta tag or header is currently set on `index.html`. GitHub Pages does not add a CSP by default. No CSP blocking to work around — the browser fetch to the Worker URL will work out of the box.

### No auth on the dashboard
The dashboard has **zero authentication**. Anyone with the URL can access it. The Worker should implement basic request validation (e.g., a shared secret header or origin check) to prevent the Worker endpoint from being called by arbitrary third parties and burning API credits.

Minimal approach: Worker checks `Origin` header matches the known domains. Stronger: add a static `X-Dashboard-Token` header checked by the Worker (store as a second Worker secret).

### Single-file constraint
Because all code lives in `index.html`, the prospecting feature's frontend code (button, modal, API call function) also goes there. This means no module imports, no tree-shaking, no TypeScript. Keep the new code self-contained and clearly commented with `// ── Prospecting agent ──` section headers matching the existing style.

### Contacts data is already in memory
`contactsByAccount` is fully loaded in the browser before any prospecting query runs. The existing contacts for the target account should be serialized and included in the Anthropic prompt payload — no second CSV fetch needed at query time.

### web_search tool
To actually find specific people (not just suggest roles), the Anthropic API call should use the `web_search` tool. This requires:
- Model: `claude-sonnet-4-5` or newer (tool use supported)
- Tool definition in API payload: `{"type": "web_search_20250305", "max_uses": 3}`
- Additional cost: ~$0.01–0.03 per query for search calls (negligible)
- Without it, Claude can only suggest roles from training data — cannot return real names

### Rate limiting
Anthropic API rate limits apply per API key (not per user). At 20 concurrent users, simultaneous prospecting queries could hit rate limits. Consider:
- Debouncing the button (disable after click until result returns)
- The Worker can queue or return a 429 the browser can surface gracefully

### Streaming vs. non-streaming
Anthropic supports streaming responses. For a prospecting query (5–10 second response time), streaming gives a better UX (results appear token by token). Non-streaming is simpler to implement. Recommend starting with non-streaming; streaming can be added later.

### Data freshness
`contacts.csv` is refreshed only when the Python pipeline is rerun and committed to the repo. The AI diff ("confirmed existing" contacts) is based on the last pipeline run, not live Salesforce data.

---

## Proposed Integration Architecture

```
[index.html in browser]
  └─ User clicks ✦ button on account row
  └─ JS builds payload:
       { accountName, entityType, state, population,
         existingContacts: contactsByAccount[id] }
  └─ fetch('https://territory-ai.bd-at-govwell.workers.dev/prospect', {
         method: 'POST', body: JSON.stringify(payload) })

[Cloudflare Worker: workers/prospecting-agent.js]
  └─ Validates origin
  └─ Builds Anthropic messages payload with web_search tool
  └─ POST https://api.anthropic.com/v1/messages
       Authorization: Bearer env.ANTHROPIC_API_KEY
  └─ Returns structured JSON:
       { new: [...], confirmed: [...], updates: [...], stale: [...] }

[index.html modal]
  └─ Renders diff UI:
       ✦ NEW (not in system)       — green badge
       ✓ CONFIRMED (in system)     — grey badge
       ↑ UPDATE (title changed)    — yellow badge
       ✗ STALE (in system, not found online) — red badge
```

---

## Summary of Most Important Findings

This is a **zero-backend static site** — the single most critical architectural constraint. Every byte of code is in one `index.html` file served from GitHub Pages with no server-side execution. Building the prospecting agent requires creating an entirely new backend layer (Cloudflare Worker) that does not exist today. The good news: the frontend integration point is clean and well-defined — a new `<button class="ext-btn">` in the existing `.ext-links` column (line 1576–1580 of `index.html`), calling a new `runProspectSearch(r)` function that posts to the Worker and renders results in a modal. The existing contacts for each account are already in memory in `contactsByAccount[accountId].byFunction`, structured and ready to serialize into the prompt payload. The main concerns are: (1) the Worker needs origin-based auth to prevent API key abuse since the dashboard has no login; (2) the `web_search` tool must be enabled or the agent can only suggest roles generically rather than find real people; (3) there is no existing loading-state or modal pattern to reuse — both need to be built fresh.
