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
    if not GROQ_API_KEY:
        return JSONResponse(status_code=500, content={"error": "GROQ_API_KEY not set in environment."})

    try:
        plan = call_groq(
            system_msg=(
                "You are a Senior Strategy Director at an elite, top-tier creative agency. Take the "
                "user's rough, messy notes from a client and transform them into a highly "
                "professional, comprehensive, and strategically brilliant Client Brief. "
                "Do not just summarize; elevate. Include these sections: "
                "1. Project Overview, 2. Business Goals & KPIs, 3. Target Audience & Insights, 4. Scope of "
                "Work, 5. Deliverables, 6. Strategic Assumptions (explain what you logically inferred to fill in the client's blanks), "
                "7. Suggested Timeline. Make logical, brilliant assumptions to fill in any gaps. Use "
                "formal, premium corporate language that exudes confidence. "
                "CRITICAL FORMATTING: Do NOT use any Markdown formatting (no **, no *, no #). Use plain text only. Use ALL-CAPS for section headers."
            ),
            user_msg=(
                f"Turn the following rough client notes into a structured, strategic client brief:\n"
                f"Client notes: {notes}\n"
                f"List each section as 1., 2., 3., 4., 5., 6., 7."
            ),
            max_tokens=800,
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
    <title>Brief Studio — From Chaos to Strategy in 60 Seconds</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="Don't just format messy client notes. Turn them into a strategically brilliant, client-ready brief with KPIs, assumptions, and timelines.">
    <meta name="theme-color" content="#F2F2EF">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #F2F2EF; /* Off-white Canvas */
            --surface: #FFFFFF;
            --ink: #0A0A0A; /* Pitch Black */
            --muted: #666666;
            --border: #0A0A0A;
            --accent: #CCFF00; /* Acid Lime */
            --accent-hover: #b3e600;
            --error: #FF3B30;
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            background: var(--bg);
            color: var(--ink);
            font-family: 'Space Grotesk', system-ui, sans-serif;
            -webkit-font-smoothing: antialiased;
            overflow-x: hidden;
        }

        .wrap { max-width: 1400px; margin: 0 auto; padding: 0 32px; position: relative; }
        section[id] { scroll-margin-top: 84px; }
        a { color: inherit; text-decoration: none; }

        /* ---------- NAV ---------- */
        .topnav {
            position: sticky;
            top: 0;
            z-index: 30;
            background: rgba(242, 242, 239, 0.85);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--ink);
        }
        .topnav .wrap { display: flex; align-items: center; justify-content: space-between; height: 72px; }
        .wordmark {
            font-family: 'Instrument Serif', serif;
            font-size: 1.6rem;
            font-weight: 400;
            letter-spacing: -0.02em;
        }
        .wordmark span { font-style: italic; }
        .wordmark::before {
            content: '◆';
            color: var(--ink);
            margin-right: 8px;
            font-size: 0.8rem;
            vertical-align: middle;
        }
        
        .nav-links { display: flex; gap: 36px; list-style: none; }
        .nav-links a { color: var(--muted); font-size: 0.9rem; font-weight: 500; transition: color 0.2s; }
        .nav-links a:hover { color: var(--ink); }
        
        .btn-nav {
            background: var(--ink);
            color: var(--bg);
            padding: 10px 20px;
            font-size: 0.85rem;
            font-weight: 600;
            border: 1px solid var(--ink);
            transition: all 0.2s;
        }
        .btn-nav:hover { background: transparent; color: var(--ink); }
        
        @media (max-width: 760px) { .nav-links { display: none; } }

        /* ---------- HERO ---------- */
        .hero { padding: 80px 0 40px; border-bottom: 1px solid var(--ink); }
        .hero-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 60px;
            align-items: flex-end;
        }
        .hero-left h1 {
            font-family: 'Instrument Serif', serif;
            font-size: clamp(3rem, 8vw, 7rem);
            line-height: 0.9;
            font-weight: 400;
            letter-spacing: -0.03em;
            margin-bottom: 24px;
        }
        .hero-left h1 em { font-style: italic; }
        .hero-left p {
            font-size: 1.1rem;
            color: var(--muted);
            max-width: 480px;
            line-height: 1.5;
            margin-bottom: 32px;
        }
        .btn-cta {
            background: var(--accent);
            color: var(--ink);
            border: 1px solid var(--ink);
            padding: 16px 32px;
            font-size: 1rem;
            font-weight: 700;
            display: inline-block;
            transition: all 0.2s;
            box-shadow: 4px 4px 0px 0px var(--ink);
        }
        .btn-cta:hover { transform: translate(-2px, -2px); box-shadow: 6px 6px 0px 0px var(--ink); }
        
        .hero-right {
            border-left: 1px solid var(--ink);
            padding-left: 40px;
            padding-bottom: 20px;
        }
        .stat-block { margin-bottom: 32px; }
        .stat-block:last-child { margin-bottom: 0; }
        .stat-num {
            font-family: 'Instrument Serif', serif;
            font-size: 3.5rem;
            line-height: 1;
            font-weight: 400;
        }
        .stat-label {
            font-size: 0.85rem;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 8px;
        }

        /* ---------- BENTO GRID (The "Why") ---------- */
        .bento-section { padding: 80px 0; border-bottom: 1px solid var(--ink); }
        .bento-header { margin-bottom: 40px; display: flex; justify-content: space-between; align-items: flex-end; }
        .bento-header h2 {
            font-family: 'Instrument Serif', serif;
            font-size: clamp(2rem, 5vw, 3.5rem);
            line-height: 1;
            font-weight: 400;
        }
        .bento-header h2 em { font-style: italic; color: var(--muted); }
        
        .bento-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            grid-template-rows: 220px 220px;
            gap: 16px;
        }
        .bento-card {
            border: 1px solid var(--ink);
            padding: 24px;
            background: var(--surface);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: background 0.3s;
        }
        .bento-card:hover { background: var(--accent); }
        .bento-card.dark { background: var(--ink); color: var(--bg); }
        .bento-card.dark:hover { background: var(--accent); color: var(--ink); }
        
        .bento-card.large { grid-column: span 2; grid-row: span 2; }
        .bento-card.wide { grid-column: span 2; }
        
        .bento-tag {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            font-weight: 600;
            opacity: 0.6;
        }
        .bento-title {
            font-family: 'Instrument Serif', serif;
            font-size: 1.8rem;
            line-height: 1.1;
            margin-top: 12px;
        }
        .bento-card.large .bento-title { font-size: 3rem; }
        .bento-desc { font-size: 0.9rem; line-height: 1.5; margin-top: 12px; opacity: 0.8; }

        @media (max-width: 880px) {
            .hero-grid { grid-template-columns: 1fr; }
            .hero-right { border-left: none; border-top: 1px solid var(--ink); padding-left: 0; padding-top: 32px; margin-top: 32px; display: flex; gap: 40px; }
            .bento-grid { grid-template-columns: 1fr; grid-template-rows: auto; }
            .bento-card.large, .bento-card.wide { grid-column: span 1; grid-row: span 1; }
        }

        /* ---------- WORKSPACE (The Tool) ---------- */
        .workspace-section { padding: 80px 0; background: var(--ink); color: var(--bg); }
        .workspace-header { text-align: center; margin-bottom: 48px; }
        .workspace-header h2 {
            font-family: 'Instrument Serif', serif;
            font-size: clamp(2.5rem, 6vw, 4.5rem);
            line-height: 1;
            font-weight: 400;
        }
        .workspace-header h2 em { font-style: italic; color: var(--accent); }
        
        .workspace-grid {
            display: grid;
            grid-template-columns: 1fr 1.2fr;
            gap: 0;
            border: 1px solid var(--bg);
            background: var(--bg);
            min-height: 600px;
        }
        
        /* Input Panel */
        .ws-input-panel {
            background: var(--bg);
            color: var(--ink);
            padding: 32px;
            display: flex;
            flex-direction: column;
        }
        .ws-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            font-weight: 700;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .ws-label::before { content: ''; width: 8px; height: 8px; background: var(--ink); border-radius: 50%; }
        
        textarea#notes-input {
            flex-grow: 1;
            width: 100%;
            resize: none;
            border: none;
            background: transparent;
            color: var(--ink);
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.2rem;
            line-height: 1.5;
            outline: none;
        }
        textarea#notes-input::placeholder { color: #999; }
        
        .ws-error { color: var(--error); font-size: 0.85rem; margin-top: 12px; height: 16px; }
        
        .ws-actions { margin-top: 24px; border-top: 1px solid var(--ink); padding-top: 24px; }
        .btn-generate {
            background: var(--ink);
            color: var(--bg);
            border: 1px solid var(--ink);
            padding: 16px 24px;
            font-size: 0.95rem;
            font-weight: 700;
            width: 100%;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
        }
        .btn-generate:hover { background: var(--accent); color: var(--ink); }
        .btn-generate:disabled { opacity: 0.5; cursor: wait; }

        /* Output Panel */
        .ws-output-panel {
            background: var(--surface);
            color: var(--ink);
            padding: 0;
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        .ws-output-header {
            display: flex;
            justify-content: space-between;
            padding: 16px 32px;
            border-bottom: 1px solid var(--border);
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            font-weight: 700;
            background: var(--bg);
        }
        .ws-doc-area {
            padding: 32px;
            flex-grow: 1;
            overflow-y: auto;
            max-height: 650px;
        }
        
        .placeholder-state {
            height: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            color: #999;
        }
        .placeholder-state svg { width: 48px; height: 48px; margin-bottom: 16px; opacity: 0.3; }
        
        .doc-content { display: none; }
        .doc-content.visible { display: block; animation: fadeIn 0.5s ease; }
        
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

        .doc-content h3 { font-family: 'Instrument Serif', serif; font-size: 1.4rem; margin: 24px 0 8px; }
        .doc-content h3:first-child { margin-top: 0; }
        .doc-content p { font-size: 0.95rem; line-height: 1.6; color: #444; margin-bottom: 8px; }
        
        .ws-copy-btn {
            background: transparent;
            border: 1px solid var(--ink);
            color: var(--ink);
            padding: 8px 16px;
            font-size: 0.75rem;
            font-weight: 600;
            cursor: pointer;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            transition: all 0.2s;
        }
        .ws-copy-btn:hover { background: var(--ink); color: var(--bg); }

        @media (max-width: 880px) {
            .workspace-grid { grid-template-columns: 1fr; min-height: auto; }
            .ws-output-panel { border-top: 1px solid var(--ink); min-height: 400px; }
        }

        /* ---------- FAQ & FOOTER ---------- */
        .faq-section { padding: 80px 0; border-bottom: 1px solid var(--ink); }
        .faq-list { max-width: 800px; margin: 0 auto; }
        .faq-item { border-bottom: 1px solid var(--ink); padding: 24px 0; }
        .faq-item summary {
            cursor: pointer; list-style: none; display: flex; align-items: center; justify-content: space-between;
            font-family: 'Instrument Serif', serif; font-size: 1.8rem; font-weight: 400;
        }
        .faq-item summary::-webkit-details-marker { display: none; }
        .faq-item summary::after { content: '+'; font-size: 2rem; color: var(--muted); }
        .faq-item[open] summary::after { content: '−'; }
        .faq-item .faq-answer { color: var(--muted); font-size: 1rem; line-height: 1.6; margin: 16px 0 0; max-width: 700px; }

        .site-footer { padding: 60px 0; text-align: center; }
        .site-footer p { font-size: 0.85rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.1em; }

        /* ---------- EMAIL GATE ---------- */
        .gate-overlay {
            display: none; position: fixed; inset: 0; background: rgba(10, 10, 10, 0.8);
            backdrop-filter: blur(8px); align-items: center; justify-content: center; padding: 20px; z-index: 100;
        }
        .gate-overlay.visible { display: flex; }
        .gate-card {
            background: var(--bg); border: 1px solid var(--ink); padding: 48px; max-width: 440px; width: 100%; text-align: center; position: relative;
            box-shadow: 8px 8px 0px 0px var(--accent);
        }
        .gate-card h2 { font-family: 'Instrument Serif', serif; font-size: 2.5rem; line-height: 1; margin: 0 0 12px; }
        .gate-card p { color: var(--muted); font-size: 1rem; margin: 0 0 24px; }
        input#gate-email {
            width: 100%; background: var(--surface); border: 1px solid var(--ink); color: var(--ink);
            font-family: 'Space Grotesk', sans-serif; font-size: 1rem; padding: 14px 16px; outline: none; margin-bottom: 12px;
        }
        .gate-close {
            position: absolute; top: 16px; right: 16px; background: none; border: none; color: var(--ink); font-size: 1.5rem; cursor: pointer;
        }
        .btn-gate {
            background: var(--ink); color: var(--bg); border: 1px solid var(--ink); padding: 16px; width: 100%; font-size: 1rem; font-weight: 700; cursor: pointer;
        }
        .btn-gate:hover { background: var(--accent); color: var(--ink); }
    </style>
</head>
<body>
    <nav class="topnav">
        <div class="wrap">
            <div class="wordmark">Brief<span>Studio</span></div>
            <ul class="nav-links">
                <li><a href="#features">Features</a></li>
                <li><a href="#workspace">Workspace</a></li>
                <li><a href="#faq">FAQ</a></li>
            </ul>
            <a href="#workspace" class="btn-nav">Launch Studio</a>
        </div>
    </nav>

    <header class="hero">
        <div class="wrap hero-grid">
            <div class="hero-left">
                <h1>Stop formatting text. Start <em>directing strategy.</em></h1>
                <p>Paste the rambling client email. Get back a comprehensive, strategically sound brief complete with KPIs, timelines, and inferred insights in 60 seconds.</p>
                <a href="#workspace" class="btn-cta">Open the Workspace →</a>
            </div>
            <div class="hero-right">
                <div class="stat-block">
                    <div class="stat-num">7</div>
                    <div class="stat-label">Strategic sections generated</div>
                </div>
                <div class="stat-block">
                    <div class="stat-num">60s</div>
                    <div class="stat-label">From chaos to client-ready</div>
                </div>
                <div class="stat-block">
                    <div class="stat-num">100%</div>
                    <div class="stat-label">Senior Strategist tone</div>
                </div>
            </div>
        </div>
    </header>

    <section class="bento-section" id="features">
        <div class="wrap">
            <div class="bento-header">
                <h2>Not just a formatter. <em>A strategist.</em></h2>
            </div>
            <div class="bento-grid">
                <div class="bento-card large dark">
                    <div class="bento-tag">THE CORE DIFFERENTIATOR</div>
                    <div>
                        <div class="bento-title">Strategic Assumptions Engine</div>
                        <div class="bento-desc">Clients never give you everything. Our AI explicitly lists the strategic gaps it filled, so you know exactly what to validate before the kickoff. No more blind spots.</div>
                    </div>
                </div>
                <div class="bento-card">
                    <div class="bento-tag">METRICS</div>
                    <div class="bento-title">Projected KPIs</div>
                </div>
                <div class="bento-card">
                    <div class="bento-tag">PLANNING</div>
                    <div class="bento-title">Suggested Timelines</div>
                </div>
                <div class="bento-card wide">
                    <div class="bento-tag">TONE OF VOICE</div>
                    <div>
                        <div class="bento-title">Elite Agency Standard</div>
                        <div class="bento-desc">Reads like it was written by a Senior Account Director. Confident, formal, and completely free of chatbot clichés.</div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <section class="workspace-section" id="workspace">
        <div class="wrap">
            <div class="workspace-header">
                <h2>The <em>Studio.</em></h2>
            </div>
            <div class="workspace-grid">
                <!-- Left Side: Input -->
                <div class="ws-input-panel">
                    <div class="ws-label">Input: Client Ramble</div>
                    <textarea id="notes-input" placeholder="e.g. hey can u whip up smth for the launch, need social + a landing page, budget is tight, oh and my sister said purple is unlucky so no purple..."></textarea>
                    <div class="ws-error" id="notes-error"></div>
                    <div class="ws-actions">
                        <button class="btn-generate" id="draft-btn" type="button">
                            Generate Strategic Brief
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                        </button>
                    </div>
                </div>
                
                <!-- Right Side: Output -->
                <div class="ws-output-panel">
                    <div class="ws-output-header">
                        <span>Output: JOB NO. <span id="doc-ref">0000</span></span>
                        <button class="ws-copy-btn" id="copy-btn" type="button" style="display: none;">Copy</button>
                    </div>
                    <div class="ws-doc-area">
                        <div class="placeholder-state" id="placeholder-state">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/></svg>
                            <p>Your structured, strategically sound brief will appear here.</p>
                        </div>
                        <div class="doc-content" id="result-body"></div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <section class="faq-section" id="faq">
        <div class="wrap">
            <div class="faq-list">
                <details class="faq-item">
                    <summary>Does this replace a strategist?</summary>
                    <p class="faq-answer">No — think of it as a 10x multiplier. It gets you from a blank page to a 90% finished, strategically structured brief in under a minute. You still bring the final human polish.</p>
                </details>
                <details class="faq-item">
                    <summary>How does it handle chaotic notes?</summary>
                    <p class="faq-answer">That's its specialty. The AI parses the intent behind the mess, structures it logically, and includes a "Strategic Assumptions" section so you can see exactly what it inferred.</p>
                </details>
                <details class="faq-item">
                    <summary>Is my client's information stored?</summary>
                    <p class="faq-answer">Yes, securely. Each brief is saved along with the notes that generated it so you can reference it later. Nothing is ever sent directly to your client without your action.</p>
                </details>
            </div>
        </div>
    </section>

    <footer class="site-footer">
        <div class="wrap">
            <p>© 2026 Brief Studio. Built for agencies who value billable hours over busywork.</p>
        </div>
    </footer>

    <div class="gate-overlay" id="email-gate">
        <div class="gate-card">
            <button class="gate-close" id="gate-close" type="button" aria-label="Close">×</button>
            <h2>Unlock the Studio</h2>
            <p>Drop your email to generate your first strategic brief. No spam—just smarter workflows.</p>
            <input type="email" id="gate-email" placeholder="you@agency.com" aria-label="Email address">
            <div class="ws-error" id="gate-error" style="text-align:left;"></div>
            <button class="btn-gate" id="gate-submit" type="button">Get My Brief</button>
        </div>
    </div>

    <script>
        const EMAIL_KEY = 'briefstudio_email';
        let pendingNotes = null;

        function getSavedEmail() { try { return localStorage.getItem(EMAIL_KEY); } catch (e) { return null; } }
        function saveEmail(email) { try { localStorage.setItem(EMAIL_KEY, email); } catch (e) {} }
        function isValidEmail(email) { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email); }
        function openGate() { document.getElementById('email-gate').classList.add('visible'); }
        function closeGate() { document.getElementById('email-gate').classList.remove('visible'); }

        function renderBrief(text) {
            const resultBody = document.getElementById('result-body');
            const placeholder = document.getElementById('placeholder-state');
            const copyBtn = document.getElementById('copy-btn');
            
            resultBody.innerHTML = '';
            text.split('\n').forEach(function (line) {
                const trimmed = line.trim();
                if (!trimmed) return;
                const el = document.createElement(/^\d+\.\s/.test(trimmed) ? 'h3' : 'p');
                el.textContent = trimmed;
                resultBody.appendChild(el);
            });
            
            placeholder.style.display = 'none';
            resultBody.classList.add('visible');
            copyBtn.style.display = 'block';
            
            document.getElementById('doc-ref').textContent = Math.floor(1000 + Math.random() * 9000);
        }

        async function draftBrief(notes, email) {
            const btn = document.getElementById('draft-btn');
            const placeholder = document.getElementById('placeholder-state');
            const resultBody = document.getElementById('result-body');
            const copyBtn = document.getElementById('copy-btn');
            
            btn.disabled = true;
            btn.innerHTML = 'Strategizing... <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10" stroke-dasharray="40" stroke-dashoffset="20"><animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="1s" repeatCount="indefinite"/></circle></svg>';
            
            resultBody.classList.remove('visible');
            copyBtn.style.display = 'none';
            placeholder.style.display = 'flex';
            placeholder.querySelector('p').textContent = 'Analyzing notes and formulating strategy...';

            try {
                let url = '/generate-brief?notes=' + encodeURIComponent(notes);
                if (email) url += '&email=' + encodeURIComponent(email);
                const response = await fetch(url);
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'Something went wrong.');
                
                renderBrief(data.plan || '');
            } catch (e) {
                placeholder.style.display = 'flex';
                placeholder.querySelector('p').textContent = e.message || 'Error generating brief. Try again.';
            } finally {
                btn.disabled = false;
                btn.innerHTML = 'Generate Strategic Brief <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>';
            }
        }

        document.getElementById('draft-btn').addEventListener('click', function () {
            const notes = document.getElementById('notes-input').value.trim();
            const errorEl = document.getElementById('notes-error');
            if (!notes) {
                errorEl.textContent = 'Paste some client notes first.';
                return;
            }
            errorEl.textContent = '';

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
                gateError.textContent = "That doesn't look like a valid email.";
                return;
            }
            gateError.textContent = '';
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
        
        // Cmd/Ctrl + Enter shortcut
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
                setTimeout(function () { btn.textContent = original; }, 2000);
            } catch (e) {
                alert('Could not copy automatically.');
            }
        });
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)