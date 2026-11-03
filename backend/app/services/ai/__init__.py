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
from .image_provider import DallEImageProvider, MockImageProvider


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
    api_key = os.getenv("OPENAI_API_KEY")
    provider_name = os.getenv("AI_IMAGE_PROVIDER", "dalle" if api_key else "mock").lower()
    if provider_name == "dalle" and api_key:
        return DallEImageProvider(api_key=api_key)
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
    "MockImageProvider",
    "get_research_provider",
    "get_text_provider",
    "get_image_provider",
]

