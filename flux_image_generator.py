import io
import os

from huggingface_hub import InferenceClient

from image_generator import BASE_PROMPT

FLUX_MODEL = os.getenv("FLUX_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")


def generate_flux_image(user_prompt):
    """Generate a square AkuWaziri comic visual with FLUX.1-schnell."""
    api_key = os.getenv("HF_TOKEN", "")
    if not api_key:
        raise RuntimeError("HF_TOKEN is not configured.")

    user_prompt = str(user_prompt or "").strip()
    if not user_prompt:
        raise RuntimeError("A generation prompt is required.")

    prompt = f"""
{BASE_PROMPT}

USER'S COMIC REQUEST:
{user_prompt}

Interpret the user's request as the subject and scene to illustrate.
Keep the visual language consistent with the fixed brand style.
Do not turn the result into a poster, photorealistic image, 3D render, or generic stock illustration.
Prioritize a strong comic composition, expressive characters and clear visual storytelling.
""".strip()

    client = InferenceClient(api_key=api_key, provider="auto", timeout=120)
    image = client.text_to_image(
        prompt,
        model=FLUX_MODEL,
        provider="auto",
    )

    if image is None:
        raise RuntimeError("The FLUX image model did not return an image.")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
