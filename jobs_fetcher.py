# jobs_fetcher.py
import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import feedparser

# Configuration via environment variables (set in GitHub Secrets)
FEEDS = os.getenv("JOB_FEEDS", "").split("|")  # pipe-separated feed URLs
KEYWORDS = os.getenv("JOB_KEYWORDS", "entry level|junior|intern|associate|fresher|data analyst|data analytics").lower().split("|")
TOP_STARTUPS = os.getenv("TOP_STARTUPS", "Flipkart|Swiggy|Zomato|Razorpay|BYJU'S|Freshworks|OYO|Unacademy|Postman|CRED").split("|")

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
RECIPIENT = os.getenv("RECIPIENT_EMAIL")
SENDER = os.getenv("SENDER_EMAIL", SMTP_USER)

# How far back to consider jobs (in days)
DAYS_BACK = int(os.getenv("DAYS_BACK", "7"))  # default 7 days

def matches(entry):
    text = " ".join([
        entry.get("title",""),
        entry.get("summary",""),
        entry.get("company","") if "company" in entry else ""
    ]).lower()
    # keyword or startup name match
    if any(k.strip() and k.strip() in text for k in KEYWORDS):
        return True
    if any(s.strip().lower() in text for s in TOP_STARTUPS):
        return True
    return False

def parse_feed(url):
    feed = feedparser.parse(url)
    matches_list = []
    cutoff = datetime.utcnow() - timedelta(days=DAYS_BACK)
    for entry in feed.entries:
        # parse published/updated time if available
        try:
            published = None
            if 'published_parsed' in entry and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6])
            elif 'updated_parsed' in entry and entry.updated_parsed:
                published = datetime(*entry.updated_parsed[:6])
        except Exception:
            published = None

        if published and published < cutoff:
            continue

        if matches(entry):
            matches_list.append({
                "title": entry.get("title","No title"),
                "link": entry.get("link",""),
                "summary": entry.get("summary","")[:400],
                "published": published.isoformat() if published else "Unknown",
                "source": feed.feed.get("title", url)
            })
    return matches_list

def build_email(found_jobs):
    html = "<h2>Daily Job Matches</h2>"
    if not found_jobs:
        html += "<p>No new matches found in the selected feeds for your keywords.</p>"
    else:
        html += "<ul>"
        for j in found_jobs:
            html += f'<li><b>{j["title"]}</b> — <i>{j["source"]}</i><br/>{j["summary"]} <br/>Published: {j["published"]} <br/><a href="{j["link"]}">View job</a></li><br/>'
        html += "</ul>"
    html += f"<hr/><p>Generated at {datetime.utcnow().isoformat()} UTC</p>"
    return html

def send_email(subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    part = MIMEText(html_body, "html")
    msg.attach(part)

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SENDER, RECIPIENT.split(","), msg.as_string())

def main():
    if not FEEDS or not FEEDS[0]:
        print("No feeds provided in JOB_FEEDS environment variable.")
        return

    all_matches = []
    for url in FEEDS:
        url = url.strip()
        if not url:
            continue
        try:
            matches = parse_feed(url)
            for m in matches:
                # avoid duplicates by link
                if m["link"] not in [x["link"] for x in all_matches]:
                    all_matches.append(m)
        except Exception as e:
            print(f"Failed to parse {url}: {e}")

    subject = f"Job Matches — {len(all_matches)} results — {datetime.utcnow().date().isoformat()}"
    html = build_email(all_matches)
    send_email(subject, html)
    print(f"Sent email with {len(all_matches)} matches.")

if __name__ == "__main__":
    main()
