import os
import re
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, HTMLResponse
from supabase import create_client, Client

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# --- SUPABASE SETUP ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# ----------------------

app = FastAPI(title="ClientBrief AI")

_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)


def normalize_email(email: str | None) -> str | None:
    """Require a full address (local@domain.tld), not a bare domain like gmail.com."""
    if not email:
        return None
    candidate = email.strip()
    if not candidate or " " in candidate:
        return None
    if candidate.count("@") != 1:
        return None
    local, _, domain = candidate.partition("@")
    if not local or not domain or "." not in domain:
        return None
    if local.startswith(".") or local.endswith("."):
        return None
    if domain.startswith(".") or domain.endswith("."):
        return None
    tld = domain.rsplit(".", 1)[-1]
    if len(tld) < 2:
        return None
    if not _EMAIL_RE.fullmatch(candidate):
        return None
    return candidate


def call_groq(system_msg: str, user_msg: str, max_tokens: int = 200) -> str:
    """
    Shared helper used by routes so the Groq-calling logic only lives in
    one place. Raises RuntimeError with a readable message if the request fails.
    """
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": max_tokens,
    }
    response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"Groq API error ({response.status_code}): {response.text}")

    data = response.json()
    return (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )


@app.get("/generate-brief")
def generate_brief(
    notes: str = Query(..., description="Rough, unstructured notes from a client"),
    email: str | None = Query(None, description="Email captured by the frontend's email gate"),
):
    """Turns messy client notes into a structured, professional client brief."""
    if not GROQ_API_KEY:
        return JSONResponse(status_code=500, content={"error": "GROQ_API_KEY not set in environment."})

    try:
        plan = call_groq(
            system_msg=(
                "You are a Senior Account Manager at a boutique creative agency. Take the "
                "user's rough, messy notes from a client and transform them into a clear, "
                "professional Client Brief an account director can send to production. Include: "
                "1. Project Overview, 2. Business Goals, 3. Target Audience, 4. Scope of "
                "Work, 5. Deliverables, 6. Assumptions & Open Questions, 7. Suggested Timeline. "
                "Fill gaps with sensible assumptions and flag them explicitly. "
                "CRITICAL FORMATTING: Do NOT use Markdown (no **, no *, no #). Plain text only. "
                "Use ALL-CAPS for section headers."
            ),
            user_msg=(
                f"Turn the following rough client notes into a structured client brief:\n"
                f"Client notes: {notes}\n"
                f"List each section as 1., 2., 3., 4., 5., 6., 7."
            ),
            max_tokens=800,
        )
    except RuntimeError as e:
        return JSONResponse(status_code=502, content={"error": str(e)})

    try:
        insert_data = {"notes": notes, "brief": plan}
        stored_email = normalize_email(email)
        if stored_email:
            insert_data["email"] = stored_email
        supabase.table("b2b_briefs").insert(insert_data).execute()
    except Exception as e:
        print(f"Database Error: {e}")

    return {"plan": plan}


