import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


def _build_html(newsletter: list, analysis: dict = None) -> str:
    """Build HTML email from newsletter summaries + analysis."""
    now = datetime.now(timezone.utc).strftime("%B %d, %Y")

    # ── Summaries Section ─────────────────────────────────
    items_html = ""
    for item in newsletter:
        tags = " ".join(
            [f'<span style="background:#1a1a2e;color:#e94560;padding:2px 8px;'
             f'border-radius:12px;font-size:12px;margin-right:4px;">{t}</span>'
             for t in item.get("tags", [])]
        )
        items_html += f"""
        <div style="margin-bottom:16px;padding:16px;background:#f8f9fa;border-radius:8px;border-left:4px solid #0f3460;">
            <a href="{item.get('url', '#')}" style="color:#0f3460;text-decoration:none;font-weight:600;font-size:15px;">
                {item.get('title', 'Untitled')}
            </a>
            <div style="color:#888;font-size:12px;margin:4px 0;">{item.get('source', '')}</div>
            <p style="color:#333;font-size:14px;line-height:1.5;margin:8px 0;">
                {item.get('summary', '')}
            </p>
            <div>{tags}</div>
        </div>
        """

    # ── Analysis Section ──────────────────────────────────
    analysis_html = ""
    if analysis:
        weekly_theme = analysis.get("weekly_theme", "")
        hot_take = analysis.get("hot_take", "")
        connections = analysis.get("connections", "")
        implications = analysis.get("implications", {})
        skills_radar = analysis.get("skills_radar", [])

        analysis_blocks = ""
        for section in analysis.get("analysis_sections", []):
            body = section.get("body", "").replace("\n", "<br>")
            relevance = section.get("relevance", "")
            analysis_blocks += f"""
            <div style="margin-bottom:20px;">
                <h3 style="color:#0f3460;margin:0 0 8px;">{section.get('heading', '')}</h3>
                <p style="color:#333;font-size:14px;line-height:1.6;margin:0;">{body}</p>
                {f'<p style="color:#e94560;font-size:13px;font-style:italic;margin:8px 0 0;">&#128073; {relevance}</p>' if relevance else ''}
            </div>
            """

        implications_html = ""
        for key, label in [("industry", "&#127970; Industry"), ("economic", "&#128200; Economic"),
                           ("geopolitical", "&#127758; Geopolitical"), ("for_builders", "&#128295; For Builders")]:
            val = implications.get(key)
            if val:
                implications_html += f"""
                <div style="margin-bottom:12px;">
                    <strong style="color:#0f3460;">{label}:</strong>
                    <span style="color:#333;font-size:14px;"> {val}</span>
                </div>
                """

        skills_html = ""
        if skills_radar:
            skills_badges = " ".join(
                [f'<span style="background:#0f3460;color:#fff;padding:4px 12px;'
                 f'border-radius:16px;font-size:13px;margin-right:6px;">{s}</span>'
                 for s in skills_radar]
            )
            skills_html = f"""
            <div style="margin-top:16px;">
                <strong style="color:#0f3460;">&#128225; Skills Radar:</strong><br>
                <div style="margin-top:8px;">{skills_badges}</div>
            </div>
            """

        analysis_html = f"""
        <div style="margin:30px 0;padding:24px;background:linear-gradient(135deg,#0f3460,#1a1a2e);color:#fff;border-radius:12px;">
            <h2 style="color:#e94560;margin:0 0 4px;font-size:20px;">&#129504; The Brain's Take</h2>
            <p style="color:#ccc;font-size:13px;margin:0 0 16px;">AI-powered analysis — connecting the dots</p>
            <div style="background:rgba(255,255,255,0.08);padding:16px;border-radius:8px;margin-bottom:16px;">
                <strong style="color:#e94560;">This Week's Theme:</strong>
                <p style="color:#fff;font-size:15px;margin:8px 0 0;line-height:1.5;">{weekly_theme}</p>
            </div>
            {f'''<div style="background:rgba(255,255,255,0.05);padding:16px;border-radius:8px;margin-bottom:16px;">
                <strong style="color:#e94560;">How It All Connects:</strong>
                <p style="color:#ddd;font-size:14px;margin:8px 0 0;line-height:1.6;">{connections.replace(chr(10), "<br>")}</p>
            </div>''' if connections else ''}
        </div>
        <div style="margin:20px 0;">
            <h2 style="color:#0f3460;font-size:20px;border-bottom:2px solid #e94560;padding-bottom:8px;">Implications</h2>
            {implications_html}
        </div>
        <div style="margin:20px 0;">
            <h2 style="color:#0f3460;font-size:20px;border-bottom:2px solid #e94560;padding-bottom:8px;">Deep Dives</h2>
            {analysis_blocks}
        </div>
        <div style="background:#fff3cd;padding:16px;border-radius:8px;border-left:4px solid #e94560;margin:20px 0;">
            <strong style="color:#0f3460;">Hot Take:</strong>
            <p style="color:#333;font-size:14px;margin:8px 0 0;line-height:1.5;">{hot_take}</p>
        </div>
        {skills_html}
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:680px;margin:0 auto;padding:20px;background:#ffffff;">
        <div style="text-align:center;padding:30px 0;border-bottom:3px solid #0f3460;">
            <h1 style="color:#0f3460;margin:0;font-size:28px;">&#9889; AI Pulse</h1>
            <p style="color:#888;margin:8px 0 0;">Your Weekly AI/ML Digest — {now}</p>
        </div>
        {analysis_html}
        <div style="margin:30px 0;">
            <h2 style="color:#0f3460;font-size:20px;border-bottom:2px solid #e94560;padding-bottom:8px;">This Week's Stories</h2>
            {items_html}
        </div>
        <div style="text-align:center;padding:20px;color:#888;font-size:13px;border-top:1px solid #eee;">
            AI Pulse — Summaries by BART | Analysis by Claude Sonnet | Pipeline by Python<br>
            Built by Shashank Bodapati
        </div>
    </body>
    </html>
    """
    return html


def send_email(
    newsletter: list,
    analysis: dict,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    to_email: str,
    from_email: str = None,
) -> bool:
    """Send newsletter + analysis as HTML email."""
    if from_email is None:
        from_email = smtp_user

    now = datetime.now(timezone.utc).strftime("%b %d, %Y")
    theme = analysis.get("weekly_theme", "AI/ML Digest") if analysis else "AI/ML Digest"
    subject = f"AI Pulse — {theme} ({now})"

    html_body = _build_html(newsletter, analysis)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"AI Pulse <{from_email}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        logger.info(f"Sending email to {to_email} via {smtp_host}:{smtp_port}")
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        logger.info("Email sent successfully")
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False
