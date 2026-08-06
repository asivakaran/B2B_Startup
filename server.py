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
<<<<<<< HEAD
            max_tokens=512,
=======
            max_tokens=800,  # Increased token limit to accommodate the deeper strategy
>>>>>>> parent of 2d9d4ca (Best version)
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
<<<<<<< HEAD
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
=======
    <title>ClientBrief AI — From Chaos to Strategy in 60 Seconds</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="Don't just format messy client notes. Turn them into a strategically brilliant, client-ready brief with KPIs, assumptions, and timelines in under a minute.">
    <meta name="theme-color" content="#F8F5F0">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #F8F5F0; /* Warm Paper White */
            --surface: #FFFFFF;
            --surface-dark: #111111;
            --text: #111111; /* Ink Black */
            --text-muted: #666666;
            --paper-ink-soft: #555555;
            --accent: #FF4D00; /* Electric Tangerine */
            --accent-hover: #E64500;
            --accent-soft: #FFE5D9;
            --border: #E5E1D9;
            --line: rgba(0, 0, 0, 0.08);
>>>>>>> parent of 2d9d4ca (Best version)
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            background: var(--bg);
            color: var(--text);
<<<<<<< HEAD
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
=======
            font-family: 'Inter', system-ui, sans-serif;
            -webkit-font-smoothing: antialiased;
            overflow-x: hidden;
            position: relative;
        }

        .wrap { max-width: 1200px; margin: 0 auto; padding: 0 32px; position: relative; }
        section[id] { scroll-margin-top: 84px; }
        a { color: inherit; text-decoration: none; }

        .wordmark {
            font-family: 'Fraunces', serif;
            font-weight: 700;
            letter-spacing: -0.02em;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-size: 1.4rem;
        }
        .wordmark .logo-dot {
            width: 12px;
            height: 12px;
            background: var(--accent);
            border-radius: 50%;
        }
        .wordmark span { font-style: italic; }

        /* ---------- NAV ---------- */
        .topnav {
            position: sticky;
            top: 0;
            z-index: 30;
            background: rgba(248, 245, 240, 0.85);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border);
        }
        .topnav .wrap { display: flex; align-items: center; justify-content: space-between; height: 72px; }
        .nav-links { display: flex; gap: 36px; list-style: none; }
        .nav-links a { color: var(--text-muted); font-size: 0.9rem; font-weight: 500; transition: color 0.2s ease; }
        .nav-links a:hover { color: var(--text); }
        
        .btn-small {
            background: var(--text);
            color: var(--bg);
            border: 1px solid var(--text);
            border-radius: 100px;
            padding: 10px 20px;
            font-size: 0.85rem;
            font-weight: 600;
            transition: all 0.2s ease;
        }
        .btn-small:hover { background: var(--accent); border-color: var(--accent); color: #fff; }
        
        @media (max-width: 760px) { .nav-links { display: none; } }

        /* ---------- BUTTONS ---------- */
        .btn-primary-lg {
            background: var(--accent);
            color: #FFFFFF;
            border: none;
            border-radius: 8px;
            padding: 16px 32px;
            font-size: 1rem;
            font-weight: 600;
            display: inline-block;
            transition: all 0.2s ease;
            cursor: pointer;
        }
        .btn-primary-lg:hover { background: var(--accent-hover); transform: translateY(-2px); }
        
        .link-muted { color: var(--text); font-size: 0.95rem; border-bottom: 1px solid var(--text); padding-bottom: 2px; transition: color 0.2s; }
        .link-muted:hover { color: var(--accent); border-color: var(--accent); }

        /* ---------- HERO ---------- */
        .hero { padding: 120px 0 80px; }
        .hero .wrap {
            display: grid;
            grid-template-columns: 1.2fr 0.8fr;
            gap: 60px;
            align-items: end;
        }
        .eyebrow {
            display: inline-flex;
            align-items: center;
            font-family: 'Inter', sans-serif;
            font-size: 0.8rem;
            letter-spacing: 0.05em;
            color: var(--accent);
            text-transform: uppercase;
            margin: 0 0 24px;
            font-weight: 600;
        }
        .eyebrow::before {
            content: '';
            display: inline-block;
            width: 24px;
            height: 1px;
            background: var(--accent);
            margin-right: 12px;
        }
        .hero h1 {
            font-family: 'Fraunces', serif;
            font-size: clamp(3rem, 7vw, 5.5rem);
            line-height: 0.95;
            margin: 0 0 32px;
            letter-spacing: -0.03em;
            font-weight: 600;
        }
        .hero h1 .highlight {
            font-style: italic;
            color: var(--accent);
            font-weight: 400;
        }
        .hero .lede { 
            color: var(--text-muted); 
            font-size: 1.15rem; 
            line-height: 1.6; 
            max-width: 520px; 
            margin: 0 0 40px; 
        }
        .hero-ctas { display: flex; align-items: center; gap: 24px; flex-wrap: wrap; }

        /* Hero Visual */
        .hero-visual {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 24px;
            box-shadow: 20px 20px 0px 0px var(--accent-soft);
            transition: transform 0.3s ease;
        }
        .hero-visual:hover { transform: translate(-5px, -5px); box-shadow: 25px 25px 0px 0px var(--accent-soft); }
        .visual-header { display: flex; justify-content: space-between; margin-bottom: 20px; font-family: 'Inter', sans-serif; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.1em; }
        .visual-tag { background: var(--text); color: var(--bg); padding: 2px 8px; border-radius: 4px; }
        .visual-line { height: 8px; background: var(--bg); border-radius: 4px; margin-bottom: 12px; }
        .visual-line.short { width: 40%; }
        .visual-line.med { width: 70%; }
        .visual-line.accent { background: var(--accent); width: 30%; margin-top: 24px; }

        /* ---------- SECTION SHELL ---------- */
        .section { padding: 100px 0; border-top: 1px solid var(--border); }
        .section-intro { max-width: 700px; margin: 0 auto 60px; text-align: center; }
        .section-intro h2 { 
            font-family: 'Fraunces', serif; 
            font-size: clamp(2.5rem, 5vw, 3.5rem); 
            line-height: 1.1;
            font-weight: 600;
            letter-spacing: -0.02em;
        }
        .section-intro h2 em { color: var(--accent); font-weight: 400; }
        .section-intro p { color: var(--text-muted); margin-top: 16px; font-size: 1.1rem; }

        /* ---------- HOW IT WORKS ---------- */
        .steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 32px; }
        .step { 
            background: var(--surface); 
            border: 1px solid var(--border); 
            border-radius: 8px; 
            padding: 32px; 
            transition: all 0.3s ease;
            position: relative;
        }
        .step:hover { border-color: var(--text); transform: translateY(-4px); }
        .step .step-no { 
            font-family: 'Fraunces', serif; 
            color: var(--accent); 
            font-size: 2rem; 
            font-weight: 600; 
            margin-bottom: 16px; 
            display: block;
            font-style: italic;
        }
        .step h3 { font-family: 'Inter', sans-serif; font-size: 1.25rem; margin: 0 0 12px; font-weight: 600; }
        .step p { color: var(--text-muted); font-size: 0.95rem; line-height: 1.6; }
        @media (max-width: 820px) { .steps { grid-template-columns: 1fr; } }

        /* ---------- WHY / FEATURES ---------- */
        .features-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0; border-top: 1px solid var(--border); border-left: 1px solid var(--border); }
        .feature-card { 
            background: var(--bg); 
            border-right: 1px solid var(--border); 
            border-bottom: 1px solid var(--border); 
            padding: 40px;
            position: relative;
            overflow: hidden;
            transition: background 0.3s ease;
        }
        .feature-card:hover { background: var(--surface); }
        .feature-card .icon { width: 32px; height: 32px; border-radius: 50%; background: var(--accent-soft); color: var(--accent); display: flex; align-items: center; justify-content: center; font-weight: 700; margin-bottom: 24px; font-family: 'Fraunces', serif; font-style: italic; }
        .feature-card h3 { font-family: 'Fraunces', serif; font-size: 1.5rem; margin: 0 0 12px; font-weight: 600; }
        .feature-card p { color: var(--text-muted); font-size: 1rem; line-height: 1.6; }
        @media (max-width: 720px) { .features-grid { grid-template-columns: 1fr; } }

        /* ---------- TOOL ---------- */
        .tool-inner { max-width: 760px; margin: 0 auto; }
        .card { 
            background: var(--surface); 
            border: 1px solid var(--border); 
            border-radius: 8px; 
            padding: 40px; 
            box-shadow: 0 20px 40px -20px rgba(0,0,0,0.05);
        }
        .field-label {
            font-family: 'Inter', sans-serif; 
            font-size: 0.8rem; letter-spacing: 0.1em;
            color: var(--text-muted); text-transform: uppercase; display: block; margin-bottom: 12px;
            font-weight: 600;
        }
        textarea#notes-input {
            width: 100%; min-height: 160px; resize: vertical; background: var(--bg);
            border: 1px solid var(--border); border-radius: 4px; color: var(--text);
            font-family: 'Inter', sans-serif; font-size: 1rem; line-height: 1.5; padding: 16px; outline: none;
            transition: border-color 0.2s;
        }
        textarea#notes-input::placeholder { color: #999; }
        textarea#notes-input:focus-visible { border-color: var(--accent); }
        
        .error-text { display: none; color: var(--accent); font-size: 0.9rem; margin-top: 8px; }
        .error-text.visible { display: block; }
        
        button.primary {
            margin-top: 20px; width: 100%; 
        }

        /* Document Output */
        .doc-wrap { display: none; width: 100%; max-width: 760px; margin: 40px auto 0; }
        .doc-wrap.visible { display: block; animation: slideUp 0.5s ease; }
        
        @keyframes slideUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .doc {
            background: var(--surface);
            color: var(--text);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 60px;
            box-shadow: 0 20px 50px -10px rgba(0, 0, 0, 0.1);
            position: relative;
        }
        .doc-letterhead {
            display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px;
            font-family: 'Inter', sans-serif; font-size: 0.75rem; letter-spacing: 0.1em;
            color: var(--text-muted); text-transform: uppercase;
            border-bottom: 2px solid var(--text); padding-bottom: 16px; margin-bottom: 32px;
            font-weight: 600;
        }
        .status-tag { background: var(--accent); color: #fff; border-radius: 4px; padding: 2px 8px; }
        
        .doc h3 { font-family: 'Fraunces', serif; font-size: 1.4rem; margin: 32px 0 8px; font-weight: 600; }
        .doc h3:first-child { margin-top: 0; }
        .doc p { font-family: 'Inter', sans-serif; font-size: 1rem; line-height: 1.7; margin: 0 0 8px; color: var(--paper-ink-soft); }
        
        .copy-link {
            display: block; margin: 24px auto 0; background: var(--bg); border: 1px solid var(--text); color: var(--text);
            font-family: 'Inter', sans-serif; font-size: 0.85rem; letter-spacing: 0.05em;
            text-transform: uppercase; cursor: pointer; padding: 12px 24px; border-radius: 100px; transition: all 0.2s; font-weight: 600;
        }
        .copy-link:hover { background: var(--text); color: var(--bg); }

        /* ---------- FAQ ---------- */
        .faq-list { max-width: 800px; margin: 0 auto; border-top: 1px solid var(--border); }
        .faq-item { border-bottom: 1px solid var(--border); padding: 32px 0; }
        .faq-item summary {
            cursor: pointer; list-style: none; display: flex; align-items: center; justify-content: space-between;
            gap: 16px; font-family: 'Fraunces', serif; font-size: 1.5rem; font-weight: 500;
        }
        .faq-item summary::-webkit-details-marker { display: none; }
        .faq-item summary::after { content: '+'; font-family: 'Inter', sans-serif; color: var(--accent); font-size: 1.5rem; flex-shrink: 0; font-weight: 300; }
        .faq-item[open] summary::after { content: '−'; }
        .faq-item .faq-answer { color: var(--text-muted); font-size: 1.05rem; line-height: 1.7; margin: 16px 0 0; max-width: 700px; }

        /* ---------- FOOTER ---------- */
        .site-footer { padding: 100px 0 60px; background: var(--surface-dark); color: #fff; }
        .site-footer .wrap { display: flex; flex-direction: column; align-items: center; text-align: center; }
        .site-footer .wordmark { color: #fff; margin-bottom: 20px; }
        .site-footer .wordmark .logo-dot { background: var(--accent); }
        .site-footer .foot-tagline { color: rgba(255,255,255,0.7); max-width: 500px; margin: 0 0 30px; font-size: 1.1rem; line-height: 1.6; }
        .site-footer .small { color: rgba(255,255,255,0.4); font-size: 0.85rem; margin-top: 60px; font-family: 'Inter', sans-serif; }

        /* ---------- EMAIL GATE ---------- */
        .gate-overlay {
            display: none; position: fixed; inset: 0; background: rgba(17, 17, 17, 0.6);
            backdrop-filter: blur(8px);
            align-items: center; justify-content: center; padding: 20px; z-index: 100;
        }
        .gate-overlay.visible { display: flex; }
        .gate-card {
            background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
            padding: 48px; max-width: 440px; width: 100%; text-align: center; position: relative;
            box-shadow: 0 20px 50px rgba(0,0,0,0.1);
        }
        .gate-seal {
            width: 56px; height: 56px; background: var(--accent); border-radius: 50%; margin: 0 auto 24px;
            display: flex; align-items: center; justify-content: center;
            font-family: 'Fraunces', serif; color: #fff; font-size: 1.2rem; font-weight: 700; font-style: italic;
        }
        .gate-card h2 { font-family: 'Fraunces', serif; font-size: 2rem; margin: 0 0 12px; font-weight: 600; }
        .gate-card .gate-copy { color: var(--text-muted); font-size: 1rem; margin: 0 0 24px; line-height: 1.5; }
        input#gate-email {
            width: 100%; background: var(--bg); border: 1px solid var(--border); border-radius: 4px;
            color: var(--text); font-family: 'Inter', sans-serif; font-size: 1rem;
            padding: 14px 16px; outline: none; margin-bottom: 12px; transition: border-color 0.2s;
        }
        input#gate-email::placeholder { color: #999; }
        input#gate-email:focus-visible { border-color: var(--accent); }
        .gate-close {
            position: absolute; top: 16px; right: 16px; background: none; border: none;
            color: var(--text-muted); font-size: 1.5rem; cursor: pointer; line-height: 1;
        }

        @media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
        @media (max-width: 880px) {
            .hero .wrap { grid-template-columns: 1fr; gap: 40px; }
            .hero-visual { display: none; }
            .doc { padding: 32px 24px; }
            .card { padding: 24px; }
            .gate-card { padding: 32px 24px; }
>>>>>>> parent of 2d9d4ca (Best version)
        }
    </style>
</head>
<body>
<<<<<<< HEAD
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
=======
    <nav class="topnav">
        <div class="wrap">
            <div class="wordmark">
                <div class="logo-dot"></div>
                Client<span>Brief</span>
            </div>
            <ul class="nav-links">
                <li><a href="#how">Process</a></li>
                <li><a href="#why">The Edge</a></li>
                <li><a href="#faq">FAQ</a></li>
            </ul>
            <a href="#tool" class="btn-small">Draft a Brief</a>
        </div>
    </nav>

    <header class="hero">
        <div class="wrap">
            <div class="hero-copy">
                <p class="eyebrow">The Strategist's Edge</p>
                <h1>Turn Client <span class="highlight">Chaos</span> into Creative Strategy.</h1>
                <p class="lede">Stop wrangling messy notes into formatting. Paste the rambling email, and get back a comprehensive, strategically sound brief complete with KPIs, timelines, and inferred insights. It's like having a Senior Strategist on call.</p>
                <div class="hero-ctas">
                    <a href="#tool" class="btn-primary-lg">Draft a Brief — Free</a>
                    <a href="#why" class="link-muted">See the strategic edge</a>
                </div>
            </div>
            
            <div class="hero-visual">
                <div class="visual-header">
                    <span>BRIEF_001.PROOF</span>
                    <span class="visual-tag">DRAFT</span>
                </div>
                <div class="visual-line med"></div>
                <div class="visual-line short"></div>
                <div class="visual-line"></div>
                <div class="visual-line med"></div>
                <div class="visual-line accent"></div>
                <div class="visual-line short"></div>
            </div>
>>>>>>> parent of 2d9d4ca (Best version)
        </div>

<<<<<<< HEAD
        <div class="doc-wrap" id="result-wrap">
            <div class="doc">
                <div class="letterhead">
                    <span id="doc-ref">REF: CB-0000</span>
                    <span id="doc-date">DATE: --</span>
                    <span class="status">STATUS: DRAFT</span>
                </div>
                <div id="result-body"></div>
=======
    <section class="section" id="how">
        <div class="wrap">
            <div class="section-intro">
                <h2>From brain-dump to <em>boardroom-ready.</em></h2>
                <p>Three steps to a brief that actually moves the project forward.</p>
            </div>
            <div class="steps">
                <div class="step">
                    <span class="step-no">01</span>
                    <h3>Paste the Chaos</h3>
                    <p>An email thread, a rushed Slack message, or a messy call transcript. However it arrived, just paste it in.</p>
                </div>
                <div class="step">
                    <span class="step-no">02</span>
                    <h3>AI Fills the Gaps</h3>
                    <p>The engine generates a 7-section brief, logically inferring target audience, suggesting KPIs, and projecting a timeline.</p>
                </div>
                <div class="step">
                    <span class="step-no">03</span>
                    <h3>Send with Confidence</h3>
                    <p>Copy the pristine, professionally formatted document straight into your proposal, deck, or project management tool.</p>
                </div>
>>>>>>> parent of 2d9d4ca (Best version)
            </div>
            <button class="copy-btn" id="copy-btn" type="button">Copy brief</button>
        </div>
<<<<<<< HEAD
    </div>
=======
    </section>

    <section class="section" id="why" style="background: var(--surface);">
        <div class="wrap">
            <div class="section-intro">
                <h2>The Factor That Makes <em>You Prefer It.</em></h2>
                <p>Anyone can format text. We strategize it.</p>
            </div>
            <div class="features-grid">
                <div class="feature-card">
                    <div class="icon">A</div>
                    <h3>Strategic Assumptions</h3>
                    <p>Clients never give you everything. Our AI explicitly lists the strategic gaps it filled, so you know exactly what to validate before the kickoff.</p>
                </div>
                <div class="feature-card">
                    <div class="icon">B</div>
                    <h3>Projected KPIs & Metrics</h3>
                    <p>A brief isn't a brief without success metrics. The tool automatically suggests relevant KPIs based on the inferred business goals.</p>
                </div>
                <div class="feature-card">
                    <div class="icon">C</div>
                    <h3>Suggested Timelines</h3>
                    <p>Stop guessing how long things will take. The AI drafts a logical, phased timeline based on the scope of work requested.</p>
                </div>
                <div class="feature-card">
                    <div class="icon">D</div>
                    <h3>Elite Agency Tone</h3>
                    <p>Reads like it was written by a Senior Account Director. Confident, formal, and completely free of chatbot clichés.</p>
                </div>
            </div>
        </div>
    </section>

    <section class="section tool" id="tool">
        <div class="wrap">
            <div class="section-intro">
                <p class="eyebrow">The Generator</p>
                <h2>Give this one a <em>job number.</em></h2>
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
                <h2>Questions, <em>answered.</em></h2>
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
                Client<span>Brief</span>
            </div>
            <p class="foot-tagline">Stop formatting text. Start delivering strategy. Built for agencies who value billable hours over busywork.</p>
            <a href="#tool" class="btn-primary-lg">Draft a Brief — Free</a>
            <p class="small">© 2026 ClientBrief AI. All rights reserved.</p>
        </div>
    </footer>
>>>>>>> parent of 2d9d4ca (Best version)

    <div class="gate-overlay" id="email-gate">
        <div class="gate-card">
            <button class="gate-close" id="gate-close" type="button" aria-label="Close">×</button>
            <div class="gate-seal">CB</div>
<<<<<<< HEAD
            <h2>Unlock the brief</h2>
            <p>Enter your work email to generate your first structured brief.</p>
            <input type="email" class="gate-input" id="gate-email" placeholder="you@agency.com">
            <div class="error-text" id="gate-error" style="margin-bottom: 16px;"></div>
            <button class="btn-primary" id="gate-submit" type="button">
                <span class="spinner"></span>
                <span class="btn-text">Unlock the Brief</span>
            </button>
=======
            <h2>Unlock the Strategy</h2>
            <p class="gate-copy">Drop your email to generate your first strategic brief. No spam—just smarter workflows.</p>
            <input type="email" id="gate-email" placeholder="you@agency.com" aria-label="Email address">
            <div class="error-text" id="gate-error"></div>
            <button class="btn-primary-lg" id="gate-submit" type="button" style="width: 100%;">Get My Brief</button>
>>>>>>> parent of 2d9d4ca (Best version)
        </div>
    </div>

    <script>
        const EMAIL_KEY = 'clientbrief_email';
        let pendingNotes = null;

<<<<<<< HEAD
        // --- Utility Functions ---
        function getSavedEmail() {
            try { return localStorage.getItem(EMAIL_KEY); } catch (e) { return null; }
        }
=======
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
>>>>>>> parent of 2d9d4ca (Best version)

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
<<<<<<< HEAD

            // Show the document
            document.getElementById('result-wrap').classList.add('visible');
            document.getElementById('result-wrap').scrollIntoView({ behavior: 'smooth', block: 'start' });
=======
            document.getElementById('doc-ref').textContent =
                'JOB NO. ' + Math.floor(1000 + Math.random() * 9000);
            document.getElementById('doc-date').textContent =
                'DATE: ' + new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).toUpperCase();
>>>>>>> parent of 2d9d4ca (Best version)
        }

        // --- API Call Logic ---
        async function draftBrief(notes, email) {
<<<<<<< HEAD
            const draftBtn = document.getElementById('draft-btn');
            const errorEl = document.getElementById('notes-error');
            
            setLoadingState(draftBtn, true, 'Drafting...', 'Draft the Brief');
            errorEl.classList.remove('visible');
=======
            const resultWrap = document.getElementById('result-wrap');
            const btn = document.getElementById('draft-btn');
            btn.disabled = true;
            btn.textContent = 'Strategizing...';
            resultWrap.classList.remove('visible');
>>>>>>> parent of 2d9d4ca (Best version)

            try {
                let url = '/generate-brief?notes=' + encodeURIComponent(notes);
                if (email) {
                    url += '&email=' + encodeURIComponent(email);
                }

                const response = await fetch(url);
                const data = await response.json();
<<<<<<< HEAD

                if (!response.ok) {
                    throw new Error(data.error || 'Something went wrong drafting your brief.');
                }

=======
                if (!response.ok) {
                    throw new Error(data.error || 'Something went wrong drafting your brief.');
                }
>>>>>>> parent of 2d9d4ca (Best version)
                renderBrief(data.plan || '');
                resultWrap.classList.add('visible');
                resultWrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
            } catch (e) {
<<<<<<< HEAD
                errorEl.textContent = e.message || 'Something went wrong. Please try again.';
                errorEl.classList.add('visible');
            } finally {
                setLoadingState(draftBtn, false, '', 'Draft the Brief');
=======
                renderBrief(e.message || 'Something went wrong drafting your brief. Try again in a moment.');
                resultWrap.classList.add('visible');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Generate Strategic Brief';
>>>>>>> parent of 2d9d4ca (Best version)
            }
        }

        // --- Event Listeners ---
        
        // Draft Button Click
        document.getElementById('draft-btn').addEventListener('click', function() {
            const notes = document.getElementById('notes-input').value.trim();
            const errorEl = document.getElementById('notes-error');

            if (!notes) {
<<<<<<< HEAD
                errorEl.textContent = 'Please paste some client notes first.';
=======
                errorEl.textContent = 'Paste some client notes first — even the messy stuff works.';
>>>>>>> parent of 2d9d4ca (Best version)
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
<<<<<<< HEAD
                gateError.textContent = "That doesn't look like a valid email address.";
=======
                gateError.textContent = "That doesn't look like a valid email — try again.";
>>>>>>> parent of 2d9d4ca (Best version)
                gateError.classList.add('visible');
                return;
            }
            gateError.classList.remove('visible');
<<<<<<< HEAD

=======
>>>>>>> parent of 2d9d4ca (Best version)
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
<<<<<<< HEAD

        // Gate Enter Key
        document.getElementById('gate-email').addEventListener('keyup', function(e) {
            if (e.key === 'Enter') {
                document.getElementById('gate-submit').click();
            }
        });

        // Cmd/Ctrl + Enter in textarea
        document.getElementById('notes-input').addEventListener('keydown', function(e) {
=======
        document.getElementById('notes-input').addEventListener('keydown', function (e) {
>>>>>>> parent of 2d9d4ca (Best version)
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
<<<<<<< HEAD
                const originalText = btn.textContent;
                btn.textContent = 'Copied!';
                setTimeout(() => {
                    btn.textContent = originalText;
                }, 2000);
            } catch (e) {
                alert('Could not copy automatically. Please select the text and copy manually.');
=======
                const original = btn.textContent;
                btn.textContent = 'Copied! Paste it anywhere.';
                setTimeout(function () { btn.textContent = original; }, 2000);
            } catch (e) {
                alert('Could not copy automatically — select the text and copy manually.');
>>>>>>> parent of 2d9d4ca (Best version)
            }
        });
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)