@app.get("/", response_class=HTMLResponse)
async def root():
    html_content = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>ClientBrief — Structured briefs for agency account teams</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="For boutique creative, performance, and dev shops: turn vague client intake into a scoped brief before scope creep eats your margin.">
    <meta name="theme-color" content="#EDE8DF">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&family=Source+Sans+3:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #EDE8DF;
            --paper: #FAF7F2;
            --ink: #1C2430;
            --muted: #5C6570;
            --line: #C9C0B4;
            --accent: #8B3A2F;
            --accent-soft: #E8D4CF;
            --error: #A12828;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background: var(--bg);
            color: var(--ink);
            font-family: 'Source Sans 3', system-ui, sans-serif;
            font-size: 17px;
            line-height: 1.55;
            -webkit-font-smoothing: antialiased;
        }
        .wrap { max-width: 1080px; margin: 0 auto; padding: 0 24px; }
        a { color: inherit; text-decoration: none; }
        section[id] { scroll-margin-top: 72px; }

        .site-bar {
            border-bottom: 1px solid var(--line);
            background: rgba(237, 232, 223, 0.92);
            backdrop-filter: blur(8px);
            position: sticky;
            top: 0;
            z-index: 20;
        }
        .site-bar .wrap {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 16px;
            padding-top: 18px;
            padding-bottom: 18px;
            flex-wrap: wrap;
        }
        .logo {
            font-family: 'Libre Baskerville', Georgia, serif;
            font-size: 1.15rem;
            letter-spacing: -0.02em;
        }
        .logo small {
            display: block;
            font-family: 'Source Sans 3', sans-serif;
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: var(--muted);
            margin-top: 2px;
        }
        .site-bar nav { display: flex; gap: 22px; font-size: 0.92rem; color: var(--muted); }
        .site-bar nav a:hover { color: var(--ink); }
        .pill-link {
            font-size: 0.85rem;
            font-weight: 600;
            border: 1px solid var(--ink);
            padding: 8px 14px;
            border-radius: 999px;
            white-space: nowrap;
        }
        .pill-link:hover { background: var(--ink); color: var(--paper); }

        .hero { padding: 56px 0 40px; }
        .hero-grid {
            display: grid;
            grid-template-columns: 1.15fr 0.85fr;
            gap: 40px;
            align-items: start;
        }
        .kicker {
            font-size: 0.8rem;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--accent);
            margin-bottom: 14px;
        }
        .hero h1 {
            font-family: 'Libre Baskerville', Georgia, serif;
            font-size: clamp(2rem, 4.5vw, 2.85rem);
            line-height: 1.15;
            font-weight: 700;
            margin-bottom: 18px;
        }
        .hero h1 em { font-style: italic; font-weight: 400; }
        .hero .lede { color: var(--muted); max-width: 34rem; margin-bottom: 22px; }
        .hero-note {
            font-size: 0.9rem;
            color: var(--muted);
            border-left: 3px solid var(--accent);
            padding-left: 14px;
            max-width: 28rem;
        }
        .for-whom {
            background: var(--paper);
            border: 1px solid var(--line);
            padding: 22px 20px;
        }
        .for-whom h2 {
            font-family: 'Libre Baskerville', serif;
            font-size: 1.05rem;
            margin-bottom: 10px;
        }
        .for-whom ul { list-style: none; font-size: 0.92rem; color: var(--muted); }
        .for-whom li { padding: 6px 0; border-top: 1px solid var(--line); }
        .for-whom li:first-child { border-top: none; padding-top: 0; }

        .strip {
            border-top: 1px solid var(--line);
            border-bottom: 1px solid var(--line);
            padding: 28px 0;
            background: var(--paper);
        }
        .strip .wrap {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            font-size: 0.92rem;
        }
        .strip strong { display: block; font-size: 1rem; margin-bottom: 4px; color: var(--ink); }

        .workspace { padding: 48px 0 64px; }
        .workspace-head { margin-bottom: 20px; }
        .workspace-head h2 {
            font-family: 'Libre Baskerville', serif;
            font-size: 1.65rem;
        }
        .workspace-head p { color: var(--muted); margin-top: 8px; font-size: 0.95rem; }
        .desk {
            display: grid;
            grid-template-columns: 1fr 1fr;
            border: 1px solid var(--line);
            background: var(--paper);
            min-height: 520px;
        }
        .desk-in, .desk-out { padding: 22px; display: flex; flex-direction: column; }
        .desk-out { border-left: 1px solid var(--line); background: #FFFCF8; }
        .field-label {
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--muted);
            margin-bottom: 10px;
        }
        textarea#notes-input {
            flex: 1;
            min-height: 280px;
            width: 100%;
            border: 1px dashed var(--line);
            background: transparent;
            padding: 14px;
            font-family: 'Source Sans 3', sans-serif;
            font-size: 1rem;
            line-height: 1.5;
            color: var(--ink);
            resize: vertical;
            outline: none;
        }
        textarea#notes-input:focus { border-color: var(--accent); border-style: solid; }
        .field-error { color: var(--error); font-size: 0.85rem; min-height: 1.2em; margin-top: 8px; }
        .btn-draft {
            margin-top: 14px;
            width: 100%;
            background: var(--accent);
            color: #fff;
            border: none;
            padding: 14px 18px;
            font-family: inherit;
            font-size: 0.95rem;
            font-weight: 700;
            cursor: pointer;
        }
        .btn-draft:hover { filter: brightness(1.05); }
        .btn-draft:disabled { opacity: 0.65; cursor: wait; }

        .out-meta {
            display: flex;
            justify-content: space-between;
            gap: 8px;
            font-size: 0.72rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: var(--muted);
            padding-bottom: 12px;
            border-bottom: 1px solid var(--line);
            margin-bottom: 16px;
        }
        .out-placeholder {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            color: var(--muted);
            font-size: 0.92rem;
            padding: 24px;
        }
        #result-body { display: none; }
        #result-body.visible { display: block; }
        #result-body h3 {
            font-family: 'Libre Baskerville', serif;
            font-size: 1.05rem;
            margin: 18px 0 6px;
        }
        #result-body h3:first-child { margin-top: 0; }
        #result-body p { font-size: 0.92rem; color: var(--muted); margin-bottom: 6px; }
        .btn-copy {
            margin-top: auto;
            align-self: flex-start;
            background: transparent;
            border: 1px solid var(--ink);
            padding: 8px 14px;
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            cursor: pointer;
            display: none;
        }
        .btn-copy.visible { display: inline-block; }

        .faq { padding: 40px 0 56px; border-top: 1px solid var(--line); }
        .faq h2 {
            font-family: 'Libre Baskerville', serif;
            font-size: 1.4rem;
            margin-bottom: 16px;
        }
        details {
            border-bottom: 1px solid var(--line);
            padding: 14px 0;
        }
        summary {
            cursor: pointer;
            font-weight: 600;
            list-style: none;
        }
        summary::-webkit-details-marker { display: none; }
        details p { color: var(--muted); font-size: 0.92rem; margin-top: 10px; max-width: 40rem; }

        footer {
            padding: 28px 0 40px;
            font-size: 0.82rem;
            color: var(--muted);
            border-top: 1px solid var(--line);
        }

        .gate-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(28, 36, 48, 0.55);
            align-items: center;
            justify-content: center;
            padding: 20px;
            z-index: 100;
        }
        .gate-overlay.visible { display: flex; }
        .gate-card {
            background: var(--paper);
            border: 1px solid var(--line);
            max-width: 420px;
            width: 100%;
            padding: 32px 28px;
            position: relative;
            box-shadow: 0 18px 40px rgba(28, 36, 48, 0.12);
        }
        .gate-card h2 {
            font-family: 'Libre Baskerville', serif;
            font-size: 1.45rem;
            margin-bottom: 8px;
        }
        .gate-card p { color: var(--muted); font-size: 0.92rem; margin-bottom: 16px; }
        input#gate-email {
            width: 100%;
            border: 1px solid var(--line);
            padding: 12px 14px;
            font: inherit;
            margin-bottom: 8px;
            background: #fff;
        }
        input#gate-email:focus { outline: 2px solid var(--accent-soft); border-color: var(--accent); }
        input#gate-email.invalid { border-color: var(--error); }
        .gate-close {
            position: absolute;
            top: 10px;
            right: 12px;
            border: none;
            background: none;
            font-size: 1.4rem;
            cursor: pointer;
            color: var(--muted);
        }
        .btn-gate {
            width: 100%;
            margin-top: 8px;
            background: var(--ink);
            color: #fff;
            border: none;
            padding: 12px;
            font: inherit;
            font-weight: 700;
            cursor: pointer;
        }

        @media (max-width: 860px) {
            .hero-grid, .desk, .strip .wrap { grid-template-columns: 1fr; }
            .desk-out { border-left: none; border-top: 1px solid var(--line); }
            .site-bar nav { display: none; }
        }
    </style>
