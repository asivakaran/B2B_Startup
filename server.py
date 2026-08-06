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
        # UPGRADED PROMPT: The "Strategist's Edge"
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
            max_tokens=800,  # Increased token limit to accommodate the deeper strategy
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
    <title>ClientBrief AI — From Chaos to Strategy in 60 Seconds</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="Don't just format messy client notes. Turn them into a strategically brilliant, client-ready brief with KPIs, assumptions, and timelines in under a minute.">
    <meta name="theme-color" content="#08090f">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&family=Newsreader:opsz,wght@6..72,400;6..72,600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #08090f;
            --bg-soft: #0f111a;
            --surface: rgba(255, 255, 255, 0.03);
            --surface-border: rgba(255, 255, 255, 0.08);
            --surface-hover: rgba(255, 255, 255, 0.06);
            --text: #ffffff;
            --text-muted: #8b8da3;
            --paper: #ffffff;
            --paper-ink: #0f111a;
            --paper-ink-soft: #4a5568;
            --accent-1: #00f2fe; /* Electric Cyan */
            --accent-2: #4facfe; /* Bright Blue */
            --accent-3: #ff007a; /* Neon Magenta */
            --accent-glow: rgba(0, 242, 254, 0.4);
            --line: rgba(255, 255, 255, 0.08);
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            background: var(--bg);
            color: var(--text);
            font-family: 'Inter', system-ui, sans-serif;
            -webkit-font-smoothing: antialiased;
            overflow-x: hidden;
            position: relative;
        }

        /* Vibrant Ambient Background Glows */
        body::before {
            content: '';
            position: fixed;
            top: -20%;
            left: -10%;
            width: 60%;
            height: 60%;
            background: radial-gradient(circle, rgba(79, 172, 254, 0.15), transparent 60%);
            filter: blur(80px);
            z-index: 0;
            pointer-events: none;
        }
        body::after {
            content: '';
            position: fixed;
            bottom: -20%;
            right: -10%;
            width: 60%;
            height: 60%;
            background: radial-gradient(circle, rgba(255, 0, 122, 0.12), transparent 60%);
            filter: blur(80px);
            z-index: 0;
            pointer-events: none;
        }

        .wrap { max-width: 1100px; margin: 0 auto; padding: 0 24px; position: relative; z-index: 1; }
        section[id] { scroll-margin-top: 84px; }
        a { color: inherit; text-decoration: none; }

        .wordmark {
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 700;
            letter-spacing: -0.02em;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-size: 1.2rem;
        }
        .wordmark .logo-dot {
            width: 10px;
            height: 10px;
            background: linear-gradient(135deg, var(--accent-1), var(--accent-3));
            border-radius: 2px;
            box-shadow: 0 0 12px var(--accent-1);
        }
        .wordmark span { color: var(--accent-1); }

        /* ---------- NAV ---------- */
        .topnav {
            position: sticky;
            top: 0;
            z-index: 30;
            background: rgba(8, 9, 15, 0.75);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-bottom: 1px solid var(--line);
        }
        .topnav .wrap { display: flex; align-items: center; justify-content: space-between; height: 70px; }
        .nav-links { display: flex; gap: 32px; list-style: none; }
        .nav-links a { color: var(--text-muted); font-size: 0.9rem; font-weight: 500; transition: color 0.2s ease; }
        .nav-links a:hover { color: var(--text); }
        
        .btn-small {
            background: rgba(255, 255, 255, 0.08);
            color: var(--text);
            border: 1px solid var(--surface-border);
            border-radius: 8px;
            padding: 10px 18px;
            font-size: 0.85rem;
            font-weight: 600;
            transition: all 0.2s ease;
        }
        .btn-small:hover { background: rgba(255, 255, 255, 0.12); border-color: var(--accent-1); box-shadow: 0 0 15px var(--accent-glow); }
        
        @media (max-width: 760px) { .nav-links { display: none; } }

        /* ---------- BUTTONS ---------- */
        .btn-primary-lg {
            background: linear-gradient(135deg, var(--accent-1) 0%, var(--accent-2) 100%);
            color: #00121a;
            border: none;
            border-radius: 8px;
            padding: 16px 28px;
            font-size: 1rem;
            font-weight: 700;
            display: inline-block;
            transition: all 0.2s ease;
            box-shadow: 0 4px 20px rgba(0, 242, 254, 0.3);
            cursor: pointer;
        }
        .btn-primary-lg:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0, 242, 254, 0.5); }
        
        .link-muted { color: var(--text-muted); font-size: 0.95rem; border-bottom: 1px dashed var(--text-muted); padding-bottom: 2px; transition: color 0.2s; }
        .link-muted:hover { color: var(--text); }

        /* ---------- HERO ---------- */
        .hero { padding: 100px 0 120px; text-align: center; }
        .eyebrow {
            display: inline-block;
            font-family: 'Space Grotesk', monospace;
            font-size: 0.75rem;
            letter-spacing: 0.15em;
            color: var(--accent-1);
            text-transform: uppercase;
            margin: 0 0 24px;
            background: rgba(0, 242, 254, 0.08);
            padding: 6px 14px;
            border-radius: 20px;
            border: 1px solid rgba(0, 242, 254, 0.2);
        }
        .hero h1 {
            font-family: 'Newsreader', serif;
            font-size: clamp(2.5rem, 6vw, 4.5rem);
            line-height: 1.1;
            margin: 0 auto 24px;
            max-width: 900px;
            letter-spacing: -0.02em;
            font-weight: 400;
        }
        .hero h1 .highlight {
            background: linear-gradient(135deg, var(--accent-1), var(--accent-3));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-style: italic;
        }
        .hero .lede { 
            color: var(--text-muted); 
            font-size: 1.15rem; 
            line-height: 1.6; 
            max-width: 600px; 
            margin: 0 auto 40px; 
        }
        .hero-ctas { display: flex; align-items: center; justify-content: center; gap: 24px; flex-wrap: wrap; }

        /* Hero Visual Placeholder */
        .hero-visual {
            margin-top: 80px;
            position: relative;
            padding: 20px;
            background: var(--surface);
            border: 1px solid var(--surface-border);
            border-radius: 16px;
            backdrop-filter: blur(10px);
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        }
        .ui-mockup {
            background: var(--bg-soft);
            border-radius: 8px;
            padding: 20px;
            text-align: left;
            font-family: 'Space Grotesk', monospace;
            font-size: 0.85rem;
        }
        .ui-mockup .dot-row { display: flex; gap: 6px; margin-bottom: 16px; }
        .ui-mockup .dot { width: 10px; height: 10px; border-radius: 50%; background: #333; }
        .ui-mockup .line { height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; margin-bottom: 8px; }
        .ui-mockup .line.short { width: 40%; }
        .ui-mockup .line.med { width: 70%; }
        .ui-mockup .line.accent { background: var(--accent-1); width: 30%; }

        /* ---------- SECTION SHELL ---------- */
        .section { padding: 100px 0; }
        .section-intro { max-width: 700px; margin: 0 auto 60px; text-align: center; }
        .section-intro h2 { 
            font-family: 'Newsreader', serif; 
            font-size: clamp(2rem, 4vw, 3rem); 
            line-height: 1.2;
            font-weight: 400;
            letter-spacing: -0.01em;
        }
        .section-intro p { color: var(--text-muted); margin-top: 16px; font-size: 1.1rem; }

        /* ---------- HOW IT WORKS ---------- */
        .steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; }
        .step { 
            background: var(--surface); 
            border: 1px solid var(--surface-border); 
            border-radius: 12px; 
            padding: 32px; 
            transition: all 0.3s ease;
        }
        .step:hover { border-color: var(--accent-1); transform: translateY(-4px); box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
        .step .step-no { 
            font-family: 'Space Grotesk', monospace; 
            color: var(--accent-1); 
            font-size: 0.9rem; 
            font-weight: 700; 
            margin-bottom: 12px; 
            display: block;
        }
        .step h3 { font-family: 'Inter', sans-serif; font-size: 1.25rem; margin: 0 0 12px; font-weight: 600; }
        .step p { color: var(--text-muted); font-size: 0.95rem; line-height: 1.6; }
        @media (max-width: 820px) { .steps { grid-template-columns: 1fr; } }

        /* ---------- WHY / FEATURES ---------- */
        .features-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px; }
        .feature-card { 
            background: var(--surface); 
            border: 1px solid var(--surface-border); 
            border-radius: 12px; 
            padding: 32px;
            position: relative;
            overflow: hidden;
        }
        .feature-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: linear-gradient(to bottom, var(--accent-1), var(--accent-3));
        }
        .feature-card h3 { font-family: 'Inter', sans-serif; font-size: 1.2rem; margin: 0 0 12px; font-weight: 600; }
        .feature-card p { color: var(--text-muted); font-size: 0.95rem; line-height: 1.6; }
        @media (max-width: 720px) { .features-grid { grid-template-columns: 1fr; } }

        /* ---------- TOOL ---------- */
        .tool-inner { max-width: 680px; margin: 0 auto; }
        .card { 
            background: var(--surface); 
            border: 1px solid var(--surface-border); 
            border-radius: 16px; 
            padding: 32px; 
            backdrop-filter: blur(10px);
        }
        .field-label {
            font-family: 'Space Grotesk', monospace; 
            font-size: 0.8rem; letter-spacing: 0.1em;
            color: var(--text-muted); text-transform: uppercase; display: block; margin-bottom: 12px;
            font-weight: 600;
        }
        textarea#notes-input {
            width: 100%; min-height: 160px; resize: vertical; background: var(--bg-soft);
            border: 1px solid var(--surface-border); border-radius: 8px; color: var(--text);
            font-family: 'Inter', sans-serif; font-size: 1rem; line-height: 1.5; padding: 16px; outline: none;
            transition: border-color 0.2s;
        }
        textarea#notes-input::placeholder { color: #555; }
        textarea#notes-input:focus-visible { border-color: var(--accent-1); box-shadow: 0 0 0 3px var(--accent-glow); }
        
        .error-text { display: none; color: var(--accent-3); font-size: 0.9rem; margin-top: 8px; }
        .error-text.visible { display: block; }
        
        button.primary { /* overrides btn-primary-lg just in case */
            margin-top: 20px; width: 100%; 
        }

        /* Document Output */
        .doc-wrap { display: none; width: 100%; max-width: 680px; margin: 40px auto 0; }
        .doc-wrap.visible { display: block; animation: slideUp 0.5s ease; }
        
        @keyframes slideUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .doc {
            background: var(--paper);
            color: var(--paper-ink);
            border-radius: 8px;
            padding: 48px;
            box-shadow: 0 20px 50px -10px rgba(0, 0, 0, 0.8);
            position: relative;
        }
        .doc-letterhead {
            display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px;
            font-family: 'Space Grotesk', monospace; font-size: 0.75rem; letter-spacing: 0.1em;
            color: var(--paper-ink-soft); text-transform: uppercase;
            border-bottom: 2px solid var(--paper-ink); padding-bottom: 16px; margin-bottom: 24px;
            font-weight: 600;
        }
        .status-tag { background: var(--paper-ink); color: var(--paper); border-radius: 4px; padding: 2px 8px; }
        
        .doc h3 { font-family: 'Newsreader', serif; font-size: 1.3rem; margin: 24px 0 8px; font-weight: 600; }
        .doc h3:first-child { margin-top: 0; }
        .doc p { font-family: 'Inter', sans-serif; font-size: 1rem; line-height: 1.7; margin: 0 0 8px; color: #333; }
        
        .copy-link {
            display: block; margin: 20px auto 0; background: var(--bg-soft); border: 1px solid var(--surface-border); color: var(--text);
            font-family: 'Space Grotesk', monospace; font-size: 0.85rem; letter-spacing: 0.05em;
            text-transform: uppercase; cursor: pointer; padding: 12px 24px; border-radius: 8px; transition: all 0.2s;
        }
        .copy-link:hover { border-color: var(--accent-1); color: var(--accent-1); }

        /* ---------- FAQ ---------- */
        .faq-list { max-width: 760px; margin: 0 auto; border-top: 1px solid var(--line); }
        .faq-item { border-bottom: 1px solid var(--line); padding: 24px 0; }
        .faq-item summary {
            cursor: pointer; list-style: none; display: flex; align-items: center; justify-content: space-between;
            gap: 16px; font-family: 'Inter', sans-serif; font-size: 1.15rem; font-weight: 500;
        }
        .faq-item summary::-webkit-details-marker { display: none; }
        .faq-item summary::after { content: '+'; font-family: 'Space Grotesk', monospace; color: var(--accent-1); font-size: 1.5rem; flex-shrink: 0; }
        .faq-item[open] summary::after { content: '−'; }
        .faq-item .faq-answer { color: var(--text-muted); font-size: 1rem; line-height: 1.7; margin: 16px 0 0; max-width: 680px; }

        /* ---------- FOOTER ---------- */
        .site-footer { padding: 80px 0 60px; border-top: 1px solid var(--line); text-align: center; }
        .site-footer .foot-tagline { color: var(--text-muted); max-width: 500px; margin: 16px auto 30px; font-size: 1rem; line-height: 1.6; }
        .site-footer .small { color: var(--text-muted); opacity: 0.5; font-size: 0.85rem; margin-top: 40px; font-family: 'Space Grotesk', monospace; }

        /* ---------- EMAIL GATE ---------- */
        .gate-overlay {
            display: none; position: fixed; inset: 0; background: rgba(8, 9, 15, 0.85);
            backdrop-filter: blur(8px);
            align-items: center; justify-content: center; padding: 20px; z-index: 100;
        }
        .gate-overlay.visible { display: flex; }
        .gate-card {
            background: var(--bg-soft); border: 1px solid var(--surface-border); border-radius: 16px;
            padding: 40px; max-width: 420px; width: 100%; text-align: center; position: relative;
            box-shadow: 0 0 40px rgba(0, 242, 254, 0.1);
        }
        .gate-seal {
            width: 56px; height: 56px; background: linear-gradient(135deg, var(--accent-1), var(--accent-3)); border-radius: 12px; margin: 0 auto 24px;
            display: flex; align-items: center; justify-content: center;
            font-family: 'Space Grotesk', sans-serif; color: #000; font-size: 1.2rem; font-weight: 700;
        }
        .gate-card h2 { font-family: 'Newsreader', serif; font-size: 1.8rem; margin: 0 0 12px; font-weight: 400; }
        .gate-card .gate-copy { color: var(--text-muted); font-size: 0.95rem; margin: 0 0 24px; line-height: 1.5; }
        input#gate-email {
            width: 100%; background: var(--bg); border: 1px solid var(--surface-border); border-radius: 8px;
            color: var(--text); font-family: 'Inter', sans-serif; font-size: 1rem;
            padding: 14px 16px; outline: none; margin-bottom: 12px; transition: border-color 0.2s;
        }
        input#gate-email::placeholder { color: #444; }
        input#gate-email:focus-visible { border-color: var(--accent-1); }
        .gate-close {
            position: absolute; top: 16px; right: 16px; background: none; border: none;
            color: var(--text-muted); font-size: 1.5rem; cursor: pointer; line-height: 1;
        }

        @media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
        @media (max-width: 480px) {
            .doc { padding: 32px 24px; }
            .card { padding: 24px; }
            .gate-card { padding: 32px 24px; }
        }
    </style>
