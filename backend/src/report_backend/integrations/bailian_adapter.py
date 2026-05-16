from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

import httpx

from ..core.config import Settings


class BailianAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return bool(self.settings.dashscope_api_key)

    async def search(self, query: str, count: int = 5) -> list[str]:
        if not self.enabled:
            raise RuntimeError("DASHSCOPE_API_KEY is not configured, skipping web search.")

        url = "https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/mcp"
        headers = {
            "Authorization": f"Bearer {self.settings.dashscope_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "bailian_web_search",
                "arguments": {"query": query, "count": count},
            },
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        raw_text = data["result"]["content"][0]["text"]
        return [line.strip("- ").strip() for line in raw_text.splitlines() if line.strip()][:count]

    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        if not self.enabled:
            raise RuntimeError("DASHSCOPE_API_KEY is not configured, model calls are disabled.")

        url = f"{self.settings.qwen_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.dashscope_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.qwen_model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):
            text_parts = [item.get("text", "") for item in content if item.get("type") == "text"]
            return "\n".join(part for part in text_parts if part).strip()
        return str(content).strip()

    async def vision_describe_images(
        self,
        *,
        title: str,
        extra_info: str,
        section_title: str,
        section_text: str,
        image_paths: list[str],
    ) -> str:
        if not self.enabled:
            raise RuntimeError("DASHSCOPE_API_KEY is not configured, model calls are disabled.")

        user_content: list[dict[str, object]] = [
            {
                "type": "text",
                "text": (
                    "You are extracting factual visual evidence for an experiment report.\n"
                    f"Experiment title: {title}\n"
                    f"User notes: {extra_info or '[none]'}\n"
                    f"Section: {section_title}\n"
                    f"Existing extracted text: {section_text or '[none]'}\n\n"
                    "Describe what is visible in the provided images. Focus on labels, charts, diagrams, "
                    "measurements, interfaces, and any experiment-relevant structure. Do not invent facts."
                ),
            }
        ]
        for image_path in image_paths:
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": _image_path_to_data_url(image_path)},
                }
            )

        payload = {
            "model": self.settings.qwen_vision_model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": "Return a concise markdown-ready visual summary."},
                {"role": "user", "content": user_content},
            ],
        }
        data = await self._post_chat(payload, timeout=90.0)
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):
            text_parts = [item.get("text", "") for item in content if item.get("type") == "text"]
            return "\n".join(part for part in text_parts if part).strip()
        return str(content).strip()

    async def _post_chat(self, payload: dict[str, object], *, timeout: float) -> dict[str, object]:
        url = f"{self.settings.qwen_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.dashscope_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()


def fallback_synthesize(
    *,
    title: str,
    extra_info: str,
    extracted_md: str,
    search_results: list[str],
    template_text: str,
) -> str:
    context_chunks = [
        f"Experiment title: {title}",
        f"User notes: {extra_info or '[User input needed: experiment details]'}",
        f"Template outline: {template_text or '[User input needed: template outline]'}",
    ]
    if extracted_md:
        context_chunks.append(f"Local material summary: {extracted_md[:2400]}")
    if search_results:
        context_chunks.append("Web summary: " + "; ".join(search_results[:5]))
    return "\n\n".join(context_chunks)


def _image_path_to_data_url(image_path: str) -> str:
    path = Path(image_path)
    mime_type, _ = mimetypes.guess_type(path.name)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type or 'application/octet-stream'};base64,{encoded}"
