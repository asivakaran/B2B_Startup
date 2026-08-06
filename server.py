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
    <title>ClientBrief AI — Client Briefs for Marketing Agencies</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="Paste messy client notes and get back a structured, client-ready brief in under a minute. Built for marketing and creative agencies.">
    <meta name="theme-color" content="#1c1611">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,500;8..60,600;8..60,700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #1c1611;
            --surface: #251d16;
            --surface-border: #3a2d1f;
            --text: #ece4d3;
            --text-muted: #93877b;
            --paper: #ddd0a8;
            --paper-ink: #2b2013;
            --paper-ink-soft: #5f4d34;
            --pink: #b3606b;
            --pink-bright: #c47680;
            --gold: #b28d3c;
            --line: rgba(236, 228, 211, 0.09);
        }
        html { scroll-behavior: smooth; }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            background: var(--bg);
            color: var(--text);
            font-family: 'IBM Plex Sans', system-ui, sans-serif;
            -webkit-font-smoothing: antialiased;
        }
        .wrap { max-width: 1080px; margin: 0 auto; padding: 0 24px; }
        section[id] { scroll-margin-top: 84px; }
        a { color: inherit; }

        .wordmark {
            font-family: 'Source Serif 4', Georgia, serif;
            font-weight: 600;
            letter-spacing: 0.01em;
            display: inline-flex;
            align-items: baseline;
        }
        .wordmark span { color: var(--pink); }

        /* ---------- NAV ---------- */
        .topnav {
            position: sticky;
            top: 0;
            z-index: 30;
            background: rgba(28, 22, 17, 0.88);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border-bottom: 1px solid var(--line);
        }
        .topnav .wrap { display: flex; align-items: center; justify-content: space-between; height: 64px; }
        .topnav .wordmark { font-size: 1.2rem; }
        .nav-links { display: flex; gap: 30px; list-style: none; margin: 0; padding: 0; }
        .nav-links a { text-decoration: none; color: var(--text-muted); font-size: 0.88rem; transition: color 0.15s ease; }
        .nav-links a:hover { color: var(--text); }
        .nav-links a:focus-visible { outline: 2px solid var(--pink-bright); outline-offset: 3px; }
        .btn-small {
            display: inline-block;
            background: var(--pink);
            color: #fbf3e9;
            border: none;
            border-radius: 7px;
            padding: 9px 18px;
            font-size: 0.85rem;
            font-weight: 600;
            text-decoration: none;
            transition: background 0.15s ease;
        }
        .btn-small:hover { background: var(--pink-bright); }
        .btn-small:focus-visible { outline: 2px solid var(--pink-bright); outline-offset: 2px; }
        @media (max-width: 760px) { .nav-links { display: none; } }

        /* ---------- HERO ---------- */
        .hero { padding: 88px 0 90px; }
        .hero .wrap {
            display: grid;
            grid-template-columns: 1.05fr 0.95fr;
            gap: 60px;
            align-items: center;
        }
        .eyebrow {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.72rem;
            letter-spacing: 0.16em;
            color: var(--gold);
            text-transform: uppercase;
            margin: 0 0 18px;
        }
        .hero h1 {
            font-family: 'Source Serif 4', Georgia, serif;
            font-size: clamp(2.1rem, 4vw, 3rem);
            line-height: 1.16;
            margin: 0 0 20px;
            max-width: 540px;
        }
        .hero .lede { color: var(--text-muted); font-size: 1.04rem; line-height: 1.65; max-width: 440px; margin: 0 0 32px; }
        .hero-ctas { display: flex; align-items: center; gap: 24px; flex-wrap: wrap; }
        .btn-primary-lg {
            background: var(--pink);
            color: #fbf3e9;
            border: none;
            border-radius: 8px;
            padding: 14px 26px;
            font-size: 0.98rem;
            font-weight: 600;
            text-decoration: none;
            display: inline-block;
            transition: background 0.15s ease;
        }
        .btn-primary-lg:hover { background: var(--pink-bright); }
        .btn-primary-lg:focus-visible { outline: 2px solid var(--pink-bright); outline-offset: 2px; }
        .link-muted { color: var(--text-muted); text-decoration: none; font-size: 0.92rem; border-bottom: 1px dashed var(--surface-border); padding-bottom: 2px; }
        .link-muted:hover { color: var(--text); }
        @media (max-width: 880px) {
            .hero .wrap { grid-template-columns: 1fr; }
            .hero h1, .hero .lede { max-width: none; }
        }

        /* ---------- HERO DEMO (before / after) ---------- */
        .demo { display: flex; align-items: stretch; gap: 14px; }
        .demo-panel { flex: 1; min-width: 0; border-radius: 10px; padding: 20px; }
        .demo-panel.raw { background: var(--surface); border: 1px solid var(--surface-border); }
        .demo-panel.filed { background: var(--paper); color: var(--paper-ink); }
        .demo-label { font-family: 'IBM Plex Mono', monospace; font-size: 0.64rem; letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 12px; }
        .demo-panel.raw .demo-label { color: var(--text-muted); }
        .demo-panel.filed .demo-label { color: var(--paper-ink-soft); }
        .demo-panel.raw p { font-family: 'IBM Plex Mono', monospace; font-size: 0.8rem; color: #beb2a2; line-height: 1.7; margin: 0 0 3px; }
        .demo-panel.filed h4 { font-family: 'Source Serif 4', serif; font-size: 0.82rem; margin: 12px 0 3px; }
        .demo-panel.filed h4:first-of-type { margin-top: 0; }
        .demo-panel.filed p { font-family: 'Source Serif 4', serif; font-size: 0.78rem; color: var(--paper-ink-soft); line-height: 1.5; margin: 0 0 2px; }
        .demo-arrow {
            flex-shrink: 0; align-self: center; width: 30px; height: 30px; border-radius: 50%;
            border: 1px solid var(--surface-border); display: flex; align-items: center; justify-content: center;
            color: var(--gold); font-size: 0.85rem;
        }
        @media (max-width: 560px) {
            .demo { flex-direction: column; }
            .demo-arrow { transform: rotate(90deg); }
        }

        /* ---------- SECTION SHELL ---------- */
        .section { padding: 80px 0; }
        .section-intro { max-width: 600px; margin: 0 auto 44px; text-align: center; }
        .section-intro h2 { font-family: 'Source Serif 4', serif; font-size: clamp(1.55rem, 3vw, 2.05rem); margin: 0; line-height: 1.3; }

        /* ---------- HOW IT WORKS ---------- */
        .steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 30px; }
        .step { border-top: 2px solid var(--pink); padding-top: 20px; }
        .step .step-no { font-family: 'IBM Plex Mono', monospace; color: var(--text-muted); font-size: 0.76rem; letter-spacing: 0.1em; }
        .step h3 { font-family: 'Source Serif 4', serif; font-size: 1.12rem; margin: 10px 0 8px; }
        .step p { color: var(--text-muted); font-size: 0.92rem; line-height: 1.65; margin: 0; }
        @media (max-width: 820px) { .steps { grid-template-columns: 1fr; gap: 26px; } }

        /* ---------- WHY / FEATURES ---------- */
        .why { background: var(--surface); border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
        .features-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
        .feature-card { background: var(--bg); border: 1px solid var(--surface-border); border-radius: 10px; padding: 26px; }
        .feature-card h3 { font-family: 'Source Serif 4', serif; font-size: 1.03rem; margin: 0 0 10px; }
        .feature-card p { color: var(--text-muted); font-size: 0.9rem; line-height: 1.65; margin: 0; }
        @media (max-width: 720px) { .features-grid { grid-template-columns: 1fr; } }

        /* ---------- TOOL ---------- */
        .tool-inner { max-width: 560px; margin: 0 auto; }
        .card { background: var(--surface); border: 1px solid var(--surface-border); border-radius: 10px; padding: 28px; width: 100%; }
        .field-label {
            font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem; letter-spacing: 0.14em;
            color: var(--text-muted); text-transform: uppercase; display: block; margin-bottom: 10px;
        }
        textarea#notes-input {
            width: 100%; min-height: 140px; resize: vertical; background: #14100c;
            border: 1px solid var(--surface-border); border-radius: 8px; color: var(--text);
            font-family: 'IBM Plex Sans', sans-serif; font-size: 0.96rem; line-height: 1.5; padding: 14px; outline: none;
        }
        textarea#notes-input:focus-visible { border-color: var(--pink); }
        .error-text { display: none; color: #e0a3ab; font-size: 0.85rem; margin-top: 8px; }
        .error-text.visible { display: block; }
        button.primary {
            margin-top: 16px; width: 100%; background: var(--pink); color: #fbf3e9; border: none;
            border-radius: 8px; padding: 13px; font-family: 'IBM Plex Sans', sans-serif; font-size: 0.98rem;
            font-weight: 600; cursor: pointer; transition: background 0.15s ease;
        }
        button.primary:hover { background: var(--pink-bright); }
        button.primary:disabled { opacity: 0.6; cursor: default; }
        button.primary:focus-visible { outline: 2px solid var(--pink-bright); outline-offset: 2px; }

        .doc-wrap { display: none; width: 100%; max-width: 560px; margin: 34px auto 0; }
        .doc-wrap.visible { display: block; }
        .doc-stack { position: relative; }
        .doc-stack::before,
        .doc-stack::after {
            content: '';
            position: absolute;
            inset: 0;
            border-radius: 4px;
        }
        .doc-stack::before { background: var(--gold); transform: rotate(-2.5deg) translate(7px, 11px); z-index: 0; }
        .doc-stack::after { background: var(--pink); transform: rotate(-1.1deg) translate(3px, 6px); z-index: 1; }
        .doc {
            position: relative;
            z-index: 2;
            background: var(--paper);
            color: var(--paper-ink);
            border-radius: 4px;
            padding: 36px 40px;
            box-shadow: 0 20px 50px -20px rgba(0, 0, 0, 0.6);
        }
        .doc-letterhead {
            display: flex; justify-content: space-between; flex-wrap: wrap; gap: 6px;
            font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem; letter-spacing: 0.1em;
            color: var(--paper-ink-soft); text-transform: uppercase;
            border-bottom: 1px solid rgba(43, 32, 19, 0.25); padding-bottom: 12px; margin-bottom: 20px;
        }
        .status-tag { border: 1px solid var(--paper-ink-soft); border-radius: 4px; padding: 1px 8px; }
        .doc h3 { font-family: 'Source Serif 4', Georgia, serif; font-size: 1.08rem; margin: 22px 0 6px; }
        .doc h3:first-child { margin-top: 0; }
        .doc p { font-family: 'Source Serif 4', Georgia, serif; font-size: 0.98rem; line-height: 1.65; margin: 0 0 6px; }
        .copy-legend {
            display: flex; gap: 18px; flex-wrap: wrap; margin-top: 16px;
            font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; letter-spacing: 0.05em;
            color: var(--text-muted); text-transform: uppercase;
        }
        .copy-legend .dot { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 6px; vertical-align: middle; }
        .dot-cream { background: var(--paper); border: 1px solid var(--surface-border); }
        .dot-gold { background: var(--gold); }
        .dot-pink { background: var(--pink); }
        .copy-link {
            display: inline-block; margin-top: 14px; background: none; border: none; color: var(--text-muted);
            font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem; letter-spacing: 0.06em;
            text-transform: uppercase; cursor: pointer; padding: 0;
        }
        .copy-link:hover { color: var(--text); }

        /* ---------- ROUTING / SIGN-OFF STRIP ---------- */
        .routing { background: var(--surface); border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
        .routing-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }
        .routing-stub {
            border: 1px dashed var(--surface-border); border-radius: 8px; padding: 20px;
        }
        .routing-stub .role { font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; letter-spacing: 0.1em; color: var(--gold); text-transform: uppercase; margin-bottom: 10px; }
        .routing-stub p { font-family: 'Source Serif 4', serif; font-style: italic; font-size: 0.94rem; line-height: 1.6; margin: 0; color: var(--text); }
        @media (max-width: 820px) { .routing-grid { grid-template-columns: 1fr; } }

        /* ---------- FAQ ---------- */
        .faq-list { border-top: 1px solid var(--line); max-width: 740px; margin: 0 auto; }
        .faq-item { border-bottom: 1px solid var(--line); padding: 20px 0; }
        .faq-item summary {
            cursor: pointer; list-style: none; display: flex; align-items: center; justify-content: space-between;
            gap: 16px; font-family: 'Source Serif 4', serif; font-size: 1.03rem;
        }
        .faq-item summary::-webkit-details-marker { display: none; }
        .faq-item summary::after { content: '+'; font-family: 'IBM Plex Mono', monospace; color: var(--text-muted); font-size: 1.1rem; flex-shrink: 0; }
        .faq-item[open] summary::after { content: '−'; }
        .faq-item summary:focus-visible { outline: 2px solid var(--pink-bright); outline-offset: 3px; }
        .faq-item .faq-answer { color: var(--text-muted); font-size: 0.92rem; line-height: 1.7; margin: 14px 0 0; max-width: 620px; }

        /* ---------- FOOTER ---------- */
        .site-footer { padding: 60px 0 54px; border-top: 1px solid var(--line); text-align: center; }
        .site-footer .wordmark { font-size: 1.3rem; justify-content: center; margin-bottom: 12px; }
        .site-footer .foot-tagline { color: var(--text-muted); max-width: 420px; margin: 0 auto 26px; font-size: 0.92rem; line-height: 1.6; }
        .site-footer .small { color: var(--text-muted); opacity: 0.7; font-size: 0.78rem; margin-top: 26px; }

        /* ---------- EMAIL GATE ---------- */
        .gate-overlay {
            display: none; position: fixed; inset: 0; background: rgba(10, 8, 6, 0.72);
            align-items: center; justify-content: center; padding: 20px; z-index: 40;
        }
        .gate-overlay.visible { display: flex; }
        .gate-card {
            background: var(--surface); border: 1px solid var(--surface-border); border-radius: 10px;
            padding: 32px; max-width: 380px; width: 100%; text-align: center; position: relative;
        }
        .gate-seal {
            width: 44px; height: 44px; border: 2px solid var(--pink); border-radius: 50%; margin: 0 auto 16px;
            display: flex; align-items: center; justify-content: center;
            font-family: 'Source Serif 4', serif; color: var(--pink); font-size: 1.05rem;
        }
        .gate-card h2 { font-family: 'Source Serif 4', serif; font-size: 1.3rem; margin: 0 0 8px; }
        .gate-card .gate-copy { color: var(--text-muted); font-size: 0.9rem; margin: 0 0 20px; line-height: 1.5; }
        input#gate-email {
            width: 100%; background: #14100c; border: 1px solid var(--surface-border); border-radius: 8px;
            color: var(--text); font-family: 'IBM Plex Sans', sans-serif; font-size: 0.95rem;
            padding: 12px 14px; outline: none; margin-bottom: 12px;
        }
        input#gate-email:focus-visible { border-color: var(--pink); }
        .gate-close {
            position: absolute; top: 14px; right: 16px; background: none; border: none;
            color: var(--text-muted); font-size: 1.2rem; cursor: pointer; line-height: 1;
        }
        .gate-close:hover { color: var(--text); }

        @media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
        @media (max-width: 480px) {
            .doc { padding: 26px 22px; }
            .card { padding: 22px; }
        }
    </style>
