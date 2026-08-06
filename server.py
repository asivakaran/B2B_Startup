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
    <title>ClientBrief AI — Structured briefs from messy notes</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="An AI tool for creative agencies that turns vague, messy client emails into structured, professional project briefs.">
    <meta name="theme-color" content="#0e0f13">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0e0f13;
            --surface: #17181e;
            --border: #272932;
            --text: #ece8dd;
            --text-muted: #8b8d98;
            --accent: #8c2f39;
            --accent-hover: #a23a45;
            --paper: #f2ead9;
            --paper-ink: #2b2013;
            --paper-ink-soft: #5f4d34;
            --paper-border: rgba(43, 32, 19, 0.2);
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            background: var(--bg);
            color: var(--text);
            font-family: 'IBM Plex Sans', system-ui, sans-serif;
            -webkit-font-smoothing: antialiased;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 48px 24px;
        }

        .container {
            width: 100%;
            max-width: 560px;
            display: flex;
            flex-direction: column;
            gap: 32px;
        }

        /* ---------- HEADER ---------- */
        .header {
            text-align: center;
            margin-bottom: 8px;
        }
        .wordmark {
            font-family: 'IBM Plex Sans', sans-serif;
            font-size: 1.5rem;
            font-weight: 600;
            letter-spacing: -0.02em;
            color: var(--text);
        }
        .wordmark span {
            color: var(--accent);
        }
        .tagline {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 8px;
            letter-spacing: 0.02em;
        }

        /* ---------- INPUT CARD ---------- */
        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .label {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.75rem;
            font-weight: 500;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }

        textarea {
            width: 100%;
            min-height: 140px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text);
            font-family: 'IBM Plex Sans', sans-serif;
            font-size: 0.95rem;
            line-height: 1.5;
            padding: 16px;
            outline: none;
            resize: vertical;
            transition: border-color 0.2s ease;
        }
        textarea:focus {
            border-color: var(--accent);
        }
        textarea::placeholder {
            color: #555765;
        }

        .btn-primary {
            width: 100%;
            background: var(--accent);
            color: #fff;
            border: none;
            border-radius: 6px;
            padding: 14px 20px;
            font-family: 'IBM Plex Sans', sans-serif;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        .btn-primary:hover {
            background: var(--accent-hover);
        }
        .btn-primary:disabled {
            opacity: 0.7;
            cursor: not-allowed;
        }

        .error-text {
            color: #e57373;
            font-size: 0.85rem;
            display: none;
        }
        .error-text.visible {
            display: block;
        }

        /* ---------- OUTPUT DOCUMENT ---------- */
        .doc-wrap {
            display: none;
            flex-direction: column;
            gap: 12px;
        }
        .doc-wrap.visible {
            display: flex;
        }

        .doc {
            background: var(--paper);
            color: var(--paper-ink);
            border-radius: 4px;
            padding: 40px;
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
            font-family: 'Source Serif 4', Georgia, serif;
            position: relative;
        }

        .letterhead {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--paper-ink-soft);
            border-bottom: 1px solid var(--paper-border);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }
        .letterhead .status {
            background: var(--paper-ink);
            color: var(--paper);
            padding: 2px 8px;
            border-radius: 3px;
        }

        .doc h3 {
            font-size: 1.1rem;
            font-weight: 600;
            margin-top: 20px;
            margin-bottom: 8px;
        }
        .doc h3:first-child {
            margin-top: 0;
        }
        .doc p {
            font-size: 0.95rem;
            line-height: 1.65;
            margin-bottom: 8px;
            color: var(--paper-ink-soft);
        }

        .copy-btn {
            align-self: center;
            background: none;
            border: none;
            color: var(--text-muted);
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            cursor: pointer;
            padding: 8px;
            transition: color 0.2s ease;
        }
        .copy-btn:hover {
            color: var(--text);
        }

        /* ---------- EMAIL GATE OVERLAY ---------- */
        .gate-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(14, 15, 19, 0.85);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            z-index: 100;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }
        .gate-overlay.visible {
            display: flex;
        }

        .gate-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 40px;
            max-width: 400px;
            width: 100%;
            text-align: center;
            position: relative;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
        }

        .gate-close {
            position: absolute;
            top: 16px;
            right: 16px;
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 1.5rem;
            line-height: 1;
            cursor: pointer;
            transition: color 0.2s ease;
        }
        .gate-close:hover {
            color: var(--text);
        }

        .gate-seal {
            width: 56px;
            height: 56px;
            border-radius: 50%;
            border: 2px solid var(--accent);
            color: var(--accent);
            font-family: 'IBM Plex Sans', sans-serif;
            font-weight: 700;
            font-size: 1.2rem;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 24px;
        }

        .gate-card h2 {
            font-family: 'IBM Plex Sans', sans-serif;
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 8px;
        }
        .gate-card p {
            color: var(--text-muted);
            font-size: 0.9rem;
            line-height: 1.5;
            margin-bottom: 24px;
        }

        .gate-input {
            width: 100%;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text);
            font-family: 'IBM Plex Sans', sans-serif;
            font-size: 0.95rem;
            padding: 12px 16px;
            outline: none;
            margin-bottom: 16px;
            transition: border-color 0.2s ease;
        }
        .gate-input:focus {
            border-color: var(--accent);
        }

        .spinner {
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255,255,255,0.3);
            border-top-color: #fff;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            display: none;
        }
        .btn-primary.loading .spinner {
            display: block;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        @media (max-width: 480px) {
            .doc {
                padding: 24px;
            }
            .letterhead {
                font-size: 0.65rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <div class="wordmark">Client<span>Brief</span> AI</div>
            <div class="tagline">From messy notes to structured briefs in seconds.</div>
        </header>

        <div class="card">
            <div class="label">Client Notes</div>
            <textarea id="notes-input" placeholder="e.g. hey can u whip up smth for the launch, need social + a landing page, budget is tight, oh and my sister said purple is unlucky so no purple..."></textarea>
            <div class="error-text" id="notes-error"></div>
            <button class="btn-primary" id="draft-btn" type="button">
                <span class="spinner"></span>
                <span class="btn-text">Draft the Brief</span>
            </button>
        </div>

        <div class="doc-wrap" id="result-wrap">
            <div class="doc">
                <div class="letterhead">
                    <span id="doc-ref">REF: CB-0000</span>
                    <span id="doc-date">DATE: --</span>
                    <span class="status">STATUS: DRAFT</span>
                </div>
                <div id="result-body"></div>
            </div>
            <button class="copy-btn" id="copy-btn" type="button">Copy brief</button>
        </div>
    </div>

    <div class="gate-overlay" id="email-gate">
        <div class="gate-card">
            <button class="gate-close" id="gate-close" type="button" aria-label="Close">×</button>
            <div class="gate-seal">CB</div>
            <h2>Unlock the brief</h2>
            <p>Enter your work email to generate your first structured brief.</p>
            <input type="email" class="gate-input" id="gate-email" placeholder="you@agency.com">
            <div class="error-text" id="gate-error" style="margin-bottom: 16px;"></div>
            <button class="btn-primary" id="gate-submit" type="button">
                <span class="spinner"></span>
                <span class="btn-text">Unlock the Brief</span>
            </button>
        </div>
    </div>

    <script>
        const EMAIL_KEY = 'clientbrief_email';
        let pendingNotes = null;

        // --- Utility Functions ---
        function getSavedEmail() {
            try { return localStorage.getItem(EMAIL_KEY); } catch (e) { return null; }
        }

        function saveEmail(email) {
            try { localStorage.setItem(EMAIL_KEY, email); } catch (e) { /* ignore */ }
        }

        function isValidEmail(email) {
            return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
        }

        function setLoadingState(button, isLoading, loadingText, defaultText) {
            const btnText = button.querySelector('.btn-text');
            if (isLoading) {
                button.classList.add('loading');
                button.disabled = true;
                btnText.textContent = loadingText;
            } else {
                button.classList.remove('loading');
                button.disabled = false;
                btnText.textContent = defaultText;
            }
        }

        // --- Brief Rendering Logic ---
        function renderBrief(text) {
            const resultBody = document.getElementById('result-body');
            resultBody.innerHTML = '';

            // Strip markdown stars
            const cleanText = text.replace(/\*\*/g, '').replace(/\*/g, '');

            // Generate letterhead data
            const refNum = Math.floor(1000 + Math.random() * 9000);
            const dateStr = new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).toUpperCase();
            
            document.getElementById('doc-ref').textContent = `REF: CB-${refNum}`;
            document.getElementById('doc-date').textContent = `DATE: ${dateStr}`;

            // Split text and render
            const lines = cleanText.split('\n');
            lines.forEach(line => {
                const trimmed = line.trim();
                if (!trimmed) return;

                // Check if line is a header (starts with "1.", "2.", etc. or "SECTION")
                const isHeader = /^\d+\.\s/.test(trimmed) || /^SECTION/i.test(trimmed);
                
                const el = document.createElement(isHeader ? 'h3' : 'p');
                el.textContent = trimmed;
                resultBody.appendChild(el);
            });

            // Show the document
            document.getElementById('result-wrap').classList.add('visible');
            document.getElementById('result-wrap').scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        // --- API Call Logic ---
        async function draftBrief(notes, email) {
            const draftBtn = document.getElementById('draft-btn');
            const errorEl = document.getElementById('notes-error');
            
            setLoadingState(draftBtn, true, 'Drafting...', 'Draft the Brief');
            errorEl.classList.remove('visible');

            try {
                let url = '/generate-brief?notes=' + encodeURIComponent(notes);
                if (email) {
                    url += '&email=' + encodeURIComponent(email);
                }

                const response = await fetch(url);
                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || 'Something went wrong drafting your brief.');
                }

                renderBrief(data.plan || '');
            } catch (e) {
                errorEl.textContent = e.message || 'Something went wrong. Please try again.';
                errorEl.classList.add('visible');
            } finally {
                setLoadingState(draftBtn, false, '', 'Draft the Brief');
            }
        }

        // --- Event Listeners ---
        
        // Draft Button Click
        document.getElementById('draft-btn').addEventListener('click', function() {
            const notes = document.getElementById('notes-input').value.trim();
            const errorEl = document.getElementById('notes-error');

            if (!notes) {
                errorEl.textContent = 'Please paste some client notes first.';
                errorEl.classList.add('visible');
                return;
            }
            errorEl.classList.remove('visible');

            const savedEmail = getSavedEmail();
            if (savedEmail) {
                draftBrief(notes, savedEmail);
            } else {
                pendingNotes = notes;
                document.getElementById('email-gate').classList.add('visible');
            }
        });

        // Gate Submit Click
        document.getElementById('gate-submit').addEventListener('click', function() {
            const email = document.getElementById('gate-email').value.trim();
            const gateError = document.getElementById('gate-error');
            const submitBtn = this;

            if (!isValidEmail(email)) {
                gateError.textContent = "That doesn't look like a valid email address.";
                gateError.classList.add('visible');
                return;
            }
            gateError.classList.remove('visible');

            saveEmail(email);
            document.getElementById('email-gate').classList.remove('visible');
            
            if (pendingNotes) {
                // Note: We don't set loading state on the gate button here because 
                // the main draft button will handle the loading state.
                draftBrief(pendingNotes, email);
                pendingNotes = null;
            }
        });

        // Gate Close Click
        document.getElementById('gate-close').addEventListener('click', function() {
            document.getElementById('email-gate').classList.remove('visible');
            pendingNotes = null;
        });

        // Gate Enter Key
        document.getElementById('gate-email').addEventListener('keyup', function(e) {
            if (e.key === 'Enter') {
                document.getElementById('gate-submit').click();
            }
        });

        // Cmd/Ctrl + Enter in textarea
        document.getElementById('notes-input').addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                document.getElementById('draft-btn').click();
            }
        });

        // Copy Brief Click
        document.getElementById('copy-btn').addEventListener('click', async function() {
            const text = document.getElementById('result-body').innerText;
            const btn = this;
            
            try {
                await navigator.clipboard.writeText(text);
                const originalText = btn.textContent;
                btn.textContent = 'Copied!';
                setTimeout(() => {
                    btn.textContent = originalText;
                }, 2000);
            } catch (e) {
                alert('Could not copy automatically. Please select the text and copy manually.');
            }
        });
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)