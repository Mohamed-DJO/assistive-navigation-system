from datetime import datetime
import smtplib
import os
from email.mime.text import MIMEText
#from navigation.gps.gps_pc import PCGPS   # IP-based GPS — works on RPi too
from navigation.gps.gps_neo7m import Neo7MGPS


def _load_credentials():
    sender   = ""        # ← your Gmail address
    password = ""        # ← your 16-char app password (no spaces)
    receiver = ""        # ← recipient email
    return sender, password, receiver


def send_email_alert():
    #gps = PCGPS()
    gps = Neo7MGPS()
    lat, lon = gps.get_location()

    sender, password, receiver = _load_credentials()

    if not all([sender, password, receiver]):
        print("[SOS] ❌ Missing credentials.")
        return

    if lat is not None and lon is not None:
        location_str = f"{lat}, {lon}"
        maps_link    = f"https://maps.google.com/?q={lat},{lon}"
    else:
        location_str = "Unavailable (GPS failed)"
        maps_link    = "N/A"

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    body = f"""
🚨🚨🚨 URGENT SOS ALERT 🚨🚨🚨

The user has triggered the emergency system.

Time:             {current_time}
Current Location: {location_str}
Google Maps:      {maps_link}

Immediate assistance is required.
Please contact the user immediately.

-- Automated SOS System
"""

    message = MIMEText(body)
    message["Subject"] = "🚨 URGENT SOS ALERT 🚨"
    message["From"]    = sender
    message["To"]      = receiver

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(message)
        print("✅ SOS Email Sent Successfully")
    except Exception as e:
        print(f"[SOS] ❌ Failed to send email: {e}")