</head>
<body>
    <nav class="topnav">
        <div class="wrap">
            <div class="wordmark">
                <div class="logo-dot"></div>
                Client<span>Brief</span> AI
            </div>
            <ul class="nav-links">
                <li><a href="#how">How it Works</a></li>
                <li><a href="#why">The Edge</a></li>
                <li><a href="#faq">FAQ</a></li>
            </ul>
            <a href="#tool" class="btn-small">Draft a Brief</a>
        </div>
    </nav>

    <header class="hero">
        <div class="wrap">
            <p class="eyebrow">The Strategist's Edge</p>
            <h1>Turn Client Chaos into <span class="highlight">Billable Strategy</span> in 60 Seconds.</h1>
            <p class="lede">Stop wrangling messy notes into formatting. Paste the rambling email, and get back a comprehensive, strategically sound brief complete with KPIs, timelines, and inferred insights. It's like having a Senior Strategist on call.</p>
            <div class="hero-ctas">
                <a href="#tool" class="btn-primary-lg">Draft a Brief — Free</a>
                <a href="#why" class="link-muted">See the strategic edge ↓</a>
            </div>
            
            <div class="hero-visual">
                <div class="ui-mockup">
                    <div class="dot-row">
                        <div class="dot" style="background:#ff5f56"></div>
                        <div class="dot" style="background:#ffbd2e"></div>
                        <div class="dot" style="background:#27c93f"></div>
                    </div>
                    <div class="line med"></div>
                    <div class="line short"></div>
                    <div class="line" style="margin-top:20px"></div>
                    <div class="line med"></div>
                    <div class="line short"></div>
                    <div class="line accent" style="margin-top:20px"></div>
                    <div class="line"></div>
                </div>
            </div>
        </div>
    </header>

    <section class="section" id="how">
        <div class="wrap">
            <div class="section-intro">
                <h2>From brain-dump to boardroom-ready.</h2>
                <p>Three steps to a brief that actually moves the project forward.</p>
            </div>
            <div class="steps">
                <div class="step">
                    <span class="step-no">01 / INPUT</span>
                    <h3>Paste the Chaos</h3>
                    <p>An email thread, a rushed Slack message, or a messy call transcript. However it arrived, just paste it in.</p>
                </div>
                <div class="step">
                    <span class="step-no">02 / STRATEGY</span>
                    <h3>AI Fills the Gaps</h3>
                    <p>The engine generates a 7-section brief, logically inferring target audience, suggesting KPIs, and projecting a timeline.</p>
                </div>
                <div class="step">
                    <span class="step-no">03 / DELIVER</span>
                    <h3>Send with Confidence</h3>
                    <p>Copy the pristine, professionally formatted document straight into your proposal, deck, or project management tool.</p>
                </div>
            </div>
        </div>
    </section>

    <section class="section" id="why">
        <div class="wrap">
            <div class="section-intro">
                <h2>The Factor That Makes You Prefer It.</h2>
                <p>Anyone can format text. We strategize it.</p>
            </div>
            <div class="features-grid">
                <div class="feature-card">
                    <h3>Strategic Assumptions</h3>
                    <p>Clients never give you everything. Our AI explicitly lists the strategic gaps it filled, so you know exactly what to validate before the kickoff.</p>
                </div>
                <div class="feature-card">
                    <h3>Projected KPIs & Metrics</h3>
                    <p>A brief isn't a brief without success metrics. The tool automatically suggests relevant KPIs based on the inferred business goals.</p>
                </div>
                <div class="feature-card">
                    <h3>Suggested Timelines</h3>
                    <p>Stop guessing how long things will take. The AI drafts a logical, phased timeline based on the scope of work requested.</p>
                </div>
                <div class="feature-card">
                    <h3>Elite Agency Tone</h3>
                    <p>Reads like it was written by a Senior Account Director. Confident, formal, and completely free of chatbot clichés.</p>
                </div>
            </div>
        </div>
    </section>

    <section class="section tool" id="tool" style="background: var(--bg-soft); border-top: 1px solid var(--line); border-bottom: 1px solid var(--line);">
        <div class="wrap">
            <div class="section-intro">
                <p class="eyebrow">The Generator</p>
                <h2>Give this one a job number.</h2>
            </div>
            <div class="tool-inner">
                <div class="card">
                    <label class="field-label" for="notes-input">Raw Client Notes / Ramble</label>
                    <textarea id="notes-input" placeholder="e.g. hey can u whip up smth for the launch, need social + a landing page, budget is tight, oh and my sister said purple is unlucky so no purple..."></textarea>
                    <div class="error-text" id="notes-error"></div>
                    <button class="btn-primary-lg primary" id="draft-btn" type="button" style="margin-top: 20px; width: 100%;">Generate Strategic Brief</button>
                </div>

                <div class="doc-wrap" id="result-wrap">
                    <div class="doc">
                        <div class="doc-letterhead">
                            <span id="doc-ref">JOB NO. 0000</span>
                            <span id="doc-date">DATE: —</span>
                            <span class="status-tag">STATUS: DRAFT</span>
                        </div>
                        <div id="result-body"></div>
                    </div>
                    <button class="copy-link" id="copy-btn" type="button">Copy Brief to Clipboard</button>
                </div>
            </div>
        </div>
    </section>

    <section class="section" id="faq">
        <div class="wrap">
            <div class="section-intro">
                <h2>Questions, answered.</h2>
            </div>
            <div class="faq-list">
                <details class="faq-item">
                    <summary>Does this replace a strategist?</summary>
                    <p class="faq-answer">No — think of it as a 10x multiplier. It gets you from a blank page to a 90% finished, strategically structured brief in under a minute. You still bring the final human polish and judgment.</p>
                </details>
                <details class="faq-item">
                    <summary>How does it handle completely chaotic notes?</summary>
                    <p class="faq-answer">That's its specialty. The AI parses the intent behind the mess, structures it logically, and—crucially—includes a "Strategic Assumptions" section so you can see exactly what it inferred from the chaos.</p>
                </details>
                <details class="faq-item">
                    <summary>Is my client's information stored?</summary>
                    <p class="faq-answer">Yes, securely. Each brief is saved along with the notes that generated it so you can reference it later. Nothing is ever sent directly to your client without your explicit action.</p>
                </details>
                <details class="faq-item">
                    <summary>Can I edit the brief after it's generated?</summary>
                    <p class="faq-answer">Always. We provide a one-click copy to clipboard. Paste it into Google Docs, Notion, or Word and make it entirely your own.</p>
                </details>
            </div>
        </div>
    </section>

    <footer class="site-footer">
        <div class="wrap">
            <div class="wordmark">
                <div class="logo-dot"></div>
                Client<span>Brief</span> AI
            </div>
            <p class="foot-tagline">Stop formatting text. Start delivering strategy. Built for agencies who value billable hours over busywork.</p>
            <a href="#tool" class="btn-primary-lg">Draft a Brief — Free</a>
            <p class="small">© 2026 ClientBrief AI. All rights reserved.</p>
        </div>
    </footer>

    <div class="gate-overlay" id="email-gate">
        <div class="gate-card">
            <button class="gate-close" id="gate-close" type="button" aria-label="Close">×</button>
            <div class="gate-seal">CB</div>
            <h2>Unlock the Strategy</h2>
            <p class="gate-copy">Drop your email to generate your first strategic brief. No spam—just smarter workflows.</p>
            <input type="email" id="gate-email" placeholder="you@agency.com" aria-label="Email address">
            <div class="error-text" id="gate-error"></div>
            <button class="btn-primary-lg" id="gate-submit" type="button" style="width: 100%;">Get My Brief</button>
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
                'JOB NO. ' + Math.floor(1000 + Math.random() * 9000);
            document.getElementById('doc-date').textContent =
                'DATE: ' + new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).toUpperCase();
        }

        async function draftBrief(notes, email) {
            const resultWrap = document.getElementById('result-wrap');
            const btn = document.getElementById('draft-btn');
            btn.disabled = true;
            btn.textContent = 'Strategizing...';
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
                btn.textContent = 'Generate Strategic Brief';
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
                btn.textContent = 'Copied! Paste it anywhere.';
                setTimeout(function () { btn.textContent = original; }, 2000);
            } catch (e) {
                alert('Could not copy automatically — select the text and copy manually.');
            }
        });
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)