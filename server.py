import os
import re
import secrets
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Body
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
# EXISTING: Generate brief (slightly modified to return brief_id)
# ============================================================================

@app.get("/generate-brief")
def generate_brief(
    notes: str = Query(..., description="Rough, unstructured notes from a client"),
    email: str = Query(..., description="Work email captured by the frontend"),
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

    # Generate a brief_id for this brief
    brief_id = str(secrets.token_hex(16))

    try:
        insert_data = {
            "notes": notes, 
            "brief": plan, 
            "email": email.strip().lower(),
            "brief_id": brief_id,
            "status": "draft"
        }
        supabase.table("b2b_briefs").insert(insert_data).execute()
    except Exception as e:
        print(f"Database Error: {e}")

    return {"plan": plan, "brief_id": brief_id}


# ============================================================================
# NEW: Create sign-off link
# ============================================================================

class SignOffRequest(BaseModel):
    brief_id: str
    agency_email: str
    brief_text: str
    client_label: str = ""

@app.post("/create-signoff")
async def create_signoff(request: SignOffRequest):
    """Creates a shareable sign-off link for a brief."""
    token = secrets.token_urlsafe(32)
    
    try:
        # Update the existing brief record with sign-off token
        result = supabase.table("b2b_briefs").update({
            "sign_off_token": token,
            "status": "sent",
            "client_label": request.client_label
        }).eq("brief_id", request.brief_id).eq("email", request.agency_email.strip().lower()).execute()
        
        if not result.data:
            # If update didn't find the record, insert a new one
            supabase.table("b2b_briefs").insert({
                "brief_id": request.brief_id,
                "email": request.agency_email.strip().lower(),
                "brief": request.brief_text,
                "sign_off_token": token,
                "status": "sent",
                "client_label": request.client_label
            }).execute()
    except Exception as e:
        print(f"Sign-off creation error: {e}")
        return JSONResponse(status_code=500, content={"error": "Could not create sign-off link."})
    
    return {"token": token, "sign_off_url": f"/b/{token}"}


# ============================================================================
# NEW: Client-facing brief view + sign-off page
# ============================================================================

@app.get("/b/{token}", response_class=HTMLResponse)
async def client_brief(token: str):
    """Client-facing page showing the brief and allowing sign-off."""
    
    # Look up the brief by token
    brief_data = None
    try:
        result = supabase.table("b2b_briefs").select("*").eq("sign_off_token", token).limit(1).execute()
        if result.data:
            brief_data = result.data[0]
    except Exception as e:
        print(f"Lookup error: {e}")
    
    if not brief_data:
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head><title>Brief Not Found</title></head>
        <body style="font-family: system-ui; background: #0F1419; color: #F4F0E8; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0;">
            <div style="text-align: center; max-width: 400px; padding: 40px;">
                <h1 style="font-size: 1.5rem;">Link Not Found</h1>
                <p style="color: #9CA3AF;">This sign-off link is invalid or has expired. Please contact your agency.</p>
            </div>
        </body>
        </html>
        """, status_code=404)
    
    brief_text = brief_data.get("brief", "")
    status = brief_data.get("status", "sent")
    signed_by = brief_data.get("signed_by", "")
    signed_at = brief_data.get("signed_at", "")
    client_label = brief_data.get("client_label", "")
    
    # Format signed_at for display
    signed_at_display = ""
    if signed_at:
        try:
            dt = datetime.fromisoformat(signed_at.replace("Z", "+00:00"))
            signed_at_display = dt.strftime("%B %d, %Y at %I:%M %p UTC")
        except:
            signed_at_display = str(signed_at)
    
    # Build the brief display HTML
    brief_lines = brief_text.split("\n")
    brief_html = ""
    for line in brief_lines:
        line = line.strip()
        if not line:
            continue
        clean = line.replace("**", "").replace("*", "")
        if clean.endswith(":") and len(clean) < 80:
            brief_html += f'<h3 style="font-family: Georgia, serif; font-size: 1.05rem; margin: 20px 0 8px; color: #0F1419;">{clean}</h3>'
        else:
            brief_html += f'<p style="font-size: 0.95rem; color: #374151; margin-bottom: 8px; line-height: 1.6;">{clean}</p>'
    
    sign_off_section = ""
    if status == "signed":
        sign_off_section = f"""
        <div style="background: #D1FAE5; border: 1px solid #6EE7B7; border-radius: 12px; padding: 24px; margin: 24px 0; text-align: center;">
            <div style="font-size: 2rem; margin-bottom: 8px;">✓</div>
            <h2 style="color: #065F46; font-size: 1.2rem; margin: 0 0 8px;">Scope Approved</h2>
            <p style="color: #047857; font-size: 0.9rem; margin: 0;">Signed by <strong>{signed_by}</strong></p>
            <p style="color: #047857; font-size: 0.85rem; margin: 4px 0 0;">{signed_at_display}</p>
            <p style="color: #6B7280; font-size: 0.8rem; margin: 12px 0 0;">This timestamped record is stored as evidence of the agreed scope.</p>
        </div>
        """
    else:
        sign_off_section = """
        <div style="background: #F4F0E8; border: 1px solid #D4CEC4; border-radius: 12px; padding: 24px; margin: 24px 0;">
            <h2 style="font-family: Georgia, serif; font-size: 1.2rem; color: #0F1419; margin: 0 0 8px;">Approve this scope</h2>
            <p style="color: #6B7280; font-size: 0.9rem; margin: 0 0 16px;">By approving, you confirm the scope above is what was agreed. Any changes to this scope will be documented separately.</p>
            <input type="text" id="signer-name" placeholder="Type your full name" style="width: 100%; padding: 12px 14px; border: 1px solid #D4CEC4; border-radius: 8px; font: inherit; margin-bottom: 12px; box-sizing: border-box;">
            <div id="sign-error" style="color: #E85D4C; font-size: 0.85rem; min-height: 1.2em; margin-bottom: 8px;"></div>
            <button id="approve-btn" onclick="approveScope()" style="width: 100%; background: #0F1419; color: #F4F0E8; border: none; padding: 14px; font: inherit; font-weight: 600; border-radius: 8px; cursor: pointer; font-size: 0.95rem;">
                I approve this scope
            </button>
        </div>
        <script>
            async function approveScope() {
                const name = document.getElementById('signer-name').value.trim();
                const errEl = document.getElementById('sign-error');
                const btn = document.getElementById('approve-btn');
                
                if (!name || name.length < 2) {
                    errEl.textContent = 'Please enter your full name.';
                    return;
                }
                
                errEl.textContent = '';
                btn.disabled = true;
                btn.textContent = 'Recording approval…';
                
                try {
                    const response = await fetch('/api/sign', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ token: window.location.pathname.split('/').pop(), signed_by: name })
                    });
                    const data = await response.json();
                    
                    if (response.ok) {
                        location.reload();
                    } else {
                        errEl.textContent = data.error || 'Something went wrong.';
                        btn.disabled = false;
                        btn.textContent = 'I approve this scope';
                    }
                } catch (e) {
                    errEl.textContent = 'Network error. Please try again.';
                    btn.disabled = false;
                    btn.textContent = 'I approve this scope';
                }
            }
        </script>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Project Brief — Sign-Off</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #FFFCF7; color: #0F1419; line-height: 1.6; }}
            .container {{ max-width: 680px; margin: 0 auto; padding: 40px 24px; }}
            .header {{ border-bottom: 2px solid #0F1419; padding-bottom: 16px; margin-bottom: 32px; display: flex; justify-content: space-between; align-items: center; }}
            .logo {{ font-family: Georgia, serif; font-size: 1.2rem; }}
            .logo span {{ color: #E85D4C; font-style: italic; }}
            .status {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; padding: 4px 10px; border-radius: 4px; font-weight: 600; }}
            .status.sent {{ background: #FEF3C7; color: #92400E; }}
            .status.signed {{ background: #D1FAE5; color: #065F46; }}
            .client-info {{ font-size: 0.85rem; color: #6B7280; margin-bottom: 24px; }}
            .brief-content {{ background: #fff; border: 1px solid #E5E7EB; border-radius: 12px; padding: 32px; }}
            .footer {{ text-align: center; font-size: 0.75rem; color: #9CA3AF; margin-top: 48px; padding-top: 24px; border-top: 1px solid #E5E7EB; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">Brief<span>Studio</span></div>
                <div class="status {status}">{status.upper()}</div>
            </div>
            <div class="client-info">
                {'Prepared for: <strong>' + client_label + '</strong>' if client_label else 'Project brief for review and approval'}
            </div>
            <div class="brief-content">
                {brief_html}
            </div>
            {sign_off_section}
            <div class="footer">
                Sent via BriefStudio — the scope-creep prevention tool for agencies.<br>
                This timestamped record protects both parties.
            </div>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)


# ============================================================================
# NEW: Record sign-off
# ============================================================================

class SignRequest(BaseModel):
    token: str
    signed_by: str

@app.post("/api/sign")
async def sign_brief(request: SignRequest):
    """Records the client's sign-off with timestamp."""
    if not request.signed_by or len(request.signed_by.strip()) < 2:
        return JSONResponse(status_code=400, content={"error": "Please provide your full name."})
    
    now = datetime.now(timezone.utc)
    
    try:
        result = supabase.table("b2b_briefs").update({
            "status": "signed",
            "signed_by": request.signed_by.strip(),
            "signed_at": now.isoformat()
        }).eq("sign_off_token", request.token).execute()
        
        if not result.data:
            return JSONResponse(status_code=404, content={"error": "Brief not found."})
        
        return {"success": True, "signed_at": now.isoformat()}
    except Exception as e:
        print(f"Sign error: {e}")
        return JSONResponse(status_code=500, content={"error": "Could not record sign-off."})


# ============================================================================
# NEW: Check scope (compare new request against signed brief)
# ============================================================================

class ScopeCheckRequest(BaseModel):
    brief_text: str
    new_request: str

@app.post("/api/check-scope")
async def check_scope(request: ScopeCheckRequest):
    """Uses AI to compare a new client request against the signed brief."""
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
            max_tokens=1500
        )
        return {"analysis": analysis}
    except RuntimeError as e:
        return JSONResponse(status_code=502, content={"error": str(e)})


# ============================================================================
# NEW: Get user's briefs (for scope-check retrieval)
# ============================================================================

@app.get("/api/my-briefs")
def get_my_briefs(email: str = Query(...)):
    """Returns all briefs for a given agency email."""
    is_valid, error_msg = validate_work_email(email)
    if not is_valid:
        return JSONResponse(status_code=400, content={"error": error_msg})
    
    try:
        result = supabase.table("b2b_briefs").select(
            "brief_id, status, signed_by, signed_at, client_label, brief, sign_off_token, created_at"
        ).eq("email", email.strip().lower()).order("created_at", desc=True).limit(20).execute()
        
        briefs = []
        for item in result.data:
            briefs.append({
                "brief_id": item.get("brief_id"),
                "status": item.get("status", "draft"),
                "signed_by": item.get("signed_by", ""),
                "signed_at": item.get("signed_at", ""),
                "client_label": item.get("client_label", ""),
                "sign_off_token": item.get("sign_off_token", ""),
                "brief_preview": (item.get("brief", ""))[:200] + "..." if len(item.get("brief", "")) > 200 else item.get("brief", ""),
                "brief_full": item.get("brief", "")
            })
        
        return {"briefs": briefs}
    except Exception as e:
        print(f"My briefs error: {e}")
        return JSONResponse(status_code=500, content={"error": "Could not retrieve briefs."})