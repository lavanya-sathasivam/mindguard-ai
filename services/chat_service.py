import os
import logging
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("mindguard.chat")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-1.5-flash")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

openai_client = None
gemini_model = None

# Prefer Gemini when a Gemini API key is available; fall back to OpenAI if not.
try:
    if GEMINI_API_KEY:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel(GEMINI_CHAT_MODEL)
except Exception as e:
    logger.warning("Gemini client initialization failed: %s", e)

try:
    if OPENAI_API_KEY:
        from openai import OpenAI

        openai_client = OpenAI(api_key=OPENAI_API_KEY)
except Exception as e:
    logger.warning("OpenAI client initialization failed: %s", e)


def _build_system_prompt(user_context: Optional[dict], emotion: str, sentiment: float, risk_level: str, is_crisis: bool) -> str:
    name = (user_context or {}).get("name") or "there"
    stress_trigger = (user_context or {}).get("stress_trigger") or "unspecified stressors"
    social_preference = (user_context or {}).get("social_preference") or "at their own pace"

    crisis_instruction = (
        "\n🚨 CRISIS PROTOCOL: User is in acute distress. Immediately validate their feelings, "
        "strongly encourage contact with emergency services if suicidal, and maintain compassion. "
        "Responses must prioritize safety above all else."
        if is_crisis
        else ""
    )

    return (
        "You are MindGuard AI, a genuinely empathetic conversational mental-health companion. "
        "Your conversation style must be INDISTINGUISHABLE from talking to a caring human therapist—not an AI. "
        "Every response is unique; never repeat the same phrases, advice, or structure.\n\n"
        "CORE PRINCIPLES:\n"
        "1. ACTIVE LISTENING: Reflect back what the user shares. Show you understand nuance, not just keywords.\n"
        "2. NATURAL TONE: Use conversational language. Avoid 'I hear you', 'take a deep breath', 'one step at a time'—these are overused.\n"
        "3. GENUINE FOLLOW-UPS: Ask questions that show you're thinking about THEIR life, not a template.\n"
        "4. VARIED RESPONSES: If a user asks similar things, respond differently each time. Vary sentence structure, emotion depth, and approach.\n"
        "5. NO ADVICE UNLESS ASKED: Listen first. Let the user lead. Don't jump to 'try this'.\n"
        "6. PERSONAL CONTEXT: Weave in the user's specific triggers and preferences naturally, but never robotically.\n"
        "7. NORMALIZE FEELINGS: Validate without being patronizing. Show that struggles are human, not failures.\n"
        "8. STAY WITHIN BOUNDS: You are not a doctor. Never diagnose. If severe mental health concerns, encourage professional help gently.\n"
        "9. EMOTIONAL INTELLIGENCE: Your tone should match their intensity—if they're frustrated, show you get the frustration; if they're lost, be thoughtful and exploratory.\n"
        "10. CONVERSATION MEMORY: Reference earlier parts of this conversation naturally to show continuity.\n\n"
        f"USER PROFILE:\n"
        f"  Name: {name}\n"
        f"  Known stress: {stress_trigger}\n"
        f"  Social preference: {social_preference}\n\n"
        f"EMOTIONAL STATE (context, not rules):\n"
        f"  Detected emotion: {emotion}\n"
        f"  Sentiment: {sentiment:.2f} (range: -1 to 1)\n"
        f"  Risk level: {risk_level}\n"
        f"{crisis_instruction}\n\n"
        "RESPONSE GUIDELINES:\n"
        "- Keep responses 2-5 sentences unless the user asks for more.\n"
        "- Use active listening (reflect, validate, clarify) rather than advice-giving.\n"
        "- Every response should feel like the next turn in a human conversation, not a pre-written template.\n"
        "- Vary your language: sometimes ask questions, sometimes reflect, sometimes validate, sometimes share perspective.\n"
    )


