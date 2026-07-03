"""Weekly report generation for office attendance tracking."""
import os
import smtplib
from collections import defaultdict
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List

from sqlmodel import Session, select

from models import Entry


def get_previous_week_start() -> datetime:
    """Get Monday of the previous week."""
    today = datetime.now().date()
    # Get Monday of current week
    days_since_monday = today.weekday()
    current_monday = today - timedelta(days=days_since_monday)
    # Go back one week
    previous_monday = current_monday - timedelta(days=7)
    return datetime.combine(previous_monday, datetime.min.time())


def calculate_office_days(entries: List[Entry]) -> Dict[str, int]:
    """
    Calculate days each person was NOT working from home (excluding holidays).
    
    Returns dict mapping user_name -> count of office/client days.
    """
    office_days_by_user = defaultdict(int)
    
    for entry in entries:
        # Count only "Neal Street" and "Client Office" (not WFH, not Holiday)
        if entry.location in ("Neal Street", "Client Office"):
            office_days_by_user[entry.user_name] += 1
    
    return dict(office_days_by_user)


def generate_report_html(week_start: datetime, week_end: datetime, office_days: Dict[str, int]) -> str:
    """Generate HTML email report."""
    week_start_str = week_start.strftime("%B %d, %Y")
    week_end_str = week_end.strftime("%B %d, %Y")
    
    # Sort by name for readability
    sorted_users = sorted(office_days.items(), key=lambda x: x[0].lower())
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f5f5f5; padding: 20px; }}
            .container {{ max-width: 800px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            h1 {{ color: #333; border-bottom: 3px solid #000; padding-bottom: 10px; }}
            h2 {{ color: #666; margin-top: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #000; color: #fff; font-weight: bold; }}
            tr:hover {{ background-color: #f5f5f5; }}
            .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Weekly Office Attendance Report</h1>
            <h2>Week of {week_start_str} to {week_end_str}</h2>
            <p>This report shows the number of days each team member was <strong>NOT working from home</strong> (excluding holidays).</p>
            
            <table>
                <thead>
                    <tr>
                        <th>Team Member</th>
                        <th>Days in Office/Client Site</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    if sorted_users:
        for user_name, days in sorted_users:
            html += f"""
                    <tr>
                        <td>{user_name}</td>
                        <td><strong>{days}</strong> day{'s' if days != 1 else ''}</td>
                    </tr>
            """
    else:
        html += """
                    <tr>
                        <td colspan="2" style="text-align: center; color: #999;">No entries found for this week</td>
                    </tr>
        """
    
    html += f"""
                </tbody>
            </table>
            
            <div class="footer">
                <p>Generated automatically on {datetime.now().strftime("%B %d, %Y at %I:%M %p")}</p>
                <p>This is an automated report from the Work Location Tracker system.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


def send_email(
    subject: str,
    html_content: str,
    recipients: List[str],
    smtp_server: str = None,
    smtp_port: int = None,
    smtp_user: str = None,
    smtp_password: str = None,
    from_email: str = None,
) -> bool:
    """
    Send email using SMTP.
    
    All parameters can come from environment variables if not provided.
    Defaults to SendGrid (recommended for cloud platforms).
    """
    # Default to SendGrid (more reliable from cloud platforms)
    smtp_server = smtp_server or os.getenv("SMTP_SERVER", "smtp.sendgrid.net")
    smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
    smtp_user = smtp_user or os.getenv("SMTP_USER", "apikey")  # SendGrid uses "apikey" as username
    smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")  # SendGrid API key goes here
    from_email = from_email or os.getenv("FROM_EMAIL")

    if not smtp_password:
        raise ValueError(f"SMTP_PASSWORD environment variable not set. Current SMTP_USER: {smtp_user}")

    if not from_email:
        raise ValueError("FROM_EMAIL environment variable not set")
    
    if not recipients:
        raise ValueError("At least one recipient email address is required")
    
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Creating email message. From: {from_email}, To: {recipients}")
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = ", ".join(recipients)
        
        # Add HTML content
        html_part = MIMEText(html_content, "html")
        msg.attach(html_part)
        
        # Send email with timeout
        logger.info(f"Connecting to SMTP server: {smtp_server}:{smtp_port}")
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
        logger.info("SMTP connection established")
        try:
            logger.info("Starting TLS...")
            server.starttls()
            logger.info("TLS started, attempting login...")
            server.login(smtp_user, smtp_password)
            logger.info("Login successful, sending message...")
            server.send_message(msg)
            logger.info("Message sent successfully")
            return True
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {str(e)}")
            raise Exception(f"SMTP authentication failed. Check your SMTP_PASSWORD. Error: {str(e)}")
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {str(e)}")
            raise Exception(f"SMTP error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during SMTP send: {str(e)}")
            raise
        finally:
            try:
                server.quit()
                logger.info("SMTP connection closed")
            except:
                pass
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        raise Exception(f"Failed to send email: {str(e)}")


def generate_and_send_weekly_report(
    session: Session,
    recipients: List[str] = None,
) -> dict:
    """
    Generate weekly report for previous week and send via email.
    
    Args:
        session: Database session
        recipients: List of email addresses (or from REPORT_EMAILS env var)
    
    Returns:
        dict with success status and details
    """
    # Get recipients from env if not provided
    if not recipients:
        emails_str = os.getenv("REPORT_EMAILS", "")
        recipients = [e.strip() for e in emails_str.split(",") if e.strip()]

    if not recipients:
        raise ValueError("No recipients provided and REPORT_EMAILS environment variable not set")
    
    try:
        # Get previous week (Monday to Friday)
        week_start = get_previous_week_start()
        week_end = week_start + timedelta(days=4)  # Friday
        
        week_start_str = week_start.strftime("%Y-%m-%d")
        week_end_str = week_end.strftime("%Y-%m-%d")
        
        # Query entries for the week
        stmt = (
            select(Entry)
            .where(Entry.date >= week_start_str)
            .where(Entry.date <= week_end_str)
        )
        
        entries = session.exec(stmt).all()
        
        # Calculate office days per user
        office_days = calculate_office_days(entries)
        
        # Generate HTML report
        html_content = generate_report_html(week_start, week_end, office_days)
        
        # Send email
        subject = f"Weekly Office Attendance Report - {week_start.strftime('%B %d')} to {week_end.strftime('%B %d, %Y')}"
        send_email(subject, html_content, recipients)
        
        return {
            "success": True,
            "week_start": week_start_str,
            "week_end": week_end_str,
            "recipients": recipients,
            "users_reported": len(office_days),
            "total_entries": len(entries),
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }

