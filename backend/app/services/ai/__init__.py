"""AI Service integration factory and facade."""
import os
from typing import Optional

from .base import (
    BaseResearchProvider,
    BaseTextProvider,
    BaseImageProvider,
    ResearchResult,
    CaptionResult,
    ImageGenResult,
)
from .research_provider import WebResearchProvider, MockResearchProvider
from .text_provider import OpenAITextProvider, MockTextProvider
from .image_provider import DallEImageProvider, PexelsImageProvider, MockImageProvider, search_pexels_photos


def get_research_provider() -> BaseResearchProvider:
    provider_name = os.getenv("AI_RESEARCH_PROVIDER", "web").lower()
    if provider_name == "mock":
        return MockResearchProvider()
    return WebResearchProvider()


def get_text_provider() -> BaseTextProvider:
    api_key = os.getenv("OPENAI_API_KEY")
    provider_name = os.getenv("AI_TEXT_PROVIDER", "openai" if api_key else "mock").lower()
    if provider_name == "openai" and api_key:
        return OpenAITextProvider(api_key=api_key)
    return MockTextProvider()


def get_image_provider() -> BaseImageProvider:
    pexels_key = os.getenv("PEXELS_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    default_provider = "pexels" if pexels_key else ("dalle" if openai_key else "mock")
    provider_name = os.getenv("AI_IMAGE_PROVIDER", default_provider).lower()

    if provider_name == "pexels" and pexels_key:
        return PexelsImageProvider(api_key=pexels_key)
    if provider_name == "dalle" and openai_key:
        return DallEImageProvider(api_key=openai_key)
    if pexels_key and provider_name != "mock":
        return PexelsImageProvider(api_key=pexels_key)
    return MockImageProvider()


__all__ = [
    "BaseResearchProvider",
    "BaseTextProvider",
    "BaseImageProvider",
    "ResearchResult",
    "CaptionResult",
    "ImageGenResult",
    "WebResearchProvider",
    "MockResearchProvider",
    "OpenAITextProvider",
    "MockTextProvider",
    "DallEImageProvider",
    "PexelsImageProvider",
    "MockImageProvider",
    "search_pexels_photos",
    "get_research_provider",
    "get_text_provider",
    "get_image_provider",
]