def _build_openai_messages(
    current_user_text: str,
    conversation_history: Optional[List[Dict[str, str]]],
    system_prompt: str,
) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    for item in (conversation_history or []):
        role = item.get("role", "user")
        content = (item.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": current_user_text})
    return messages


def _build_gemini_prompt(
    current_user_text: str,
    conversation_history: Optional[List[Dict[str, str]]],
    system_prompt: str,
) -> str:
    history_lines = []
    for item in (conversation_history or []):
        role = item.get("role", "user")
        content = (item.get("content") or "").strip()
        if not content:
            continue
        prefix = "User" if role == "user" else "Assistant"
        history_lines.append(f"{prefix}: {content}")

    history_block = "\n".join(history_lines)

    return (
        f"SYSTEM:\n{system_prompt}\n\n"
        f"RECENT CONVERSATION:\n{history_block}\n\n"
        f"USER:\n{current_user_text}\n\n"
        "ASSISTANT:"
    )


def _local_fallback_reply(
    text: str,
    emotion: str,
    sentiment: float,
    risk_level: str,
    is_crisis: bool,
    user_context: Optional[dict] = None,
) -> str:
    name = (user_context or {}).get("name") or "there"

    if is_crisis or risk_level.lower() in {"high", "severe"}:
        return (
            f"I’m really glad you shared this, {name}. Your safety matters most right now. "
            "If you might act on thoughts of self-harm, please contact local emergency services immediately. "
            "If you can, reach out to someone you trust and stay with them while we take this one step at a time."
        )

    lowered = text.lower()
    if "sleep" in lowered or "tired" in lowered:
        return (
            "That sounds exhausting, and it makes sense this is weighing on you. "
            "A small reset could help: put the phone away for 10 minutes, slow your breathing, and let your body settle. "
            "Would you like a short wind-down routine for tonight?"
        )

    if "work" in lowered or "study" in lowered or "exam" in lowered:
        return (
            "That pressure can build up fast, especially when your mind stays in overdrive. "
            "Try this: pick one tiny next task that takes under 10 minutes and do only that first. "
            "What feels like the smallest doable step right now?"
        )

    emotion_key = (emotion or "neutral").lower()
    if emotion_key in {"anger", "frustration"}:
        return (
            "I can hear how intense this feels right now. "
            "Before reacting, try a quick release: unclench your jaw, drop your shoulders, and take three slow breaths. "
            "Do you want to talk through what triggered this feeling?"
        )

    if emotion_key in {"sadness", "grief", "disappointment"} or sentiment < -0.35:
        return (
            "I’m with you, and what you’re feeling is valid. "
            "When things feel heavy, it helps to shrink the moment: one glass of water, one breath, one gentle action. "
            "Would it help to name what feels hardest right now?"
        )

    if emotion_key in {"fear", "anxiety", "nervousness"} or sentiment < -0.1:
        return (
            "It sounds like your mind is on high alert right now. "
            "Let’s ground for 30 seconds: notice 5 things you can see, 4 you can feel, and one slow exhale. "
            "After that, tell me which thought feels the loudest."
        )

    if emotion_key in {"joy", "optimism", "relief"} or sentiment > 0.4:
        return (
            "I’m really glad to hear this shift. "
            "If you want to keep this momentum, capture one thing that helped you feel better today so you can reuse it later. "
            "Want me to help you turn it into a simple routine?"
        )

    return (
        f"Thanks for sharing this, {name}. I’m here with you. "
        "We can take this one step at a time—slow breath in, slower breath out. "
        "Would you like support focused on calming down right now or on making a plan for the next few hours?"
    )


def _smart_fallback_reply(
    text: str,
    emotion: str,
    sentiment: float,
    risk_level: str,
    is_crisis: bool,
    user_context: Optional[dict] = None,
) -> str:
    """
    Smart fallback when LLM is unavailable.
    Instead of hardcoded templates, this generates contextual responses that invite deeper conversation.
    Better than a generic error, though still not as good as LLM-generated responses.
    """
    name = (user_context or {}).get("name") or "there"

    # Crisis takes absolute priority
    if is_crisis or risk_level.lower() in {"high", "severe"}:
        crisis_responses = [
            f"{name}, I need to be direct: your safety comes first. If there's any chance you might harm yourself, please reach out to emergency services or a crisis line right now. This conversation matters, but your immediate safety matters more.",
            f"I'm really concerned about what you're sharing. Please reach out to someone you trust immediately—a friend, family member, or crisis hotline. You don't have to face this alone, and professional support is crucial right now.",
            f"This sounds like you're in real distress. Please contact emergency services (911 in the US) or a mental health crisis line. Your safety is the priority, and trained professionals can help in ways I can't.",
        ]
        import random
        return random.choice(crisis_responses)

    # For non-crisis, generate responses that encourage further conversation
    reflection_starters = [
        f"It sounds like you're dealing with a lot right now. Can you tell me more about what's making this so difficult?",
        f"I'm picking up that you're struggling with this. What's going on beneath the surface?",
        f"That's a lot to carry. What part of this feels most overwhelming to you?",
        f"I hear you. What do you think is at the center of what you're feeling?",
        f"You're sharing something real here. What would help the most right now—to be heard, to brainstorm, or something else?",
        f"That matters. What do you think needs to happen next?",
        f"Tell me more about what led you here. I'm listening.",
        f"I'm here. What would be useful for you to talk through?",
    ]

    import random
    return random.choice(reflection_starters)


def generate_ai_reply(
    text: str,
    emotion: str,
    sentiment: float,
    risk_level: str,
    is_crisis: bool,
    user_context: Optional[dict] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    system_prompt = _build_system_prompt(user_context, emotion, sentiment, risk_level, is_crisis)

    # Prefer Gemini if initialized
    if gemini_model:
        try:
            prompt = _build_gemini_prompt(text, conversation_history, system_prompt)
            response = gemini_model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.8,
                    "max_output_tokens": 280,
                },
                request_options={"timeout": 8},
            )
            content = (getattr(response, "text", "") or "").strip()
            if content:
                return content
        except Exception as e:
            logger.warning("Gemini completion failed: %s", e)

    if openai_client:
        try:
            messages = _build_openai_messages(text, conversation_history, system_prompt)
            response = openai_client.chat.completions.create(
                model=OPENAI_CHAT_MODEL,
                messages=messages,
                temperature=0.8,
                max_tokens=280,
                timeout=8.0,
            )
            content = (response.choices[0].message.content or "").strip()
            if content:
                return content
        except Exception as e:
            logger.warning("OpenAI completion failed: %s", e)

    return _smart_fallback_reply(
        text=text,
        emotion=emotion,
        sentiment=sentiment,
        risk_level=risk_level,
        is_crisis=is_crisis,
        user_context=user_context,
    )