</head>
<body>
    <nav class="topnav">
        <div class="wrap">
            <div class="wordmark">Client<span>Brief</span> AI</div>
            <ul class="nav-links">
                <li><a href="#how">How it Works</a></li>
                <li><a href="#why">Why it Works</a></li>
                <li><a href="#faq">FAQ</a></li>
            </ul>
            <a href="#tool" class="btn-small">Draft a Brief</a>
        </div>
    </nav>

    <header class="hero">
        <div class="wrap">
            <div class="hero-copy">
                <p class="eyebrow">For marketing &amp; creative agencies</p>
                <h1>Every client ramble gets a job number.</h1>
                <p class="lede">Paste in the notes — however messy. Get back a five-section brief, client-ready, in under a minute. The kind of thing an account lead would actually send with their name on it.</p>
                <div class="hero-ctas">
                    <a href="#tool" class="btn-primary-lg">Draft a Brief — Free</a>
                    <a href="#how" class="link-muted">See how it works ↓</a>
                </div>
            </div>
            <div class="hero-visual">
                <div class="demo">
                    <div class="demo-panel raw">
                        <div class="demo-label">As it came in</div>
                        <p>need smth for the product launch</p>
                        <p>social + landing page probably?</p>
                        <p>budget is tight rn</p>
                        <p>no purple anywhere lol</p>
                    </div>
                    <div class="demo-arrow">→</div>
                    <div class="demo-panel filed">
                        <div class="demo-label">Job No. 4471</div>
                        <h4>1. Project Overview</h4>
                        <p>A go-to-market push ahead of the client's...</p>
                        <h4>2. Business Goals</h4>
                        <p>Drive awareness and early sign-ups for...</p>
                    </div>
                </div>
            </div>
        </div>
    </header>

    <section class="section" id="how">
        <div class="wrap">
            <div class="section-intro">
                <p class="eyebrow">How it works</p>
                <h2>From client ramble to numbered brief.</h2>
            </div>
            <div class="steps">
                <div class="step">
                    <div class="step-no">01</div>
                    <h3>Paste the mess</h3>
                    <p>An email thread, call notes, a three-word text — however it actually arrived.</p>
                </div>
                <div class="step">
                    <div class="step-no">02</div>
                    <h3>It gets a number and a shape</h3>
                    <p>Five sections fill in — Overview, Goals, Audience, Scope, Deliverables — with a sensible call made wherever the client left a gap.</p>
                </div>
                <div class="step">
                    <div class="step-no">03</div>
                    <h3>Send it as your own</h3>
                    <p>Copy it into the proposal, the kickoff deck, or wherever it needs to go next.</p>
                </div>
            </div>
        </div>
    </section>

    <section class="section why" id="why">
        <div class="wrap">
            <div class="section-intro">
                <p class="eyebrow">Why it works</p>
                <h2>Built for the brief nobody wants to write.</h2>
            </div>
            <div class="features-grid">
                <div class="feature-card">
                    <h3>Fills gaps like a strategist</h3>
                    <p>Clients never hand over a complete brief. This makes a reasonable call instead of leaving a field blank.</p>
                </div>
                <div class="feature-card">
                    <h3>Reads any kind of mess</h3>
                    <p>Long email chains, three-word texts, a call transcript — the input doesn't need to be tidy.</p>
                </div>
                <div class="feature-card">
                    <h3>Sounds like an account lead</h3>
                    <p>Formal, agency-ready language — nothing that reads like a chatbot wrote it.</p>
                </div>
                <div class="feature-card">
                    <h3>Numbers every brief</h3>
                    <p>Each one gets a job number and a date, so nothing gets lost across a growing client list.</p>
                </div>
            </div>
        </div>
    </section>

    <section class="section tool" id="tool">
        <div class="wrap">
            <div class="section-intro">
                <p class="eyebrow">New job</p>
                <h2>Give this one a number.</h2>
            </div>
            <div class="tool-inner">
                <div class="card">
                    <label class="field-label" for="notes-input">Raw client notes</label>
                    <textarea id="notes-input" placeholder="e.g. hey can u whip up smth for the launch, need social + a landing page, budget is tight, oh and my sister said purple is unlucky so no purple..."></textarea>
                    <div class="error-text" id="notes-error"></div>
                    <button class="primary" id="draft-btn" type="button">Draft the Brief</button>
                </div>

                <div class="doc-wrap" id="result-wrap">
                    <div class="doc-stack">
                        <div class="doc">
                            <div class="doc-letterhead">
                                <span id="doc-ref">JOB NO. 0000</span>
                                <span id="doc-date">DATE: —</span>
                                <span class="status-tag">STATUS: PROOF</span>
                            </div>
                            <div id="result-body"></div>
                            <div class="copy-legend">
                                <span><span class="dot dot-cream"></span>Client copy</span>
                                <span><span class="dot dot-gold"></span>File copy</span>
                                <span><span class="dot dot-pink"></span>Internal copy</span>
                            </div>
                        </div>
                    </div>
                    <button class="copy-link" id="copy-btn" type="button">Copy brief</button>
                </div>
            </div>
        </div>
    </section>

    <section class="section routing">
        <div class="wrap">
            <div class="section-intro">
                <p class="eyebrow">Already moving through agencies</p>
                <h2>Signed off by the people who'd actually use it.</h2>
            </div>
            <!-- Placeholder sign-offs — swap in real quotes before launch -->
            <div class="routing-grid">
                <div class="routing-stub">
                    <div class="role">Accounts</div>
                    <p>"I stopped dreading the intake call. I paste my notes in on the drive home and it's basically done."</p>
                </div>
                <div class="routing-stub">
                    <div class="role">Creative</div>
                    <p>"Clients can't tell the difference between this and something I spent an hour formatting myself."</p>
                </div>
                <div class="routing-stub">
                    <div class="role">Traffic</div>
                    <p>"Every job used to sit blank for a day before anyone touched it. Now it has a shape before lunch."</p>
                </div>
            </div>
        </div>
    </section>

    <section class="section" id="faq">
        <div class="wrap">
            <div class="section-intro">
                <p class="eyebrow">Questions, answered</p>
                <h2>Before you start a job.</h2>
            </div>
            <div class="faq-list">
                <details class="faq-item">
                    <summary>Does this replace a strategist?</summary>
                    <p class="faq-answer">No — think of it as a strong first draft. It gets you from a blank page to a structured brief in under a minute; you still shape the final version.</p>
                </details>
                <details class="faq-item">
                    <summary>What if the client's notes are a total mess?</summary>
                    <p class="faq-answer">That's exactly what this is built for. The messier the input, the more useful it is — it makes sensible assumptions wherever the client left a gap, and you can adjust those afterward.</p>
                </details>
                <details class="faq-item">
                    <summary>Is my client's information stored anywhere?</summary>
                    <p class="faq-answer">Yes — each brief is saved along with the notes that generated it, so you can find it again later. Nothing is sent to your client automatically.</p>
                </details>
                <details class="faq-item">
                    <summary>Can I edit the brief after it's generated?</summary>
                    <p class="faq-answer">Always. Copy it out and edit freely — it's meant to save you the blank page, not replace your judgment.</p>
                </details>
            </div>
        </div>
    </section>

    <footer class="site-footer">
        <div class="wrap">
            <div class="wordmark">Client<span>Brief</span> AI</div>
            <p class="foot-tagline">Paste the rambling client email. Get back a brief you could send with your name on it.</p>
            <a href="#tool" class="btn-primary-lg">Draft a Brief — Free</a>
            <p class="small">© 2026 ClientBrief AI. Built for agencies who'd rather bill hours than write briefs.</p>
        </div>
    </footer>

    <div class="gate-overlay" id="email-gate">
        <div class="gate-card">
            <button class="gate-close" id="gate-close" type="button" aria-label="Close">×</button>
            <div class="gate-seal">CB</div>
            <h2>One more thing</h2>
            <p class="gate-copy">Drop your email and we'll hand over the finished brief. No spam — just briefs.</p>
            <input type="email" id="gate-email" placeholder="you@agency.com" aria-label="Email address">
            <div class="error-text" id="gate-error"></div>
            <button class="primary" id="gate-submit" type="button">Get My Brief</button>
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