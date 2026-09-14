import base64
import os

from groq import Groq


VISION_MODEL = os.getenv(
    "GROQ_VISION_MODEL",
    "qwen/qwen3.6-27b",
)


def analyze_image(image_bytes, user_instruction=""):
    """Turn a Telegram image into a detailed factual visual context packet."""
    if not image_bytes:
        return ""

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    encoded = base64.b64encode(image_bytes).decode("utf-8")

    prompt = f"""
You are the visual evidence extractor for a crypto/Web3 intelligence system.

The attached image is the PRIMARY SOURCE. Inspect the actual pixels carefully.
Do not describe it merely as "a screenshot", "a composite image", "a CoinGecko image", or "a user-provided image".
Extract the substantive information visible inside the image.

Read and report, where visible:
- exact text, headlines, captions, usernames and account names
- protocol, project, token and company names
- prices, market caps, volumes, percentages, dates and other numbers
- chart labels, axes, time ranges, trends, candles, lines and notable movements
- rankings, tables, balances, transaction data and dashboard metrics
- URLs, contract addresses, tickers and identifiers
- claims, announcements, quotes and calls to action shown in the image
- relationships between the visible elements
- unusual, surprising or potentially important details

For charts or dashboards, explain the actual visible data and direction of movement.
For screenshots of posts or announcements, transcribe the meaningful text and identify who/what is making the claim.
For multiple panels, inspect each panel and connect the information when appropriate.

Do not invent text that cannot be read.
Do not treat a visible claim as verified fact.
Clearly mark anything unreadable or uncertain.

User instruction:
{user_instruction or 'Identify what this image actually shows and extract the strongest evidence that should be researched for crypto/Web3 intelligence.'}

Return a concise but information-dense visual evidence packet.
The next model will use your output as evidence, so prioritize concrete facts over generic description.
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
        reasoning_effort="none",
        temperature=0.2,
        max_completion_tokens=1200,
    )

    return (
        response.choices[0].message.content or ""
    ).strip()
