import os
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
                "You are a Senior Account Manager at a premium creative agency. Take the "
                "user's rough, messy notes from a client and transform them into a highly "
                "professional, comprehensive Client Brief. Include these sections: "
                "1. Project Overview, 2. Business Goals, 3. Target Audience, 4. Scope of "
                "Work, 5. Deliverables. Make logical assumptions to fill in any gaps. Use "
                "formal, premium corporate language."
                "CRITICAL FORMATTING: Do NOT use any Markdown formatting (no **, no *, no #). Use plain text only. Use ALL-CAPS for section headers."
            ),
            user_msg=(
                f"Turn the following rough client notes into a structured client brief:\n"
                f"Client notes: {notes}\n"
                f"List each section as 1., 2., 3., 4., 5."
            ),
            max_tokens=512,
        )
    except RuntimeError as e:
        return JSONResponse(status_code=502, content={"error": str(e)})

    try:
        insert_data = {"notes": notes, "brief": plan}
        if email:
            insert_data["email"] = email
        # Changed from "saved_plans" to "b2b_briefs"
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
    <title>ClientBrief AI</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,500;8..60,600;8..60,700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0e0f13;
            --surface: #17181e;
            --surface-border: #272932;
            --text: #ece8dd;
            --text-muted: #8d8b85;
            --paper: #f2ead9;
            --paper-ink: #2b2416;
            --paper-ink-soft: #5c4f3a;
            --accent: #8c2f39;
            --accent-bright: #ab3d49;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            min-height: 100vh;
            background: var(--bg);
            color: var(--text);
            font-family: 'IBM Plex Sans', system-ui, sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 56px 20px 80px;
        }
        .wordmark {
            font-family: 'Source Serif 4', Georgia, serif;
            font-size: 1.7rem;
            font-weight: 600;
            letter-spacing: 0.01em;
        }
        .wordmark span { color: var(--accent); }
        .tagline {
            color: var(--text-muted);
            max-width: 460px;
            text-align: center;
            margin: 10px 0 40px;
            line-height: 1.55;
            font-size: 0.97rem;
        }
        .card {
            background: var(--surface);
            border: 1px solid var(--surface-border);
            border-radius: 10px;
            padding: 28px;
            width: 100%;
            max-width: 560px;
        }
        .field-label {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.72rem;
            letter-spacing: 0.14em;
            color: var(--text-muted);
            text-transform: uppercase;
            display: block;
            margin-bottom: 10px;
        }
        textarea#notes-input {
            width: 100%;
            min-height: 140px;
            resize: vertical;
            background: #0b0c10;
            border: 1px solid var(--surface-border);
            border-radius: 8px;
            color: var(--text);
            font-family: 'IBM Plex Sans', sans-serif;
            font-size: 0.96rem;
            line-height: 1.5;
            padding: 14px;
            outline: none;
        }
        textarea#notes-input:focus-visible { border-color: var(--accent); }
        .error-text {
            display: none;
            color: #e2909a;
            font-size: 0.85rem;
            margin-top: 8px;
        }
        .error-text.visible { display: block; }
        button.primary {
            margin-top: 16px;
            width: 100%;
            background: var(--accent);
            color: #f8f1ea;
            border: none;
            border-radius: 8px;
            padding: 13px;
            font-family: 'IBM Plex Sans', sans-serif;
            font-size: 0.98rem;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.15s ease;
        }
        button.primary:hover { background: var(--accent-bright); }
        button.primary:disabled { opacity: 0.6; cursor: default; }
        button.primary:focus-visible { outline: 2px solid var(--accent-bright); outline-offset: 2px; }

        .doc-wrap { display: none; width: 100%; max-width: 560px; margin-top: 28px; }
        .doc-wrap.visible { display: block; }
        .doc {
            background: var(--paper);
            color: var(--paper-ink);
            border-radius: 4px;
            padding: 36px 40px;
            box-shadow: 0 20px 50px -20px rgba(0,0,0,0.6);
        }
        .doc-letterhead {
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 6px;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.7rem;
            letter-spacing: 0.1em;
            color: var(--paper-ink-soft);
            text-transform: uppercase;
            border-bottom: 1px solid rgba(43,36,22,0.25);
            padding-bottom: 12px;
            margin-bottom: 20px;
        }
        .doc h3 {
            font-family: 'Source Serif 4', Georgia, serif;
            font-size: 1.08rem;
            margin: 22px 0 6px;
        }
        .doc h3:first-child { margin-top: 0; }
        .doc p {
            font-family: 'Source Serif 4', Georgia, serif;
            font-size: 0.98rem;
            line-height: 1.65;
            margin: 0 0 6px;
        }
        .copy-link {
            display: inline-block;
            margin-top: 14px;
            background: none;
            border: none;
            color: var(--text-muted);
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.78rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            cursor: pointer;
            padding: 0;
        }
        .copy-link:hover { color: var(--text); }

        .gate-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(10,10,13,0.72);
            align-items: center;
            justify-content: center;
            padding: 20px;
            z-index: 10;
        }
        .gate-overlay.visible { display: flex; }
        .gate-card {
            background: var(--surface);
            border: 1px solid var(--surface-border);
            border-radius: 10px;
            padding: 32px;
            max-width: 380px;
            width: 100%;
            text-align: center;
            position: relative;
        }
        .gate-seal {
            width: 44px;
            height: 44px;
            border: 2px solid var(--accent);
            border-radius: 50%;
            margin: 0 auto 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'Source Serif 4', serif;
            color: var(--accent);
            font-size: 1.05rem;
        }
        .gate-card h2 { font-family: 'Source Serif 4', serif; font-size: 1.3rem; margin: 0 0 8px; }
        .gate-card p.gate-copy { color: var(--text-muted); font-size: 0.9rem; margin: 0 0 20px; line-height: 1.5; }
        input#gate-email {
            width: 100%;
            background: #0b0c10;
            border: 1px solid var(--surface-border);
            border-radius: 8px;
            color: var(--text);
            font-family: 'IBM Plex Sans', sans-serif;
            font-size: 0.95rem;
            padding: 12px 14px;
            outline: none;
            margin-bottom: 12px;
        }
        input#gate-email:focus-visible { border-color: var(--accent); }
        .gate-close {
            position: absolute;
            top: 14px;
            right: 16px;
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 1.2rem;
            cursor: pointer;
            line-height: 1;
        }
        .gate-close:hover { color: var(--text); }

        @media (prefers-reduced-motion: reduce) {
            * { transition: none !important; }
        }
        @media (max-width: 480px) {
            .doc { padding: 26px 22px; }
            .card { padding: 22px; }
        }
    </style>
