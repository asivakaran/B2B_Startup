import os
import re
import requests
import dns.resolver
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

# Block free email providers and known disposable email domains
BLOCKED_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "live.com", 
    "aol.com", "icloud.com", "protonmail.com", "zoho.com", "msn.com",
    "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com",
    "yopmail.com", "trashmail.com", "getnada.com"
}

def validate_work_email(email: str) -> tuple[bool, str]:
    """Validates format, blocks free providers, and checks MX records."""
    if not email:
        return False, "Email is required."
    
    candidate = email.strip().lower()
    if not _EMAIL_RE.fullmatch(candidate):
        return False, "Invalid email format."
    
    domain = candidate.split("@")[1]
    
    if domain in BLOCKED_DOMAINS:
        return False, "Please use your work email. Free providers (Gmail, Yahoo, etc.) are not accepted."
    
    # Check if the domain actually exists and can receive mail (MX Record)
    try:
        dns.resolver.resolve(domain, 'MX')
        return True, "Valid"
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
        return False, "This email domain does not exist. Please provide a valid work email."
    except Exception:
        # If DNS server fails temporarily, we let it pass to not block real users
        return True, "Valid"


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
    email: str = Query(..., description="Work email captured by the frontend"),
):
    if not GROQ_API_KEY:
        return JSONResponse(status_code=500, content={"error": "GROQ_API_KEY not set in environment."})

    # 1. Validate the email strictly
    is_valid, error_msg = validate_work_email(email)
    if not is_valid:
        return JSONResponse(status_code=400, content={"error": error_msg})

    # 2. Call AI
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

    # 3. Save to Database
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
            min-height: 100vh;
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

        .hero { padding: 80px 0 72px; }
        .hero-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 64px;
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
            margin-bottom: 20px;
        }
        .eyebrow::before {
            content: '';
            width: 24px;
            height: 1px;
            background: var(--accent);
        }
        .hero h1 {
            font-family: 'Instrument Serif', Georgia, serif;
            font-size: clamp(2.4rem, 5vw, 3.6rem);
            line-height: 1.05;
            font-weight: 400;
            margin-bottom: 20px;
            letter-spacing: -0.02em;
        }
        .hero h1 em { color: var(--accent); font-style: italic; }
        .hero p {
            color: var(--muted-on-dark);
            font-size: 1.1rem;
            margin-bottom: 32px;
            max-width: 480px;
        }

        .input-card {
            background: var(--bg-soft);
            padding: 28px;
            border-radius: 16px;
            border: 1px solid var(--line);
            box-shadow: 0 20px 50px rgba(0,0,0,0.3);
        }
        .input-group {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        .input-group label {
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--ink-on-dark);
            margin-bottom: -8px;
        }
        .input-group input, .input-group textarea {
            width: 100%;
            padding: 14px;
            border-radius: 8px;
            border: 1px solid var(--line-light);
            background: var(--surface-2);
            color: var(--ink);
            font-family: inherit;
            font-size: 1rem;
            transition: border-color 0.2s;
        }
        .input-group input:focus, .input-group textarea:focus {
            outline: none;
            border-color: var(--accent);
        }
        .input-group textarea {
            min-height: 140px;
            resize: vertical;
        }
        .generate-btn {
            background: var(--accent);
            color: white;
            border: none;
            padding: 16px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 1rem;
            cursor: pointer;
            transition: background 0.2s, transform 0.1s;
            margin-top: 8px;
        }
        .generate-btn:hover { background: #d14c3d; }
        .generate-btn:active { transform: scale(0.98); }
        .generate-btn:disabled { background: #555; cursor: not-allowed; }

        .output-container {
            margin-top: 48px;
            display: none;
        }
        .output-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }
        .output-header h3 {
            font-family: 'Instrument Serif', serif;
            font-size: 1.5rem;
            font-weight: 400;
        }
        .copy-btn {
            background: transparent;
            border: 1px solid var(--line);
            color: var(--muted-on-dark);
            padding: 8px 16px;
            border-radius: 999px;
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        .copy-btn:hover {
            border-color: var(--accent);
            color: var(--accent);
        }
        #output {
            white-space: pre-wrap;
            background: var(--bg-soft);
            padding: 32px;
            border-radius: 16px;
            border: 1px solid var(--line);
            font-family: 'DM Sans', sans-serif;
            line-height: 1.7;
            color: var(--ink-on-dark);
        }
        #errorBox {
            display: none;
            background: rgba(232, 93, 76, 0.1);
            border: 1px solid var(--error);
            color: var(--error);
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 16px;
            font-size: 0.9rem;
        }
        
        .loading-spinner {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: #fff;
            animation: spin 1s ease-in-out infinite;
            margin-right: 8px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        footer {
            border-top: 1px solid var(--line);
            margin-top: 80px;
            padding: 32px 0;
            text-align: center;
            color: var(--muted-on-dark);
            font-size: 0.85rem;
        }

        @media (max-width: 768px) {
            .hero-grid { grid-template-columns: 1fr; gap: 32px; }
            .site-bar nav { display: none; }
        }
    </style>
</head>
<body>
    <header class="site-bar">
        <div class="wrap">
            <a href="/" class="logo">ClientBrief <span>AI</span></a>
            <nav>
                <a href="#how-it-works">How it works</a>
                <a href="#generator">Try it</a>
            </nav>
            <a href="#generator" class="nav-cta">Generate Brief</a>
        </div>
    </header>

    <section class="hero" id="generator">
        <div class="wrap">
            <div class="hero-grid">
                <div>
                    <div class="eyebrow">For Agency Account Leads</div>
                    <h1>Turn messy client intake into a <em>send-ready</em> project brief.</h1>
                    <p>Paste your rough notes from the discovery call. We'll structure them into a professional, 7-point agency brief instantly. No more scope creep from misaligned notes.</p>
                </div>
                
                <div class="input-card">
                    <div id="errorBox"></div>
                    <div class="input-group">
                        <label for="email">Work Email (No Gmail/Yahoo)</label>
                        <input type="email" id="email" placeholder="you@agency.com">
                        
                        <label for="notes">Client Discovery Notes</label>
                        <textarea id="notes" placeholder="e.g., Client wants a new Shopify store. Sell skateboards. Target gen-z. Needs to be done by christmas. Budget is around 10k. They liked the typography on Thrasher's site."></textarea>
                        
                        <button class="generate-btn" id="generateBtn" onclick="generateBrief()">Generate Brief</button>
                    </div>
                </div>
            </div>

            <div class="output-container" id="outputContainer">
                <div class="output-header">
                    <h3>Generated Project Brief</h3>
                    <button class="copy-btn" onclick="copyOutput()">Copy Text</button>
                </div>
                <div id="output"></div>
            </div>
        </div>
    </section>

    <footer>
        <div class="wrap">
            Built with FastAPI, Supabase, and Groq AI.
        </div>
    </footer>

    <script>
        async function generateBrief() {
            const notes = document.getElementById('notes').value;
            const email = document.getElementById('email').value;
            const outputDiv = document.getElementById('output');
            const outputContainer = document.getElementById('outputContainer');
            const errorBox = document.getElementById('errorBox');
            const btn = document.getElementById('generateBtn');
            
            errorBox.style.display = 'none';
            errorBox.textContent = '';

            if (!notes || !email) {
                errorBox.textContent = "Please enter both your email and client notes.";
                errorBox.style.display = 'block';
                return;
            }

            btn.disabled = true;
            btn.innerHTML = '<span class="loading-spinner"></span> Generating...';
            outputContainer.style.display = 'block';
            outputDiv.textContent = "Analyzing notes and structuring brief...";

            try {
                const response = await fetch(`/generate-brief?notes=${encodeURIComponent(notes)}&email=${encodeURIComponent(email)}`);
                const data = await response.json();
                
                if (data.error) {
                    outputContainer.style.display = 'none';
                    errorBox.textContent = data.error;
                    errorBox.style.display = 'block';
                } else {
                    outputDiv.textContent = data.plan;
                }
            } catch (err) {
                outputDiv.textContent = "Failed to connect to the server. Please try again.";
            } finally {
                btn.disabled = false;
                btn.innerHTML = 'Generate Brief';
            }
        }

        function copyOutput() {
            const text = document.getElementById('output').innerText;
            navigator.clipboard.writeText(text).then(() => {
                const btn = document.querySelector('.copy-btn');
                btn.innerText = 'Copied!';
                setTimeout(() => { btn.innerText = 'Copy Text'; }, 2000);
            });
        }
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)