</head>
<body>
    <header class="site-bar">
        <div class="wrap">
            <div class="logo">
                ClientBrief
                <small>For agency account teams</small>
            </div>
            <nav>
                <a href="#why">Why</a>
                <a href="#tool">Try it</a>
                <a href="#faq">FAQ</a>
            </nav>
            <a class="pill-link" href="#tool">Draft a brief</a>
        </div>
    </header>

    <section class="hero">
        <div class="wrap hero-grid">
            <div>
                <p class="kicker">Stage 1 · MVP for shops under $1M</p>
                <h1>Turn a messy client intake into a <em>brief your team can scope.</em></h1>
                <p class="lede">Account directors at boutique creative, performance, and dev agencies still lose billable hours rewriting vague kickoff notes. ClientBrief structures the ramble—before scope creep and revision loops do the damage.</p>
                <p class="hero-note">Paste an email thread, Slack dump, or call transcript. You get sections, assumptions called out, and a timeline you can push back on in the next client call.</p>
            </div>
            <aside class="for-whom" id="why">
                <h2>Built for teams like yours</h2>
                <ul>
                    <li>Creative &amp; brand boutiques (5–25 people)</li>
                    <li>Performance marketing shops juggling fast turn briefs</li>
                    <li>Software studios translating non-technical client notes</li>
                </ul>
            </aside>
        </div>
    </section>

    <div class="strip">
        <div class="wrap">
            <div>
                <strong>Problem we heard</strong>
                Incomplete intakes → fuzzy scope → unpaid rework.
            </div>
            <div>
                <strong>What you get</strong>
                Seven-part brief with assumptions &amp; open questions listed upfront.
            </div>
            <div>
                <strong>Pricing direction</strong>
                Self-serve from $49–$99/mo with clear generation caps—not unlimited usage.
            </div>
        </div>
    </div>

    <section class="workspace" id="tool">
        <div class="wrap">
            <div class="workspace-head">
                <h2>Your desk</h2>
                <p>No login for the demo—just your work email the first time you generate, so we know who's actually in an agency seat.</p>
            </div>
            <div class="desk">
                <div class="desk-in">
                    <label class="field-label" for="notes-input">Raw client notes</label>
                    <textarea id="notes-input" placeholder="Example: 'Need something for Q4 launch — social, maybe landing page. Budget TBD. Client hates purple. Competitor X just did a rebrand…'"></textarea>
                    <div class="field-error" id="notes-error"></div>
                    <button class="btn-draft" id="draft-btn" type="button">Structure this brief</button>
                </div>
                <div class="desk-out">
                    <div class="out-meta">
                        <span>Job <span id="doc-ref">—</span></span>
                        <span id="doc-date">Draft</span>
                    </div>
                    <div class="out-placeholder" id="placeholder-state">Your brief lands here—ready to paste into Notion, Google Docs, or your PM tool.</div>
                    <div id="result-body"></div>
                    <button class="btn-copy" id="copy-btn" type="button">Copy to clipboard</button>
                </div>
            </div>
        </div>
    </section>

    <section class="faq" id="faq">
        <div class="wrap">
            <h2>Questions account leads actually ask</h2>
            <details>
                <summary>Does this replace my strategist?</summary>
                <p>No. It gets you from blank doc to a solid first pass in about a minute. You still own tone, pricing, and what goes to the client.</p>
            </details>
            <details>
                <summary>Why ask for my email?</summary>
                <p>We're validating demand with real agency inboxes—not just someone typing @gmail.com. We need your full address (name@yourshop.com).</p>
            </details>
            <details>
                <summary>What happens to client data?</summary>
                <p>Notes and generated briefs are stored so you can revisit them. Nothing is emailed to your client automatically.</p>
            </details>
            <details>
                <summary>How will pricing work?</summary>
                <p>Flat monthly subscription with a fixed number of brief generations per month—designed to keep margins healthy while you're still proving unit economics.</p>
            </details>
        </div>
    </section>

    <footer>
        <div class="wrap">© 2026 ClientBrief · Made for agencies that track billable hours seriously.</div>
    </footer>

    <div class="gate-overlay" id="email-gate">
        <div class="gate-card">
            <button class="gate-close" id="gate-close" type="button" aria-label="Close">&times;</button>
            <h2>One quick thing</h2>
            <p>Enter your full work email—first name, @, and company domain. We can't use entries like <em>gmail.com</em> or <em>@agency.com</em> alone.</p>
            <input type="text" id="gate-email" autocomplete="email" inputmode="email" spellcheck="false" placeholder="alex@northwind.studio" aria-label="Work email address">
            <div class="field-error" id="gate-error"></div>
            <button class="btn-gate" id="gate-submit" type="button">Continue &amp; generate</button>
        </div>
    </div>

    <script>
        const EMAIL_KEY = 'clientbrief_email';
        let pendingNotes = null;

        function getSavedEmail() {
            try { return localStorage.getItem(EMAIL_KEY); } catch (e) { return null; }
        }
        function saveEmail(email) {
            try { localStorage.setItem(EMAIL_KEY, email); } catch (e) { /* ignore */ }
        }
        function clearSavedEmail() {
            try { localStorage.removeItem(EMAIL_KEY); } catch (e) { /* ignore */ }
        }

        function isValidEmail(raw) {
            const email = (raw || '').trim();
            if (!email || email.indexOf(' ') !== -1) return false;
            if ((email.match(/@/g) || []).length !== 1) return false;
            const at = email.indexOf('@');
            const local = email.slice(0, at);
            const domain = email.slice(at + 1);
            if (!local || !domain) return false;
            if (local.startsWith('.') || local.endsWith('.')) return false;
            if (domain.startsWith('.') || domain.endsWith('.') || domain.indexOf('.') === -1) return false;
            const labels = domain.split('.');
            if (labels.some(function (part) { return !part.length; })) return false;
            if (labels[labels.length - 1].length < 2) return false;
            return /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$/.test(email);
        }

        function openGate() { document.getElementById('email-gate').classList.add('visible'); }
        function closeGate() { document.getElementById('email-gate').classList.remove('visible'); }

        function renderBrief(text) {
            const resultBody = document.getElementById('result-body');
            const placeholder = document.getElementById('placeholder-state');
            const copyBtn = document.getElementById('copy-btn');
            resultBody.innerHTML = '';
            const clean = text.replace(/\*\*/g, '').replace(/\*/g, '');
            clean.split('\n').forEach(function (line) {
                const trimmed = line.trim();
                if (!trimmed) return;
                const el = document.createElement(/^\d+\.\s/.test(trimmed) ? 'h3' : 'p');
                el.textContent = trimmed;
                resultBody.appendChild(el);
            });
            placeholder.style.display = 'none';
            resultBody.classList.add('visible');
            copyBtn.classList.add('visible');
            document.getElementById('doc-ref').textContent = String(Math.floor(1000 + Math.random() * 9000));
            document.getElementById('doc-date').textContent = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
        }

        async function draftBrief(notes, email) {
            const btn = document.getElementById('draft-btn');
            const notesError = document.getElementById('notes-error');
            const placeholder = document.getElementById('placeholder-state');
            const resultBody = document.getElementById('result-body');
            const copyBtn = document.getElementById('copy-btn');
            btn.disabled = true;
            btn.textContent = 'Working…';
            notesError.textContent = '';
            resultBody.classList.remove('visible');
            copyBtn.classList.remove('visible');
            placeholder.style.display = 'flex';
            placeholder.textContent = 'Reading the notes and drafting sections…';

            try {
                let url = '/generate-brief?notes=' + encodeURIComponent(notes);
                if (email) url += '&email=' + encodeURIComponent(email);
                const response = await fetch(url);
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'Could not generate the brief.');
                renderBrief(data.plan || '');
            } catch (e) {
                placeholder.style.display = 'flex';
                placeholder.textContent = e.message || 'Something went wrong. Try again in a moment.';
            } finally {
                btn.disabled = false;
                btn.textContent = 'Structure this brief';
            }
        }

        document.getElementById('draft-btn').addEventListener('click', function () {
            const notes = document.getElementById('notes-input').value.trim();
            const errorEl = document.getElementById('notes-error');
            if (!notes) {
                errorEl.textContent = 'Paste client notes first—even half a paragraph is enough.';
                return;
            }
            errorEl.textContent = '';
            const savedEmail = getSavedEmail();
            if (savedEmail && isValidEmail(savedEmail)) {
                draftBrief(notes, savedEmail);
            } else {
                if (savedEmail) clearSavedEmail();
                pendingNotes = notes;
                openGate();
            }
        });

        document.getElementById('gate-submit').addEventListener('click', function () {
            const input = document.getElementById('gate-email');
            const email = input.value.trim();
            const gateError = document.getElementById('gate-error');
            if (!isValidEmail(email)) {
                input.classList.add('invalid');
                gateError.textContent = 'Use your full address (e.g. sam@youragency.com)—not just a domain.';
                return;
            }
            input.classList.remove('invalid');
            gateError.textContent = '';
            saveEmail(email);
            closeGate();
            if (pendingNotes) {
                draftBrief(pendingNotes, email);
                pendingNotes = null;
            }
        });

        document.getElementById('gate-close').addEventListener('click', function () {
            closeGate();
            pendingNotes = null;
        });
        document.getElementById('gate-email').addEventListener('keyup', function (e) {
            if (e.key === 'Enter') document.getElementById('gate-submit').click();
        });
        document.getElementById('gate-email').addEventListener('input', function () {
            this.classList.remove('invalid');
            document.getElementById('gate-error').textContent = '';
        });
        document.getElementById('notes-input').addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                document.getElementById('draft-btn').click();
            }
        });
        document.getElementById('copy-btn').addEventListener('click', async function () {
            const text = document.getElementById('result-body').innerText;
            const btn = this;
            try {
                await navigator.clipboard.writeText(text);
                const original = btn.textContent;
                btn.textContent = 'Copied';
                setTimeout(function () { btn.textContent = original; }, 2000);
            } catch (e) {
                alert('Copy failed—select the brief text manually.');
            }
        });
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)
