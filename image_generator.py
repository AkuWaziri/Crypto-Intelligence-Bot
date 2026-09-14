import base64
import os

from google import genai


IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")

BASE_PROMPT = """
New comic visual on a grey #3e3e40 outer-layer background.
Use dynamic colours for the artwork comic panels; choose any palette that fits the subject and mood.
The comic panel should stretch to the extreme edges of the outer-layer background, with no unnecessary margins inside the outer layer.
Colourize the art when it fits the comic and improves the visual storytelling.
Hand-drawn digital comic, bold, clean hand-drawn digital comic, bold thick lines, expressive characters, strong readable composition, polished comic illustration.
Add @akuwazir at the bottom-right side in small black handwritten writing.
Square 1:1 composition.
""".strip()


def generate_image(user_prompt):
    """Generate a comic visual. Prefix with 'flux' to use FLUX; otherwise use Gemini."""
    user_prompt = str(user_prompt or "").strip()
    if not user_prompt:
        raise RuntimeError("A generation prompt is required.")

    parts = user_prompt.split(maxsplit=1)
    provider = parts[0].lower() if parts else ""
    if provider == "flux":
        if len(parts) == 1 or not parts[1].strip():
            raise RuntimeError("A generation prompt is required after 'flux'.")
        from flux_image_generator import generate_flux_image
        return generate_flux_image(parts[1].strip())

    if provider == "gemini":
        if len(parts) == 1 or not parts[1].strip():
            raise RuntimeError("A generation prompt is required after 'gemini'.")
        user_prompt = parts[1].strip()

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    prompt = f"""
{BASE_PROMPT}

USER'S COMIC REQUEST:
{user_prompt}

Interpret the user's request as the subject and scene to illustrate.
Keep the visual language consistent with the base brand style.
Do not turn the result into a poster, photorealistic image, 3D render, or generic stock illustration.
Prioritize a strong comic composition and clear visual storytelling.
""".strip()

    client = genai.Client(api_key=api_key)
    interaction = client.interactions.create(
        model=IMAGE_MODEL,
        input=prompt,
        response_format={
            "type": "image",
            "mime_type": "image/jpeg",
            "aspect_ratio": "1:1",
            "image_size": "1K",
        },
    )

    output_image = interaction.output_image
    if not output_image or not output_image.data:
        raise RuntimeError("The image model did not return an image.")

    return base64.b64decode(output_image.data)
