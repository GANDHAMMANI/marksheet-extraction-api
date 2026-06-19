import base64
import io

from groq import AsyncGroq
from openai import AsyncOpenAI
from PIL import Image

from app.config import settings
from app.core.exceptions import LLMExtractionError

_groq = AsyncGroq(api_key=settings.groq_api_key)

_nvidia = AsyncOpenAI(
    api_key=settings.nvidia_api_key,
    base_url="https://integrate.api.nvidia.com/v1",
    max_retries=0,
)


async def call_scout(images: list[Image.Image], prompt: str) -> str:
    content = [{"type": "text", "text": prompt}]
    content += [{"type": "image_url", "image_url": {"url": _to_data_uri(img)}} for img in images]
    try:
        response = await _groq.chat.completions.create(
            model=settings.groq_model_name,
            messages=[{"role": "user", "content": content}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise LLMExtractionError(f"Scout failed: {exc}")
    message = response.choices[0].message.content
    if not message:
        raise LLMExtractionError("Empty response from Scout")
    return message


async def call_minimax(images: list[Image.Image], prompt: str) -> str:
    content = [{"type": "text", "text": prompt}]
    content += [{"type": "image_url", "image_url": {"url": _to_data_uri(img)}} for img in images]
    try:
        response = await _nvidia.chat.completions.create(
            model=settings.nvidia_model_name,
            messages=[{"role": "user", "content": content}],
            temperature=0.1,
            max_tokens=8192,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise LLMExtractionError(f"MiniMax failed: {exc}")
    message = response.choices[0].message.content
    if not message:
        raise LLMExtractionError("Empty response from MiniMax")
    return message


def _to_data_uri(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"