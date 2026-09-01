import os
import re
import secrets
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from supabase import create_client, Client

load_dotenv()

# --- GEMINI AI SETUP ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# -----------------------

# --- SUPABASE SETUP ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# ----------------------

app = FastAPI(title="BriefStudio")

_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)

BLOCKED_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "10minutemail.com", 
    "tempmail.com", "yopmail.com", "trashmail.com", "getnada.com",
    "temp-mail.org", "sharklasers.com", "guerrillamailblock.com"
}

def validate_work_email(email: str) -> tuple[bool, str]:
    if not email:
        return False, "Email is required."
    candidate = email.strip().lower()
    if not _EMAIL_RE.fullmatch(candidate):
        return False, "Please enter a valid email format."
    domain = candidate.split("@")[1]
    if domain in BLOCKED_DOMAINS:
        return False, "Please use a real email. Temporary/disposable emails are not accepted."
    return True, "Valid"


def call_ai(system_msg: str, user_msg: str, max_tokens: int = 800) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "system_instruction": {"parts": [{"text": system_msg}]},
        "contents": [{"parts": [{"text": user_msg}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7}
    }
    response = requests.post(url, json=payload, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"Gemini API error ({response.status_code}): {response.text}")
    data = response.json()
    return (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
        .strip()
    )


# ============================================================================
# Generate brief (now returns brief_id for the sign-off workflow)
# ============================================================================

@app.get("/generate-brief")
def generate_brief(
    notes: str = Query(...),
    email: str = Query(...),
):
    if not GEMINI_API_KEY:
        return JSONResponse(status_code=500, content={"error": "GEMINI_API_KEY not set."})

    is_valid, error_msg = validate_work_email(email)
    if not is_valid:
        return JSONResponse(status_code=400, content={"error": error_msg})

    try:
        plan = call_ai(
            system_msg=(
                "You are an overworked Senior Account Director. You write directly and practically, with zero corporate fluff. "
                "You never use buzzwords like 'seamless', 'synergy', 'delve', or 'tapestry'. "
                "Take the rough client notes and write a structured project brief covering: "
                "Project Overview, Business Goals, Target Audience, Scope of Work, Deliverables, Assumptions & Open Questions, and Suggested Timeline.\n\n"
                "CRITICAL INSTRUCTION 1: ABSOLUTELY NO HALLUCINATIONS. Do NOT guess, invent, or inject any missing facts, dates, years, or audiences. If information is missing, you MUST write 'Not specified in notes' or make a logical assumption but explicitly FLAG IT as an assumption. Do not invent facts.\n"
                "CRITICAL INSTRUCTION 2: In the 'Assumptions & Open Questions' section, generate 3 hyper-specific questions that address scope-killers. You MUST include a question about the number of initial concepts provided and the number of revision rounds included. Do not ask shallow questions like 'what is the launch date?'.\n"
                "CRITICAL FORMATTING: Use plain text ONLY. NO markdown stars (** or *). Use simple plain-text headings followed by a colon."
            ),
            user_msg=(
                f"Turn the following rough client notes into this structured brief:\n"
                f"Client notes: {notes}\n"
            ),
            max_tokens=2500,
        )
    except RuntimeError as e:
        return JSONResponse(status_code=502, content={"error": str(e)})

    brief_id = secrets.token_hex(16)

    try:
        supabase.table("b2b_briefs").insert({
            "notes": notes, "brief": plan, "email": email.strip().lower(),
            "brief_id": brief_id, "status": "draft"
        }).execute()
    except Exception as e:
        print(f"Database Error: {e}")

    return {"plan": plan, "brief_id": brief_id}


# ============================================================================
# Create sign-off link
# ============================================================================

class SignOffRequest(BaseModel):
    brief_id: str
    agency_email: str
    brief_text: str
    client_label: str = ""

@app.post("/create-signoff")
async def create_signoff(request: SignOffRequest):
    token = secrets.token_urlsafe(32)
    try:
        result = supabase.table("b2b_briefs").update({
            "sign_off_token": token, "status": "sent", "client_label": request.client_label
        }).eq("brief_id", request.brief_id).eq("email", request.agency_email.strip().lower()).execute()
        if not result.data:
            supabase.table("b2b_briefs").insert({
                "brief_id": request.brief_id, "email": request.agency_email.strip().lower(),
                "brief": request.brief_text, "sign_off_token": token,
                "status": "sent", "client_label": request.client_label
            }).execute()
    except Exception as e:
        print(f"Sign-off creation error: {e}")
        return JSONResponse(status_code=500, content={"error": "Could not create sign-off link."})
    return {"token": token, "sign_off_url": f"/b/{token}"}


# ============================================================================
# Record sign-off
# ============================================================================

class SignRequest(BaseModel):
    token: str
    signed_by: str

@app.post("/api/sign")
async def sign_brief(request: SignRequest):
    if not request.signed_by or len(request.signed_by.strip()) < 2:
        return JSONResponse(status_code=400, content={"error": "Please provide your full name."})
    now = datetime.now(timezone.utc)
    try:
        result = supabase.table("b2b_briefs").update({
            "status": "signed", "signed_by": request.signed_by.strip(), "signed_at": now.isoformat()
        }).eq("sign_off_token", request.token).execute()
        if not result.data:
            return JSONResponse(status_code=404, content={"error": "Brief not found."})
        return {"success": True, "signed_at": now.isoformat()}
    except Exception as e:
        print(f"Sign error: {e}")
        return JSONResponse(status_code=500, content={"error": "Could not record sign-off."})


# ============================================================================
# Scope check (new request vs signed brief)
# ============================================================================

class ScopeCheckRequest(BaseModel):
    brief_text: str
    new_request: str

@app.post("/api/check-scope")
async def check_scope(request: ScopeCheckRequest):
    if not request.brief_text or not request.new_request:
        return JSONResponse(status_code=400, content={"error": "Both the signed brief and the new request are required."})
    try:
        analysis = call_ai(
            system_msg=(
                "You are a project scope auditor for a creative/marketing agency. "
                "You compare a SIGNED project brief against a NEW request from the client. "
                "Your job is to flag exactly what in the new request falls OUTSIDE the signed scope.\n\n"
                "RULES:\n"
                "1. Be specific. Reference exact items from both documents.\n"
                "2. If something is clearly new (not mentioned in the signed brief), flag it as NEW SCOPE.\n"
                "3. If something is an extension of existing scope (e.g., more revisions than stated), flag it as SCOPE EXTENSION.\n"
                "4. If it's ambiguous, flag it as UNCLEAR — REQUIRES CLARIFICATION.\n"
                "5. Do NOT flag things that are clearly within the signed scope.\n"
                "6. End with a suggested next action (e.g., 'Issue change order for X' or 'Clarify with client before proceeding').\n\n"
                "FORMAT:\n"
                "VERDICT: [WITHIN SCOPE / NEW SCOPE DETECTED / UNCLEAR]\n\n"
                "If new scope detected, list each item:\n"
                "1. [Item]: [Why it's outside scope]\n\n"
                "SUGGESTED ACTION: [What the agency should do]\n\n"
                "Use plain text only. No markdown formatting."
            ),
            user_msg=(
                f"SIGNED BRIEF (the agreed scope):\n{request.brief_text}\n\n"
                f"NEW CLIENT REQUEST (what they're now asking for):\n{request.new_request}\n\n"
                f"Compare and flag anything outside the signed scope."
            ),
            max_tokens=1200
        )
        return {"analysis": analysis}
    except RuntimeError as e:
        return JSONResponse(status_code=502, content={"error": str(e)})


# ============================================================================
# Support endpoint: list briefs by email. NOTE: email-keyed, no auth.
# Fine for hand-held onboarding of your first 10 customers. Auth-gate
# before you scale past that.
# ============================================================================

@app.get("/api/my-briefs")
def get_my_briefs(email: str = Query(...)):
    is_valid, error_msg = validate_work_email(email)
    if not is_valid:
        return JSONResponse(status_code=400, content={"error": error_msg})
    try:
        result = supabase.table("b2b_briefs").select(
            "brief_id, status, signed_by, signed_at, client_label, sign_off_token, created_at"
        ).eq("email", email.strip().lower()).order("created_at", desc=True).limit(20).execute()
        return {"briefs": result.data}
    except Exception as e:
        print(f"My briefs error: {e}")
        return JSONResponse(status_code=500, content={"error": "Could not retrieve briefs."})


# ============================================================================
# Client-facing sign-off page (matches brand styling)
# ============================================================================

_CLIENT_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Project Brief — Sign-Off</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'DM Sans', system-ui, sans-serif; background: #FFFCF7; color: #0F1419; line-height: 1.6; }
        .container { max-width: 680px; margin: 0 auto; padding: 40px 24px; }
        .topbar { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #D4CEC4; padding-bottom: 16px; margin-bottom: 8px; }
        .logo { font-family: 'Instrument Serif', Georgia, serif; font-size: 1.3rem; }
        .logo span { color: #E85D4C; font-style: italic; }
        .status { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; padding: 4px 10px; border-radius: 4px; font-weight: 700; }
        .status.sent { background: #FEF3C7; color: #92400E; }
        .status.signed { background: #D1FAE5; color: #065F46; }
        .client-line { font-size: 0.85rem; color: #6B7280; padding: 16px 0 8px; }
        .brief-content { background: #F4F0E8; border: 1px solid #D4CEC4; border-radius: 12px; padding: 32px; margin-top: 8px; }
        .brief-content h3 { font-family: 'Instrument Serif', Georgia, serif; font-size: 1.08rem; margin: 20px 0 8px; color: #0F1419; }
        .brief-content h3:first-child { margin-top: 0; }
        .brief-content p { font-size: 0.94rem; color: #374151; margin-bottom: 8px; }
        .signbox { background: #F4F0E8; border: 1px solid #D4CEC4; border-radius: 12px; padding: 24px; margin: 24px 0; }
        .signbox h2 { font-family: 'Instrument Serif', Georgia, serif; font-size: 1.3rem; color: #0F1419; margin-bottom: 8px; font-weight: 400; }
        .signbox .sub { color: #6B7280; font-size: 0.9rem; margin-bottom: 16px; }
        .signbox input { width: 100%; padding: 12px 14px; border: 1px solid #D4CEC4; border-radius: 8px; font: inherit; margin-bottom: 8px; background: #fff; color: #0F1419; }
        .signbox input:focus { outline: 2px solid rgba(232, 93, 76, 0.35); border-color: #E85D4C; }
        .err { color: #E85D4C; font-size: 0.85rem; min-height: 1.2em; margin-bottom: 8px; }
        .signbox button { width: 100%; background: #0F1419; color: #F4F0E8; border: none; padding: 14px; font: inherit; font-weight: 700; cursor: pointer; border-radius: 8px; font-size: 0.95rem; }
        .signbox button:hover { background: #E85D4C; }
        .signbox button:disabled { opacity: 0.6; cursor: wait; }
        .signedbox { background: #D1FAE5; border: 1px solid #6EE7B7; border-radius: 12px; padding: 24px; margin: 24px 0; text-align: center; }
        .signedbox .mark { font-size: 1.8rem; margin-bottom: 4px; }
        .signedbox h2 { color: #065F46; font-size: 1.15rem; margin-bottom: 6px; }
        .signedbox p { color: #047857; font-size: 0.9rem; }
        .signedbox .fine { color: #6B7280; font-size: 0.78rem; margin-top: 12px; }
        .foot { text-align: center; font-size: 0.75rem; color: #9CA3AF; margin-top: 40px; padding-top: 24px; border-top: 1px solid #E5E7EB; line-height: 1.7; }
    </style>
</head>
<body>
    <div class="container">
        <div class="topbar">
            <div class="logo">Brief<span>Studio</span></div>
            <div class="status __STATUS_CLASS__">__STATUS_TEXT__</div>
        </div>
        <div class="client-line">__CLIENT_LINE__</div>
        <div class="brief-content">
"""

_CLIENT_TAIL = """
        </div>
        <div class="foot">Sent via BriefStudio — scope-creep prevention for agencies.<br>This timestamped record documents the agreed scope for both parties.</div>
    </div>
</body>
</html>
"""

_CLIENT_SIGN_JS = """
        <div class="signbox">
            <h2>Approve this scope</h2>
            <p class="sub">By approving, you confirm the scope above is what was agreed. Any changes to this scope will be documented separately.</p>
            <input type="text" id="signer-name" placeholder="Type your full name" autocomplete="name">
            <div class="err" id="sign-error"></div>
            <button id="approve-btn" type="button">I approve this scope</button>
        </div>
        <script>
            document.getElementById('approve-btn').addEventListener('click', async function () {
                var name = document.getElementById('signer-name').value.trim();
                var errEl = document.getElementById('sign-error');
                if (!name || name.length < 2) { errEl.textContent = 'Please enter your full name.'; return; }
                errEl.textContent = '';
                this.disabled = true; this.textContent = 'Recording approval…';
                try {
                    var parts = window.location.pathname.split('/');
                    var response = await fetch('/api/sign', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ token: parts[parts.length - 1], signed_by: name })
                    });
                    if (response.ok) { window.location.reload(); }
                    else {
                        var data = await response.json();
                        errEl.textContent = data.error || 'Something went wrong.';
                        this.disabled = false; this.textContent = 'I approve this scope';
                    }
                } catch (e) {
                    errEl.textContent = 'Network error. Please try again.';
                    this.disabled = false; this.textContent = 'I approve this scope';
                }
            });
        </script>
"""

_NOT_FOUND_PAGE = """<!DOCTYPE html>
<html>
<head><title>Brief Not Found</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
<style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:'DM Sans',system-ui,sans-serif;background:#0F1419;color:#F4F0E8;display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center;padding:40px}h1{font-family:'Instrument Serif',serif;font-size:1.6rem;font-weight:400;margin-bottom:12px}p{color:#9CA3AF;font-size:0.95rem}</style>
</head>
<body><div><h1>Link not found</h1><p>This sign-off link is invalid or has expired. Please contact your agency.</p></div></body>
</html>
"""


@app.get("/b/{token}", response_class=HTMLResponse)
async def client_brief(token: str):
    brief_data = None
    try:
        result = supabase.table("b2b_briefs").select("*").eq("sign_off_token", token).limit(1).execute()
        if result.data:
            brief_data = result.data[0]
    except Exception as e:
        print(f"Lookup error: {e}")

    if not brief_data:
        return HTMLResponse(content=_NOT_FOUND_PAGE, status_code=404)

    brief_text = brief_data.get("brief", "") or ""
    status = brief_data.get("status", "sent")
    signed_by = brief_data.get("signed_by", "") or ""
    signed_at = brief_data.get("signed_at", "") or ""
    client_label = brief_data.get("client_label", "") or ""

    # Build brief body
    body_parts = []
    for line in brief_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        clean = line.replace("**", "").replace("*", "")
        if clean.endswith(":") and len(clean) < 80:
            body_parts.append(f"<h3>{clean}</h3>")
        else:
            body_parts.append(f"<p>{clean}</p>")
    brief_html = "".join(body_parts)

    if status == "signed":
        try:
            dt = datetime.fromisoformat(str(signed_at).replace("Z", "+00:00"))
            when = dt.strftime("%B %d, %Y at %I:%M %p UTC")
        except Exception:
            when = str(signed_at)
        sign_section = f"""
        <div class="signedbox">
            <div class="mark">&#10003;</div>
            <h2>Scope approved</h2>
            <p>Signed by <strong>{signed_by}</strong></p>
            <p>{when}</p>
            <p class="fine">This timestamped record is stored as evidence of the agreed scope.</p>
        </div>
        """
    else:
        sign_section = _CLIENT_SIGN_JS

    status_class = "signed" if status == "signed" else "sent"
    client_line = f"Prepared for: <strong>{client_label}</strong>" if client_label else "Project brief for review and approval"

    page = (
        _CLIENT_HEAD
        .replace("__STATUS_CLASS__", status_class)
        .replace("__STATUS_TEXT__", status.upper())
        .replace("__CLIENT_LINE__", client_line)
        + brief_html
        + sign_section
        + _CLIENT_TAIL
    )
    return HTMLResponse(content=page)


# ============================================================================
# Landing page — same design system, painkiller positioning
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    html_content = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>BriefStudio — Stop scope creep at the brief</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="Turn messy client intake into a structured brief your client signs. Timestamped sign-off and scope-change flagging for small marketing and creative agencies.">
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
        .section-cream {
            background: var(--surface-2);
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
            grid-template-columns: repeat(4, 1fr);
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

        .pricing {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 24px;
            max-width: 960px;
            margin: 0 auto;
        }
        .price-card {
            border: 1px solid var(--line-light);
            border-radius: 12px;
            padding: 28px 22px;
            background: var(--surface);
            text-align: center;
            position: relative;
        }
        .price-card.featured { border: 2px solid var(--accent); box-shadow: 0 12px 32px var(--accent-glow); }
        .price-card.featured::before {
            content: 'MOST POPULAR';
            position: absolute;
            top: -12px;
            left: 50%;
            transform: translateX(-50%);
            background: var(--accent);
            color: #fff;
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            padding: 4px 12px;
            border-radius: 999px;
        }
        .price-tier {
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--muted);
            margin-bottom: 10px;
        }
        .price-amount {
            font-family: 'Instrument Serif', Georgia, serif;
            font-size: 2.6rem;
            line-height: 1;
            margin-bottom: 4px;
        }
        .price-period { font-size: 0.82rem; color: var(--muted); margin-bottom: 20px; }
        .price-features { list-style: none; text-align: left; margin-bottom: 22px; }
        .price-features li {
            font-size: 0.88rem;
            color: var(--ink);
            margin-bottom: 10px;
            padding-left: 22px;
            position: relative;
        }
        .price-features li::before { content: '✓'; position: absolute; left: 0; color: var(--accent-2); font-weight: 700; }
        .price-features li.off { color: var(--muted); }
        .price-features li.off::before { content: '—'; color: var(--muted); }
        .price-note { font-size: 0.75rem; color: var(--muted); margin-top: 10px; }

        .workspace {
            padding: 72px 0 80px;
            position: relative;
            z-index: 1;
        }
        .workspace .section-head { margin-bottom: 32px; }
        .workspace .section-head h2 { color: var(--surface); }
        .workspace .section-head p { color: var(--muted-on-dark); }
        .workspace-alt { background: var(--bg-soft); }
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
        textarea#notes-input, textarea.notes-area {
            flex: 1;
            min-height: 200px;
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
        textarea#notes-input:focus, textarea.notes-area:focus {
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
            color: var(--ink);
        }
        .btn-copy.visible { display: inline-block; }
        .btn-copy:hover { background: var(--ink); color: var(--surface); }

        .signoff-box {
            display: none;
            margin-top: 14px;
            padding: 16px;
            background: #fff;
            border: 1px solid var(--line-light);
            border-radius: 10px;
        }
        .signoff-box.visible { display: block; }
        .signoff-box h4 {
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--muted);
            margin-bottom: 6px;
        }
        .signoff-box .sub { font-size: 0.8rem; color: var(--muted); margin-bottom: 10px; }
        .text-input {
            width: 100%;
            border: 1px solid var(--line-light);
            border-radius: 8px;
            padding: 11px 13px;
            font: inherit;
            font-size: 0.9rem;
            margin-bottom: 4px;
            background: var(--surface-2);
            color: var(--ink);
            outline: none;
        }
        .text-input:focus { outline: 2px solid var(--accent-glow); border-color: var(--accent); }
        .signoff-url {
            display: none;
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            font-size: 0.75rem;
            background: var(--surface-2);
            border: 1px dashed var(--line-light);
            border-radius: 8px;
            padding: 10px 12px;
            word-break: break-all;
            color: var(--ink);
            margin-top: 10px;
        }
        .scope-result {
            display: none;
            margin: 0;
            padding: 20px 24px 24px;
            background: var(--surface-2);
            border-top: 1px solid var(--line-light);
            font-size: 0.92rem;
            line-height: 1.6;
            color: var(--ink);
            white-space: pre-wrap;
        }
        .scope-result.visible { display: block; }

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
            .hero-grid, .desk, .steps, .benefits, .preview-cols, .pricing { grid-template-columns: 1fr; }
            .desk-out { border-left: none; border-top: 1px solid var(--line-light); }
            .site-bar nav { display: none; }
            .preview-card { transform: none; }
        }
    </style>
</head>
<body>
    <header class="site-bar">
        <div class="wrap">
            <div class="logo">Brief<span>Studio</span></div>
            <nav>
                <a href="#how">How it works</a>
                <a href="#pricing">Pricing</a>
                <a href="#scope-check">Scope check</a>
                <a href="#faq">FAQ</a>
            </nav>
            <a class="nav-cta" href="#tool">Try it free</a>
        </div>
    </header>

    <section class="hero">
        <div class="wrap hero-grid">
            <div>
                <p class="eyebrow">For marketing &amp; creative agencies</p>
                <h1>Every "small tweak" costs you money—<em>stop it at the brief.</em></h1>
                <p class="lede">Paste the kickoff email, Slack thread, or call notes. Get a structured brief your client signs off on—timestamped. When scope creep starts, you'll have the record to bill against instead of absorbing it.</p>
                <div class="hero-actions">
                    <a class="btn-primary" href="#tool">Create a brief</a>
                    <a class="btn-ghost" href="#pricing">See pricing</a>
                </div>
                <div class="trust-row">
                    <span>No account to start</span>
                    <span>Client sign-off included</span>
                    <span>You edit before anything goes out</span>
                </div>
            </div>
            <div class="preview-card" aria-hidden="true">
                <div class="preview-bar">
                    <span>briefstudio / brief / northwind-q4</span>
                    <span style="color:#6EE7B7;">SIGNED</span>
                </div>
                <div class="preview-body">
                    <div class="preview-cols">
                        <div class="preview-stat">
                            <label>Client</label>
                            <strong>Northwind Studio</strong>
                        </div>
                        <div class="preview-stat">
                            <label>Signed</label>
                            <strong>Oct 14 · 2:31 PM UTC</strong>
                        </div>
                    </div>
                    <p class="preview-snippet">"Scope: 3 concepts, 2 revision rounds, paid social + landing page. Approved by client—timestamped. Later request for 'a quick video' falls outside signed scope → change order."</p>
                    <cite>Scope locked · Record on file</cite>
                </div>
            </div>
        </div>
    </section>

    <section class="section-light" id="how">
        <div class="wrap">
            <div class="section-head">
                <h2>From messy intake to defensible scope in four steps</h2>
                <p>The brief isn't the product. The signed, timestamped record is what protects your margins.</p>
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
                    <p>Seven clear sections—goals, audience, scope, deliverables, assumptions, open questions, and timeline—ready for your edits.</p>
                </div>
                <div class="step">
                    <div class="step-num">03</div>
                    <h3>Client signs off</h3>
                    <p>Send a link. Client approves. Name and timestamp recorded—your evidence of what was agreed.</p>
                </div>
                <div class="step">
                    <div class="step-num">04</div>
                    <h3>Flag the creep</h3>
                    <p>When a new request lands, check it against the signed brief. See exactly what falls outside scope—bill for it.</p>
                </div>
            </div>
        </div>
    </section>

    <section class="workspace" id="tool">
        <div class="wrap">
            <div class="section-head">
                <h2>Try it on real notes</h2>
                <p>Paste below or load a sample. First brief asks for your email—then you're set.</p>
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

                        <div class="signoff-box" id="signoff-box">
                            <h4>Send for client sign-off</h4>
                            <p class="sub">Client sees this brief and approves it. Name + timestamp recorded—that's your evidence.</p>
                            <input type="text" class="text-input" id="client-label" placeholder="Client name (e.g., Northwind Studio)">
                            <button class="btn-draft" id="create-signoff-btn" type="button" style="margin-top:8px; padding:12px 18px;">Create sign-off link</button>
                            <div class="signoff-url" id="signoff-url"></div>
                            <button class="btn-copy" id="copy-signoff-url" type="button" style="width:100%; align-self:stretch; text-align:center;">Copy link</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <section class="workspace workspace-alt" id="scope-check">
        <div class="wrap">
            <div class="section-head">
                <h2>Check a new request against your signed brief</h2>
                <p>When the client asks for "just one more thing," paste it here. See exactly what falls outside the signed scope.</p>
            </div>
            <div class="tool-shell">
                <div class="tool-tabs">
                    <span class="active">Signed brief</span>
                    <span>New request</span>
                </div>
                <div class="desk" style="min-height:360px;">
                    <div class="desk-in">
                        <label class="field-label" for="signed-brief-input">Signed brief (paste the brief text)</label>
                        <textarea class="notes-area" id="signed-brief-input" placeholder="Paste the signed brief here…" style="min-height:160px;"></textarea>
                    </div>
                    <div class="desk-out">
                        <label class="field-label" for="new-request-input">New client request</label>
                        <textarea class="notes-area" id="new-request-input" placeholder="Paste the client's new email or request here…" style="min-height:160px;"></textarea>
                        <button class="btn-draft" id="scope-check-btn" type="button" style="margin-top:auto;">Check scope</button>
                    </div>
                </div>
                <div class="scope-result" id="scope-result"></div>
            </div>
        </div>
    </section>

    <section class="section-light" id="why">
        <div class="wrap">
            <div class="section-head">
                <h2>You're running accounts—not eating scope creep</h2>
                <p>Built for boutiques where the same person sells the work, writes the scope, and still has to deliver.</p>
            </div>
            <div class="benefits">
                <div class="benefit">
                    <h3>Bill for the "small tweaks"</h3>
                    <p>Scope-change flagging shows exactly what falls outside the signed scope—so "just one more thing" becomes a change order, not a freebie.</p>
                </div>
                <div class="benefit">
                    <h3>Evidence, not just a doc</h3>
                    <p>Your client's approval, name, and timestamp are recorded. A doc in your Drive can be edited after the fact. A signed record can't.</p>
                </div>
                <div class="benefit">
                    <h3>Works how clients actually brief you</h3>
                    <p>No templates to fill first. Drop in the ramble; get sections that match how your team already writes SOWs.</p>
                </div>
                <div class="benefit">
                    <h3>Why not just ChatGPT?</h3>
                    <p>ChatGPT can draft a brief—it can't capture your client's signature or flag drift against what was signed. The record is the part that protects your margins.</p>
                </div>
            </div>
        </div>
    </section>

    <section class="section-cream" id="pricing">
        <div class="wrap">
            <div class="section-head">
                <h2>Pricing that pays for itself</h2>
                <p>One prevented scope-creep event per month covers the cost. That's the bar.</p>
            </div>
            <div class="pricing">
                <div class="price-card">
                    <div class="price-tier">Starter</div>
                    <div class="price-amount">$0</div>
                    <div class="price-period">free forever</div>
                    <ul class="price-features">
                        <li>1 brief per month</li>
                        <li>Full 7-section output</li>
                        <li>Copy &amp; paste anywhere</li>
                        <li class="off">No client sign-off</li>
                        <li class="off">No scope checking</li>
                    </ul>
                    <a href="#tool" class="btn-primary" style="display:block; text-align:center; background:transparent; color:var(--ink); border:1px solid var(--ink);">Start free</a>
                    <p class="price-note">No card required</p>
                </div>
                <div class="price-card featured">
                    <div class="price-tier">Solo</div>
                    <div class="price-amount">$49</div>
                    <div class="price-period">per month</div>
                    <ul class="price-features">
                        <li>10 briefs per month</li>
                        <li>Client sign-off + timestamp</li>
                        <li>Scope-change flagging</li>
                        <li>Shareable sign-off links</li>
                        <li>Email support</li>
                    </ul>
                    <a href="#tool" class="btn-primary" style="display:block; text-align:center;">Start with Solo</a>
                    <p class="price-note">For 1–5 person shops</p>
                </div>
                <div class="price-card">
                    <div class="price-tier">Studio</div>
                    <div class="price-amount">$99</div>
                    <div class="price-period">per month</div>
                    <ul class="price-features">
                        <li>Unlimited briefs</li>
                        <li>Everything in Solo</li>
                        <li>Priority support</li>
                        <li>Early access to new features</li>
                        <li>Cancel anytime</li>
                    </ul>
                    <a href="#tool" class="btn-primary" style="display:block; text-align:center;">Start with Studio</a>
                    <p class="price-note">For 6–15 person shops</p>
                </div>
            </div>
            <p style="text-align:center; margin-top:32px; color:var(--muted); font-size:0.85rem;">
                Founding customers: we set up billing personally—invoice or card link.<br>
                Annual plans once you've proven the value. Cancel anytime.
            </p>
        </div>
    </section>

    <section class="faq" id="faq">
        <div class="wrap">
            <div class="section-head">
                <h2>Common questions</h2>
            </div>
            <div class="faq-list">
                <details>
                    <summary>How is this different from ChatGPT?</summary>
                    <p>ChatGPT drafts text. BriefStudio gets the brief signed by your client with a timestamp, stores it as a locked record, and flags when new requests fall outside what was signed. Generating text is free. Creating defensible evidence isn't.</p>
                </details>
                <details>
                    <summary>What does the sign-off actually do?</summary>
                    <p>Your client receives a link, reviews the brief, and clicks "I approve this scope." Their name and a UTC timestamp are recorded. If a dispute arises, you have a dated record of what was agreed—not a doc you may have edited since.</p>
                </details>
                <details>
                    <summary>How does scope-change flagging work?</summary>
                    <p>Paste the signed brief and the client's new request into the Scope Check. BriefStudio identifies what's new, what's an extension of existing scope, and what's unclear—so you can issue a change order instead of absorbing the cost.</p>
                </details>
                <details>
                    <summary>Do I still edit before the client sees it?</summary>
                    <p>Always. You get a draft to reshape, price, and approve. You send the sign-off link when you're ready—nothing goes to your client before you say so.</p>
                </details>
                <details>
                    <summary>What does it cost?</summary>
                    <p>$49/mo for Solo—10 briefs, sign-off, scope checking. $99/mo for Studio—unlimited briefs. First brief is free, no card needed.</p>
                </details>
                <details>
                    <summary>Why do you ask for my email?</summary>
                    <p>Once, so we know who's using the tool and can attach your briefs and sign-off records to you. We block temporary/disposable emails to prevent spam, but standard emails (Gmail, Outlook, etc.) are totally fine!</p>
                </details>
                <details>
                    <summary>What happens to client notes?</summary>
                    <p>Notes and briefs are stored securely so you can revisit them and use the scope-check. Delete requests are honored—contact us anytime.</p>
                </details>
            </div>
        </div>
    </section>

    <section class="cta-band">
        <div class="wrap">
            <h2>Stop eating the cost of scope creep</h2>
            <a class="btn-primary" href="#tool">Create a brief</a>
        </div>
    </section>

    <footer>
        <div class="wrap">© 2026 BriefStudio · Built for agencies that bill for their work</div>
    </footer>

    <div class="gate-overlay" id="email-gate">
        <div class="gate-card">
            <button class="gate-close" id="gate-close" type="button" aria-label="Close">&times;</button>
            <h2>Almost there</h2>
            <p>Enter your email so we know who's using the tool. Standard emails (Gmail, Outlook, etc.) are great—just no temporary/disposable emails.</p>
            <input type="text" id="gate-email" autocomplete="email" inputmode="email" spellcheck="false" placeholder="you@yourcompany.com" aria-label="Email address">
            <div class="field-error" id="gate-error"></div>
            <button class="btn-gate" id="gate-submit" type="button">Continue</button>
        </div>
    </div>

    <script>
        const EMAIL_KEY = 'briefstudio_email';
        let pendingNotes = null;
        let currentBriefId = null;
        let currentBriefText = null;

        // Frontend blocklist for instant rejection of disposable/temporary emails ONLY
        const BLOCKED_DOMAINS_JS = ["mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com", "yopmail.com", "trashmail.com", "getnada.com", "temp-mail.org", "sharklasers.com", "guerrillamailblock.com"];

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
            if (BLOCKED_DOMAINS_JS.includes(domain)) return false;
            if (!/^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$/.test(email)) return false;
            return true;
        }

        function openGate() { document.getElementById('email-gate').classList.add('visible'); }
        function closeGate() { document.getElementById('email-gate').classList.remove('visible'); }

        function renderBrief(text, briefId) {
            const resultBody = document.getElementById('result-body');
            const placeholder = document.getElementById('placeholder-state');
            const copyBtn = document.getElementById('copy-btn');
            const signoffBox = document.getElementById('signoff-box');
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
            currentBriefId = briefId || null;
            currentBriefText = text;
            if (currentBriefId) signoffBox.classList.add('visible');
            document.getElementById('doc-ref').textContent = currentBriefId ? currentBriefId.substring(0, 8) : String(Math.floor(1000 + Math.random() * 9000));
            document.getElementById('doc-date').textContent = 'Draft ready';
        }

        const SAMPLE_NOTES = "Hey team — client wants something for Q4 product launch. Social (Meta + maybe TikTok), landing page, they mentioned 'premium but approachable'. Budget not confirmed yet, ballpark 15–20k. No purple (CEO hates it). Competitor Lumina just rebranded — client wants to look distinct. Need first concepts in ~3 weeks if possible. Oh and they mentioned maybe wanting a video too but not sure yet.";

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
            const signoffBox = document.getElementById('signoff-box');
            const docDate = document.getElementById('doc-date');
            btn.disabled = true;
            btn.textContent = 'Building your brief…';
            notesError.textContent = '';
            resultBody.classList.remove('visible');
            copyBtn.classList.remove('visible');
            signoffBox.classList.remove('visible');
            document.getElementById('signoff-url').style.display = 'none';
            document.getElementById('copy-signoff-url').classList.remove('visible');
            placeholder.style.display = 'flex';
            placeholder.querySelector('p').textContent = 'Organizing sections…';
            docDate.textContent = 'In progress';

            try {
                let url = '/generate-brief?notes=' + encodeURIComponent(notes);
                if (email) url += '&email=' + encodeURIComponent(email);
                const response = await fetch(url);
                const data = await response.json();

                if (!response.ok) {
                    if (response.status === 400 && data.error && data.error.toLowerCase().includes('temporary')) {
                        clearSavedEmail();
                        document.getElementById('gate-error').textContent = data.error;
                        document.getElementById('gate-email').classList.add('invalid');
                        openGate();
                        throw new Error(data.error);
                    }
                    throw new Error(data.error || 'Could not create the brief.');
                }

                renderBrief(data.plan || '', data.brief_id);
            } catch (e) {
                placeholder.style.display = 'flex';
                placeholder.querySelector('p').textContent = e.message || 'Something went wrong. Try again.';
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
                gateError.textContent = 'Please use a valid email. Temporary/disposable emails are blocked.';
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

        // --- Sign-off link creation ---
        document.getElementById('create-signoff-btn').addEventListener('click', async function () {
            if (!currentBriefId || !currentBriefText) return;
            const btn = this;
            const clientLabel = document.getElementById('client-label').value.trim();
            const agencyEmail = getSavedEmail();
            btn.disabled = true;
            btn.textContent = 'Creating link…';
            try {
                const response = await fetch('/create-signoff', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        brief_id: currentBriefId,
                        agency_email: agencyEmail,
                        brief_text: currentBriefText,
                        client_label: clientLabel
                    })
                });
                const data = await response.json();
                if (response.ok) {
                    const fullUrl = window.location.origin + '/b/' + data.token;
                    const urlEl = document.getElementById('signoff-url');
                    urlEl.textContent = fullUrl;
                    urlEl.style.display = 'block';
                    document.getElementById('copy-signoff-url').classList.add('visible');
                    btn.textContent = 'Link created ✓';
                } else {
                    btn.textContent = 'Error—try again';
                }
            } catch (e) {
                btn.textContent = 'Error—try again';
            } finally {
                btn.disabled = false;
                setTimeout(function () { btn.textContent = 'Create sign-off link'; }, 2500);
            }
        });

        document.getElementById('copy-signoff-url').addEventListener('click', async function () {
            const url = document.getElementById('signoff-url').textContent;
            try {
                await navigator.clipboard.writeText(url);
                this.textContent = 'Copied';
                setTimeout(function () { document.getElementById('copy-signoff-url').textContent = 'Copy link'; }, 2000);
            } catch (e) { /* ignore */ }
        });

        // --- Scope check ---
        document.getElementById('scope-check-btn').addEventListener('click', async function () {
            const signedBrief = document.getElementById('signed-brief-input').value.trim();
            const newRequest = document.getElementById('new-request-input').value.trim();
            const resultEl = document.getElementById('scope-result');
            const btn = this;

            if (!signedBrief || !newRequest) {
                resultEl.textContent = 'Paste both the signed brief and the new request to run a check.';
                resultEl.classList.add('visible');
                return;
            }

            btn.disabled = true;
            btn.textContent = 'Analyzing…';
            resultEl.classList.remove('visible');

            try {
                const response = await fetch('/api/check-scope', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ brief_text: signedBrief, new_request: newRequest })
                });
                const data = await response.json();
                resultEl.textContent = data.analysis || data.error || 'Something went wrong.';
            } catch (e) {
                resultEl.textContent = 'Network error. Please try again.';
            } finally {
                resultEl.classList.add('visible');
                btn.disabled = false;
                btn.textContent = 'Check scope';
            }
        });
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)