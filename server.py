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

# Backend blocklist for free and disposable email providers
BLOCKED_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "live.com", 
    "aol.com", "icloud.com", "protonmail.com", "zoho.com", "msn.com",
    "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com",
    "yopmail.com", "trashmail.com", "getnada.com", "googlemail.com", "gmx.com"
}

def validate_work_email(email: str) -> tuple[bool, str]:
    """Validates format and blocks free providers."""
    if not email:
        return False, "Email is required."
    
    candidate = email.strip().lower()
    if not _EMAIL_RE.fullmatch(candidate):
        return False, "Please enter a valid email format."
    
    domain = candidate.split("@")[1]
    
    if domain in BLOCKED_DOMAINS:
        return False, "Please use your work email. Free providers (Gmail, Yahoo, etc.) are not accepted."
    
    return True, "Valid"


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
    email: str = Query(..., description="Work email captured by the frontend's email gate"),
):
    """Turns messy client notes into a structured, professional client brief."""
    if not GROQ_API_KEY:
        return JSONResponse(status_code=500, content={"error": "GROQ_API_KEY not set in environment."})

    # 1. Strict Email Validation
    is_valid, error_msg = validate_work_email(email)
    if not is_valid:
        return JSONResponse(status_code=400, content={"error": error_msg})

    try:
        plan = call_groq(
            system_msg=(
                "Write a professional client project brief from rough intake notes, in the tone "
                "of an experienced agency account lead. Include: "
                "1. Project Overview, 2. Business Goals, 3. Target Audience, 4. Scope of "
                "Work, 5. Deliverables, 6. Assumptions & Open Questions, 7. Suggested Timeline. "
                "Fill gaps with sensible assumptions and list them under section 6. "
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
        insert_data = {"notes": notes, "brief": plan, "email": email.strip().lower()}
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
    <title>BriefStudio — Project briefs for marketing &amp; creative agencies</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="Turn messy client intake into a scoped, send-ready project brief. Built for account teams at creative, performance, and dev agencies.">
    <meta name="theme-color" content="#0F1419">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0F1419;
            --bg-soft: #161D26;
            --surface: #F4F0E8;
            --surface-2: #FFFCF7;
            --ink: #0F1419;
            --ink-on-dark: #F4F0E8;
            --muted: #6B7280;
            --muted-on-dark: #9CA3AF;
            --line: rgba(244, 240, 232, 0.12);
            --line-light: #D4CEC4;
            --accent: #E85D4C;
            --accent-2: #3D8B7A;
            --accent-glow: rgba(232, 93, 76, 0.35);
            --error: #E85D4C;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html { scroll-behavior: smooth; }
        body {
            background: var(--bg);
            color: var(--ink-on-dark);
            font-family: 'DM Sans', system-ui, sans-serif;
            font-size: 16px;
            line-height: 1.55;
            -webkit-font-smoothing: antialiased;
        }
        body::before {
            content: '';
            position: fixed;
            inset: 0;
            background:
                radial-gradient(ellipse 80% 50% at 20% -10%, rgba(232, 93, 76, 0.15), transparent 50%),
                radial-gradient(ellipse 60% 40% at 90% 10%, rgba(61, 139, 122, 0.12), transparent 45%);
            pointer-events: none;
            z-index: 0;
        }
        .wrap { max-width: 1140px; margin: 0 auto; padding: 0 24px; position: relative; z-index: 1; }
        a { color: inherit; text-decoration: none; }
        section[id] { scroll-margin-top: 80px; }

        .site-bar {
            position: sticky;
            top: 0;
            z-index: 40;
            border-bottom: 1px solid var(--line);
            background: rgba(15, 20, 25, 0.88);
            backdrop-filter: blur(14px);
        }
        .site-bar .wrap {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
            height: 68px;
        }
        .logo {
            font-family: 'Instrument Serif', Georgia, serif;
            font-size: 1.35rem;
            letter-spacing: -0.02em;
        }
        .logo span { color: var(--accent); font-style: italic; }
        .site-bar nav { display: flex; gap: 28px; font-size: 0.9rem; color: var(--muted-on-dark); }
        .site-bar nav a:hover { color: var(--ink-on-dark); }
        .nav-cta {
            background: var(--surface);
            color: var(--ink);
            font-weight: 600;
            font-size: 0.88rem;
            padding: 10px 18px;
            border-radius: 999px;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .nav-cta:hover {
            transform: translateY(-1px);
            box-shadow: 0 8px 24px var(--accent-glow);
        }

        .hero { padding: 48px 0 72px; }
        .hero-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 48px;
            align-items: center;
        }
        .eyebrow {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: var(--accent);
            margin-bottom: 16px;
        }
        .eyebrow::before {
            content: '';
            width: 24px;
            height: 1px;
            background: var(--accent);
        }
        .hero h1 {
            font-family: 'Instrument Serif', Georgia, serif;
            font-size: clamp(2.4rem, 5vw, 3.5rem);
            line-height: 1.05;
            font-weight: 400;
            margin-bottom: 20px;
            letter-spacing: -0.02em;
        }
        .hero h1 em { font-style: italic; color: var(--surface); }
        .hero .lede {
            color: var(--muted-on-dark);
            font-size: 1.08rem;
            max-width: 28rem;
            margin-bottom: 28px;
        }
        .hero-actions { display: flex; flex-wrap: wrap; gap: 14px; align-items: center; margin-bottom: 24px; }
        .btn-primary {
            background: var(--accent);
            color: #fff;
            font-weight: 700;
            font-size: 0.95rem;
            padding: 14px 26px;
            border-radius: 999px;
            border: none;
            cursor: pointer;
            font-family: inherit;
            transition: filter 0.2s, transform 0.2s;
        }
        .btn-primary:hover { filter: brightness(1.08); transform: translateY(-1px); }
        .btn-ghost {
            color: var(--muted-on-dark);
            font-size: 0.92rem;
            border-bottom: 1px solid var(--muted-on-dark);
            padding-bottom: 2px;
        }
        .btn-ghost:hover { color: var(--surface); border-color: var(--surface); }
        .trust-row {
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            font-size: 0.82rem;
            color: var(--muted-on-dark);
        }
        .trust-row span { display: flex; align-items: center; gap: 6px; }
        .trust-row span::before {
            content: '';
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: var(--accent-2);
        }

        .preview-card {
            background: var(--surface-2);
            color: var(--ink);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(255,255,255,0.06);
            transform: rotate(1deg);
            transition: transform 0.4s ease;
        }
        .preview-card:hover { transform: rotate(0deg) translateY(-4px); }
        .preview-bar {
            background: var(--ink);
            color: var(--surface);
            font-size: 0.72rem;
            padding: 10px 16px;
            display: flex;
            justify-content: space-between;
            letter-spacing: 0.04em;
        }
        .preview-body { padding: 22px 20px 24px; }
        .preview-cols {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-bottom: 18px;
        }
        .preview-stat {
            background: var(--surface);
            border: 1px solid var(--line-light);
            border-radius: 8px;
            padding: 12px;
        }
        .preview-stat label {
            font-size: 0.65rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--muted);
            display: block;
            margin-bottom: 4px;
        }
        .preview-stat strong { font-size: 0.95rem; }
        .preview-snippet {
            font-family: 'Instrument Serif', Georgia, serif;
            font-size: 1.05rem;
            line-height: 1.45;
            color: #3d3d3d;
        }
        .preview-snippet cite {
            display: block;
            font-family: 'DM Sans', sans-serif;
            font-size: 0.72rem;
            font-style: normal;
            color: var(--muted);
            margin-top: 10px;
        }

        .section-light {
            background: var(--surface);
            color: var(--ink);
            padding: 72px 0;
            position: relative;
            z-index: 1;
        }
        .section-head {
            text-align: center;
            max-width: 560px;
            margin: 0 auto 48px;
        }
        .section-head h2 {
            font-family: 'Instrument Serif', Georgia, serif;
            font-size: clamp(1.85rem, 4vw, 2.6rem);
            font-weight: 400;
            margin-bottom: 12px;
        }
        .section-head p { color: var(--muted); font-size: 1.02rem; }

        .steps {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 24px;
        }
        .step {
            border: 1px solid var(--line-light);
            border-radius: 12px;
            padding: 28px 22px;
            background: var(--surface-2);
        }
        .step-num {
            font-family: 'Instrument Serif', serif;
            font-size: 2rem;
            color: var(--accent);
            line-height: 1;
            margin-bottom: 14px;
        }
        .step h3 { font-size: 1.05rem; margin-bottom: 8px; font-weight: 600; }
        .step p { color: var(--muted); font-size: 0.92rem; }

        .benefits {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
        }
        .benefit {
            padding: 28px;
            border-radius: 12px;
            background: var(--bg-soft);
            color: var(--ink-on-dark);
            border: 1px solid var(--line);
        }
        .benefit h3 {
            font-family: 'Instrument Serif', serif;
            font-size: 1.35rem;
            font-weight: 400;
            margin-bottom: 8px;
        }
        .benefit p { color: var(--muted-on-dark); font-size: 0.92rem; }

        .workspace {
            padding: 72px 0 80px;
            position: relative;
            z-index: 1;
        }
        .workspace .section-head { margin-bottom: 32px; }
        .workspace .section-head h2 { color: var(--surface); }
        .workspace .section-head p { color: var(--muted-on-dark); }
        .tool-shell {
            background: var(--surface);
            color: var(--ink);
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 32px 80px rgba(0, 0, 0, 0.35);
        }
        .tool-tabs {
            display: flex;
            border-bottom: 1px solid var(--line-light);
            background: var(--surface-2);
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }
        .tool-tabs span {
            padding: 14px 20px;
            color: var(--muted);
        }
        .tool-tabs span.active {
            color: var(--ink);
            background: var(--surface);
            box-shadow: inset 0 -2px 0 var(--accent);
        }
        .desk {
            display: grid;
            grid-template-columns: 1fr 1fr;
            min-height: 480px;
        }
        .desk-in, .desk-out {
            padding: 24px;
            display: flex;
            flex-direction: column;
        }
        .desk-out {
            background: var(--surface-2);
            border-left: 1px solid var(--line-light);
        }
        .field-label {
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--muted);
            margin-bottom: 10px;
        }
        .input-tools {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 10px;
        }
        .chip {
            background: var(--surface-2);
            border: 1px solid var(--line-light);
            font-size: 0.78rem;
            padding: 6px 12px;
            border-radius: 999px;
            cursor: pointer;
            font-family: inherit;
            color: var(--muted);
        }
        .chip:hover { border-color: var(--accent); color: var(--ink); }
        textarea#notes-input {
            flex: 1;
            min-height: 240px;
            width: 100%;
            border: 1px solid var(--line-light);
            border-radius: 10px;
            background: #fff;
            padding: 16px;
            font-family: inherit;
            font-size: 0.98rem;
            line-height: 1.55;
            color: var(--ink);
            resize: vertical;
            outline: none;
        }
        textarea#notes-input:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 3px var(--accent-glow);
        }
        .hint { font-size: 0.78rem; color: var(--muted); margin-top: 8px; }
        .field-error { color: var(--error); font-size: 0.85rem; min-height: 1.2em; margin-top: 8px; }
        .btn-draft {
            margin-top: 14px;
            width: 100%;
            background: var(--ink);
            color: var(--surface);
            border: none;
            padding: 15px 18px;
            font-family: inherit;
            font-size: 0.95rem;
            font-weight: 700;
            cursor: pointer;
            border-radius: 10px;
        }
        .btn-draft:hover { background: var(--accent); }
        .btn-draft:disabled { opacity: 0.6; cursor: wait; }

        .out-meta {
            display: flex;
            justify-content: space-between;
            gap: 8px;
            font-size: 0.72rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: var(--muted);
            margin-bottom: 16px;
        }
        .status-pill {
            background: var(--accent-2);
            color: #fff;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.65rem;
        }
        .out-placeholder {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            color: var(--muted);
            font-size: 0.92rem;
            padding: 32px 16px;
            border: 1px dashed var(--line-light);
            border-radius: 10px;
        }
        .out-placeholder svg { opacity: 0.35; margin-bottom: 12px; }
        .out-placeholder p { margin: 0; max-width: 220px; }
        #result-body { display: none; flex: 1; overflow-y: auto; max-height: 340px; }
        #result-body.visible { display: block; }
        #result-body h3 {
            font-family: 'Instrument Serif', serif;
            font-size: 1.08rem;
            margin: 16px 0 6px;
        }
        #result-body h3:first-child { margin-top: 0; }
        #result-body p { font-size: 0.9rem; color: var(--muted); margin-bottom: 6px; }
        .btn-copy {
            margin-top: 14px;
            align-self: flex-start;
            background: transparent;
            border: 1px solid var(--ink);
            padding: 10px 18px;
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            cursor: pointer;
            border-radius: 999px;
            display: none;
        }
        .btn-copy.visible { display: inline-block; }
        .btn-copy:hover { background: var(--ink); color: var(--surface); }

        .faq { padding: 64px 0; background: var(--surface); color: var(--ink); }
        .faq-list { max-width: 640px; margin: 0 auto; }
        details {
            border-bottom: 1px solid var(--line-light);
            padding: 18px 0;
        }
        summary {
            cursor: pointer;
            font-weight: 600;
            list-style: none;
            font-size: 1rem;
        }
        summary::-webkit-details-marker { display: none; }
        details p { color: var(--muted); font-size: 0.92rem; margin-top: 10px; line-height: 1.6; }

        .cta-band {
            padding: 56px 0;
            text-align: center;
            background: var(--bg-soft);
            border-top: 1px solid var(--line);
        }
        .cta-band h2 {
            font-family: 'Instrument Serif', serif;
            font-size: clamp(1.8rem, 4vw, 2.4rem);
            font-weight: 400;
            margin-bottom: 20px;
        }

        footer {
            padding: 32px 0 48px;
            font-size: 0.82rem;
            color: var(--muted-on-dark);
            text-align: center;
            border-top: 1px solid var(--line);
        }

        .gate-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(15, 20, 25, 0.72);
            backdrop-filter: blur(6px);
            align-items: center;
            justify-content: center;
            padding: 20px;
            z-index: 100;
        }
        .gate-overlay.visible { display: flex; }
        .gate-card {
            background: var(--surface);
            color: var(--ink);
            border-radius: 14px;
            max-width: 400px;
            width: 100%;
            padding: 32px 28px;
            position: relative;
            box-shadow: 0 24px 60px rgba(0, 0, 0, 0.4);
        }
        .gate-card h2 {
            font-family: 'Instrument Serif', serif;
            font-size: 1.6rem;
            font-weight: 400;
            margin-bottom: 8px;
        }
        .gate-card p { color: var(--muted); font-size: 0.92rem; margin-bottom: 16px; }
        input#gate-email {
            width: 100%;
            border: 1px solid var(--line-light);
            border-radius: 8px;
            padding: 12px 14px;
            font: inherit;
            margin-bottom: 8px;
        }
        input#gate-email:focus { outline: 2px solid var(--accent-glow); border-color: var(--accent); }
        input#gate-email.invalid { border-color: var(--error); }
        .gate-close {
            position: absolute;
            top: 12px;
            right: 14px;
            border: none;
            background: none;
            font-size: 1.4rem;
            cursor: pointer;
            color: var(--muted);
        }
        .btn-gate {
            width: 100%;
            margin-top: 8px;
            background: var(--accent);
            color: #fff;
            border: none;
            padding: 13px;
            font: inherit;
            font-weight: 700;
            cursor: pointer;
            border-radius: 999px;
        }

        @media (max-width: 900px) {
            .hero-grid, .desk, .steps, .benefits, .preview-cols { grid-template-columns: 1fr; }
            .desk-out { border-left: none; border-top: 1px solid var(--line-light); }
            .site-bar nav { display: none; }
            .preview-card { transform: none; }
        }
    </style>