</head>
<body>
    <div class="wordmark">Client<span>Brief</span> AI</div>
    <p class="tagline">Paste the rambling client email. Get back a brief you could send with your name on it.</p>

    <div class="card">
        <label class="field-label" for="notes-input">Client notes</label>
        <textarea id="notes-input" placeholder="e.g. hey can u whip up smth for the launch, need social + a landing page, budget is tight, oh and my sister said purple is unlucky so no purple..."></textarea>
        <div class="error-text" id="notes-error"></div>
        <button class="primary" id="draft-btn" type="button">Draft the Brief</button>
    </div>

    <div class="doc-wrap" id="result-wrap">
        <div class="doc">
            <div class="doc-letterhead">
                <span id="doc-ref">REF: CB-0000</span>
                <span id="doc-date">DATE: —</span>
                <span>STATUS: DRAFT</span>
            </div>
            <div id="result-body"></div>
        </div>
        <button class="copy-link" id="copy-btn" type="button">Copy brief</button>
    </div>

    <div class="gate-overlay" id="email-gate">
        <div class="gate-card">
            <button class="gate-close" id="gate-close" type="button" aria-label="Close">×</button>
            <div class="gate-seal">CB</div>
            <h2>Unlock your brief</h2>
            <p class="gate-copy">Enter your email and we'll reveal the full document. No spam, just briefs.</p>
            <input type="email" id="gate-email" placeholder="you@agency.com" aria-label="Email address">
            <div class="error-text" id="gate-error"></div>
            <button class="primary" id="gate-submit" type="button">Reveal My Brief</button>
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
        function isValidEmail(email) {
            return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
        }
        function openGate() { document.getElementById('email-gate').classList.add('visible'); }
        function closeGate() { document.getElementById('email-gate').classList.remove('visible'); }

        function renderBrief(text) {
            const resultBody = document.getElementById('result-body');
            resultBody.innerHTML = '';
            text.split('\n').forEach(function (line) {
                const trimmed = line.trim();
                if (!trimmed) return;
                const el = document.createElement(/^\d+\.\s/.test(trimmed) ? 'h3' : 'p');
                el.textContent = trimmed;
                resultBody.appendChild(el);
            });
            document.getElementById('doc-ref').textContent =
                'REF: CB-' + Math.floor(1000 + Math.random() * 9000);
            document.getElementById('doc-date').textContent =
                'DATE: ' + new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).toUpperCase();
        }

        async function draftBrief(notes, email) {
            const resultWrap = document.getElementById('result-wrap');
            const btn = document.getElementById('draft-btn');
            btn.disabled = true;
            btn.textContent = 'Drafting your brief…';
            resultWrap.classList.remove('visible');

            try {
                let url = '/generate-brief?notes=' + encodeURIComponent(notes);
                if (email) url += '&email=' + encodeURIComponent(email);
                const response = await fetch(url);
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.error || 'Something went wrong drafting your brief.');
                }
                renderBrief(data.plan || '');
                resultWrap.classList.add('visible');
                resultWrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
            } catch (e) {
                renderBrief(e.message || 'Something went wrong drafting your brief. Try again in a moment.');
                resultWrap.classList.add('visible');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Draft the Brief';
            }
        }

        document.getElementById('draft-btn').addEventListener('click', function () {
            const notes = document.getElementById('notes-input').value.trim();
            const errorEl = document.getElementById('notes-error');
            if (!notes) {
                errorEl.textContent = 'Paste some client notes first — even the messy stuff works.';
                errorEl.classList.add('visible');
                return;
            }
            errorEl.classList.remove('visible');

            const savedEmail = getSavedEmail();
            if (savedEmail) {
                draftBrief(notes, savedEmail);
            } else {
                pendingNotes = notes;
                openGate();
            }
        });

        document.getElementById('gate-submit').addEventListener('click', function () {
            const email = document.getElementById('gate-email').value.trim();
            const gateError = document.getElementById('gate-error');
            if (!isValidEmail(email)) {
                gateError.textContent = "That doesn't look like a valid email — try again.";
                gateError.classList.add('visible');
                return;
            }
            gateError.classList.remove('visible');
            saveEmail(email);
            closeGate();
            if (pendingNotes) {
                draftBrief(pendingNotes, email);
                pendingNotes = null;
            }
        });

        document.getElementById('gate-close').addEventListener('click', closeGate);
        document.getElementById('gate-email').addEventListener('keyup', function (e) {
            if (e.key === 'Enter') document.getElementById('gate-submit').click();
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
                btn.textContent = 'Copied!';
                setTimeout(function () { btn.textContent = original; }, 1500);
            } catch (e) {
                alert('Could not copy automatically — select the text and copy manually.');
            }
        });
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)