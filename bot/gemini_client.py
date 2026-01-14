"""Lightweight Gemini API wrapper (synchronous/async usage)
This wrapper prefers google-generative-ai library if available, otherwise falls back to a simple HTTP stub.
"""
import os
import asyncio
import logging

try:
    import google.generativeai as genai
    _HAS_GENAI = True
except Exception:
    genai = None
    _HAS_GENAI = False

logger = logging.getLogger(__name__)

API_KEY = os.getenv("GEMINI_API_KEY")
# default inexpensive model and high quality model names
DEFAULT_CHEAP_MODEL = os.getenv("GEMINI_CHEAP_MODEL", "gemini-1.5" )
DEFAULT_HIGH_MODEL = os.getenv("GEMINI_HIGH_MODEL", "gemini-pro")

if _HAS_GENAI and API_KEY:
    genai.configure(api_key=API_KEY)


async def chat(prompt: str, system: str = None, max_tokens: int = 512, model: str | None = None) -> dict:
    """Call Gemini chat. Returns dict with keys: 'text', 'tokens' (estimated)"""
    model = model or DEFAULT_HIGH_MODEL
    if _HAS_GENAI:
        try:
            resp = genai.ChatCompletion.create(
                model=model,
                messages=[{"role": "system", "content": system or ""}, {"role": "user", "content": prompt}],
                max_output_tokens=max_tokens,
            )
            text = getattr(resp, "content", None) or resp["choices"][0]["message"]["content"]
            tokens = (len(text.split()) // 0.75) if text else 0
            return {"text": text, "tokens": float(tokens)}
        except Exception as e:
            logger.exception("Gemini chat failed: %s", e)
            return {"text": "", "tokens": 0.0}
    else:
        await asyncio.sleep(0.2)
        text = f"[stub] {prompt[:512]}"
        return {"text": text, "tokens": float(len(text.split())/0.75)}


async def summarize_context(text: str, max_tokens: int = 128) -> dict:
    """Generate a short summary using the cheap model to save tokens."""
    # Use cheap model for summarization
    if not text:
        return {"summary": "", "tokens": 0.0}
    prompt = f"要約してください（短く）: {text}"
    resp = await chat(prompt, system="Summarize the conversation briefly.", max_tokens=max_tokens, model=DEFAULT_CHEAP_MODEL)
    return {"summary": (resp.get("text") or "").strip(), "tokens": resp.get("tokens", 0.0)}