</head>
<body>
    <header class="site-bar">
        <div class="wrap">
            <div class="logo">Client<span>Brief</span> AI</div>
            <nav>
                <a href="#how">How it works</a>
                <a href="#why">Benefits</a>
                <a href="#faq">FAQ</a>
            </nav>
            <a class="nav-cta" href="#tool">Try it free</a>
        </div>
    </header>

    <section class="hero">
        <div class="wrap hero-grid">
            <div>
                <p class="eyebrow">For marketing &amp; creative agencies</p>
                <h1>Project briefs from messy client intake—in <em>about a minute.</em></h1>
                <p class="lede">Paste the kickoff email, Slack thread, or call notes. Get a structured brief with scope, deliverables, open questions, and a timeline you can share internally or polish for the client.</p>
                <div class="hero-actions">
                    <a class="btn-primary" href="#tool">Create a brief</a>
                    <a class="btn-ghost" href="#how">See how it works</a>
                </div>
                <div class="trust-row">
                    <span>No account to start</span>
                    <span>Copy &amp; paste anywhere</span>
                    <span>You edit before anything goes out</span>
                </div>
            </div>
            <div class="preview-card" aria-hidden="true">
                <div class="preview-bar">
                    <span>clientbrief / brief / northwind-q4</span>
                    <span>DRAFT</span>
                </div>
                <div class="preview-body">
                    <div class="preview-cols">
                        <div class="preview-stat">
                            <label>Client</label>
                            <strong>Northwind Studio</strong>
                        </div>
                        <div class="preview-stat">
                            <label>Timeline</label>
                            <strong>6 weeks · phased</strong>
                        </div>
                    </div>
                    <p class="preview-snippet">“Scope covers paid social and a launch landing page. Budget still TBD—flagged for follow-up. Display excluded per client note on brand colors…”</p>
                    <cite>Excerpt · Project overview &amp; scope</cite>
                </div>
            </div>
        </div>
    </section>

    <section class="section-light" id="how">
        <div class="wrap">
            <div class="section-head">
                <h2>From intake to internal brief in three steps</h2>
                <p>Same rhythm your account team already uses—without an afternoon lost to formatting.</p>
            </div>
            <div class="steps">
                <div class="step">
                    <div class="step-num">01</div>
                    <h3>Paste client notes</h3>
                    <p>Email forwards, discovery call bullets, or a messy voice-memo transcript. However the client actually talks to you.</p>
                </div>
                <div class="step">
                    <div class="step-num">02</div>
                    <h3>Review the draft</h3>
                    <p>Seven clear sections—goals, audience, scope, deliverables, assumptions, and timeline—ready for your edits.</p>
                </div>
                <div class="step">
                    <div class="step-num">03</div>
                    <h3>Send when you're ready</h3>
                    <p>Copy into Notion, Google Docs, or your PM tool. Nothing goes to your client until you say so.</p>
                </div>
            </div>
        </div>
    </section>

    <section class="workspace" id="tool">
        <div class="wrap">
            <div class="section-head">
                <h2>Try it on real notes</h2>
                <p>Paste below or load a sample. First brief asks for your work email—then you're set.</p>
            </div>
            <div class="tool-shell">
                <div class="tool-tabs">
                    <span class="active">Intake</span>
                    <span>Brief output</span>
                </div>
                <div class="desk">
                    <div class="desk-in">
                        <label class="field-label" for="notes-input">Client notes</label>
                        <div class="input-tools">
                            <button type="button" class="chip" id="sample-btn">Load sample notes</button>
                        </div>
                        <textarea id="notes-input" placeholder="Paste client intake here…"></textarea>
                        <p class="hint">Tip: Ctrl+Enter (⌘+Enter on Mac) to create brief</p>
                        <div class="field-error" id="notes-error"></div>
                        <button class="btn-draft" id="draft-btn" type="button">Create brief</button>
                    </div>
                    <div class="desk-out">
                        <div class="out-meta">
                            <span>Brief · <span id="doc-ref">—</span></span>
                            <span class="status-pill" id="doc-date">Awaiting input</span>
                        </div>
                        <div class="out-placeholder" id="placeholder-state">
                            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/></svg>
                            <p id="placeholder-msg">Your formatted brief appears here—ready to copy and tweak.</p>
                        </div>
                        <div id="result-body"></div>
                        <button class="btn-copy" id="copy-btn" type="button">Copy brief</button>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <section class="section-light" id="why">
        <div class="wrap">
            <div class="section-head">
                <h2>You're running accounts—not retyping briefs</h2>
                <p>Built for boutiques and small agencies where the same person sells the work, writes the scope, and still has to deliver.</p>
            </div>
            <div class="benefits">
                <div class="benefit">
                    <h3>Hours back on every new job</h3>
                    <p>Skip the blank doc. Start from a structured draft so production and design can estimate sooner.</p>
                </div>
                <div class="benefit">
                    <h3>Scope you can defend</h3>
                    <p>Assumptions and open questions sit in their own section—so change requests don't sneak in as "small tweaks."</p>
                </div>
                <div class="benefit">
                    <h3>Works how clients actually brief you</h3>
                    <p>No templates to fill first. Drop in the ramble; get sections that match how your team already writes SOWs.</p>
                </div>
                <div class="benefit">
                    <h3>Not another reporting tool</h3>
                    <p>Unlike monthly performance reports, this is for <strong>project intake</strong>—before the work starts and scope still moves.</p>
                </div>
            </div>
        </div>
    </section>

    <section class="faq" id="faq">
        <div class="wrap">
            <div class="section-head">
                <h2>Common questions</h2>
            </div>
            <div class="faq-list">
                <details>
                    <summary>Do I still edit before the client sees it?</summary>
                    <p>Always. You get a draft to reshape, price, and approve. Nothing is sent on your behalf.</p>
                </details>
                <details>
                    <summary>Why do you ask for my email?</summary>
                    <p>Once, so we know who's using the tool. We require a work email (name@company.com) to prevent spam—no free providers like Gmail.</p>
                </details>
                <details>
                    <summary>What happens to client notes?</summary>
                    <p>Notes and briefs are stored securely so you can revisit them. Delete requests are honored—contact us anytime.</p>
                </details>
                <details>
                    <summary>How is this different from client reporting software?</summary>
                    <p>Reporting tools summarize campaign results after the fact. ClientBrief AI is for the <em>front</em> of the job—turning vague intake into a scoped brief before production starts.</p>
                </details>
            </div>
        </div>
    </section>

    <section class="cta-band">
        <div class="wrap">
            <h2>Clear the intake backlog on your next new business call</h2>
            <a class="btn-primary" href="#tool">Create a brief</a>
        </div>
    </section>

    <footer>
        <div class="wrap">© 2026 ClientBrief AI · Built for agencies</div>
    </footer>

    <div class="gate-overlay" id="email-gate">
        <div class="gate-card">
            <button class="gate-close" id="gate-close" type="button" aria-label="Close">&times;</button>
            <h2>Almost there</h2>
            <p>Enter your full work email so we know who’s using the tool (e.g. jordan@youragency.com). No free emails.</p>
            <input type="text" id="gate-email" autocomplete="email" inputmode="email" spellcheck="false" placeholder="jordan@youragency.com" aria-label="Work email address">
            <div class="field-error" id="gate-error"></div>
            <button class="btn-gate" id="gate-submit" type="button">Continue</button>
        </div>
    </div>

    <script>
        const EMAIL_KEY = 'clientbrief_email';
        let pendingNotes = null;
        
        // Frontend blocklist for instant rejection of free emails
        const BLOCKED_DOMAINS_JS = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "live.com", "aol.com", "icloud.com", "protonmail.com", "zoho.com", "msn.com", "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com", "yopmail.com", "trashmail.com", "getnada.com", "googlemail.com", "gmx.com"];

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
            const email = (raw || '').trim().toLowerCase();
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
            
            // Block free providers instantly
            if (BLOCKED_DOMAINS_JS.includes(domain)) return false;

            if (!/^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$/.test(email)) return false;
            return true;
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
            document.getElementById('doc-date').textContent = 'Draft ready';
        }

        const SAMPLE_NOTES = "Hey team — client wants something for Q4 product launch. Social (Meta + maybe TikTok), landing page, they mentioned 'premium but approachable'. Budget not confirmed yet, ballpark 15–20k. No purple (CEO hates it). Competitor Lumina just rebranded — client wants to look distinct. Need first concepts in ~3 weeks if possible.";

        document.getElementById('sample-btn').addEventListener('click', function () {
            document.getElementById('notes-input').value = SAMPLE_NOTES;
            document.getElementById('notes-error').textContent = '';
        });

        async function draftBrief(notes, email) {
            const btn = document.getElementById('draft-btn');
            const notesError = document.getElementById('notes-error');
            const placeholder = document.getElementById('placeholder-state');
            const resultBody = document.getElementById('result-body');
            const copyBtn = document.getElementById('copy-btn');
            const docDate = document.getElementById('doc-date');
            btn.disabled = true;
            btn.textContent = 'Building your brief…';
            notesError.textContent = '';
            resultBody.classList.remove('visible');
            copyBtn.classList.remove('visible');
            placeholder.style.display = 'flex';
            placeholder.querySelector('p') || (function () {
                var p = document.createElement('p');
                placeholder.appendChild(p);
            })();
            var phText = placeholder.querySelector('p') || placeholder;
            if (placeholder.querySelector('p')) {
                placeholder.querySelector('p').textContent = 'Organizing sections…';
            } else {
                placeholder.childNodes.forEach(function (n) {
                    if (n.nodeType === 3) n.textContent = '';
                });
                placeholder.lastChild && placeholder.lastChild.textContent && (placeholder.lastChild.textContent = 'Organizing sections…');
            }
            docDate.textContent = 'In progress';

            try {
                let url = '/generate-brief?notes=' + encodeURIComponent(notes);
                if (email) url += '&email=' + encodeURIComponent(email);
                const response = await fetch(url);
                const data = await response.json();
                
                if (!response.ok) {
                    // If the backend rejects the email, clear it and force the user to re-enter
                    if (response.status === 400 && data.error && data.error.toLowerCase().includes('work email')) {
                        clearSavedEmail();
                        document.getElementById('gate-error').textContent = data.error;
                        document.getElementById('gate-email').classList.add('invalid');
                        openGate();
                        throw new Error(data.error);
                    }
                    throw new Error(data.error || 'Could not create the brief.');
                }
                
                renderBrief(data.plan || '');
            } catch (e) {
                placeholder.style.display = 'flex';
                var msg = placeholder.querySelector('p');
                if (msg) msg.textContent = e.message || 'Something went wrong. Try again.';
                docDate.textContent = 'Error';
            } finally {
                btn.disabled = false;
                btn.textContent = 'Create brief';
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
                gateError.textContent = 'Please use a valid work email. Free providers (Gmail, Yahoo, etc.) are blocked.';
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