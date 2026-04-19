import os
import httpx
from dotenv import load_dotenv

load_dotenv()

# Common crisis keywords
CRISIS_KEYWORDS = [
    "suicide",
    "self harm",
    "hopeless",
    "end my life",
    "kill myself",
    "don't want to live",
    "better off dead"
]

def check_crisis_and_notify(text: str, user_id: str) -> bool:
    text_lower = text.lower()
    is_crisis = any(keyword in text_lower for keyword in CRISIS_KEYWORDS)
    
    if is_crisis:
        # Trigger webhook
        n8n_url = os.getenv("N8N_WEBHOOK_URL")
        if n8n_url:
            try:
                # Fire and forget (in a real app, use background task)
                payload = {
                    "event": "CRISIS_ALERT",
                    "user_id": user_id,
                    "message": text,
                    "risk_level": "SEVERE"
                }
                httpx.post(n8n_url, json=payload, timeout=2.0)
            except Exception as e:
                print(f"Webhook failed to send: {e}")
                
    return is_crisis
