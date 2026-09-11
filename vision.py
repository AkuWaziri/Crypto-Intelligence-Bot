import base64
import os

from groq import Groq


VISION_MODEL = os.getenv(
    "GROQ_VISION_MODEL",
    "qwen/qwen3.6-27b",
)


def analyze_image(image_bytes, user_instruction=""):
    """Turn a Telegram image into a factual visual context packet."""
    if not image_bytes:
        return ""

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    encoded = base64.b64encode(image_bytes).decode("utf-8")

    prompt = f"""
Analyze this image for a crypto intelligence/content workflow.

Identify only what is actually visible or clearly readable.
Extract:
- visible text, headlines, usernames, protocol names, token names, numbers, dates and URLs
- charts, dashboards, screenshots, posts, memes, announcements or interfaces
- important visual relationships or unusual details
- what the image appears to be about
- uncertainty where text/details cannot be read reliably

Do not invent missing information.
Do not assume a claim in the image is true.
Treat the image as evidence to investigate, not as verified fact.

User instruction:
{user_instruction or 'Determine what is useful in this image for the requested crypto task.'}

Return a concise factual visual context packet that another research/writing model can use.
""".strip()

    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{encoded}",
                        },
                    },
                ],
            }
        ],
        max_completion_tokens=900,
    )

    return (
        response.choices[0].message.content or ""
    ).strip()
