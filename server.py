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
    <title>ClientBrief AI — Project briefs for marketing &amp; creative agencies</title>
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
        .hero p {
            color: var(--muted-on-dark);
            font-size: 1.1rem;
            margin-bottom: 32px;
        }
        .input-group {
            display: flex;
            flex-direction: column;
            gap: 16px;
            background: var(--bg-soft);
            padding: 24px;
            border-radius: 16px;
            border: 1px solid var(--line);
        }
        .input-group input, .input-group textarea {
            width: 100%;
            padding: 12px;
            border-radius: 8px;
            border: 1px solid var(--line-light);
            background: var(--surface-2);
            color: var(--ink);
            font-family: inherit;
            font-size: 1rem;
        }
        .input-group button {
            background: var(--accent);
            color: white;
            border: none;
            padding: 14px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }
        .input-group button:hover { background: #d14c3d; }
        #output {
            margin-top: 24px;
            white-space: pre-wrap;
            background: var(--bg-soft);
            padding: 24px;
            border-radius: 16px;
            border: 1px solid var(--line);
            display: none;
        }
    </style>
</head>
<body>
    <header class="site-bar">
        <div class="wrap">
            <a href="/" class="logo">ClientBrief <span>AI</span></a>
            <nav>
                <a href="#how-it-works">How it works</a>
                <a href="#pricing">Pricing</a>
            </nav>
            <a href="#generator" class="nav-cta">Try it free</a>
        </div>
    </header>

    <section class="hero" id="generator">
        <div class="wrap">
            <div class="eyebrow">For Account & Project Leads</div>
            <h1>Turn messy client intake into a send-ready project brief.</h1>
            <p>Paste your rough notes below. We'll structure them into a professional agency brief instantly.</p>
            
            <div class="input-group">
                <input type="email" id="email" placeholder="Your work email (required)">
                <textarea id="notes" rows="5" placeholder="e.g., Client wants a new shopify store, sell skateboards, target gen z, need it by christmas, budget is tight..."></textarea>
                <button onclick="generateBrief()">Generate Brief</button>
            </div>
            
            <div id="output"></div>
        </div>
    </section>

    <script>
        async function generateBrief() {
            const notes = document.getElementById('notes').value;
            const email = document.getElementById('email').value;
            const outputDiv = document.getElementById('output');
            
            if (!notes || !email) {
                alert("Please enter both your email and client notes.");
                return;
            }

            outputDiv.style.display = 'block';
            outputDiv.textContent = "Generating brief...";

            try {
                const response = await fetch(`/generate-brief?notes=${encodeURIComponent(notes)}&email=${encodeURIComponent(email)}`);
                const data = await response.json();
                
                if (data.error) {
                    outputDiv.textContent = "Error: " + data.error;
                } else {
                    outputDiv.textContent = data.plan;
                }
            } catch (err) {
                outputDiv.textContent = "Failed to connect to the server.";
            }
        }
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)