"""Base interfaces and data structures for AI providers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CitationItem:
    url: Optional[str]
    title: Optional[str]
    excerpt: Optional[str]
    published_at: Optional[str] = None


@dataclass
class ResearchResult:
    summary: str
    citations: List[CitationItem] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    tokens_used: int = 150
    cost_usd: float = 0.002


@dataclass
class CaptionResult:
    caption: str
    hashtags: List[str] = field(default_factory=list)
    tokens_used: int = 200
    cost_usd: float = 0.004


@dataclass
class ImageGenResult:
    image_bytes: bytes
    mime_type: str = "image/png"
    prompt_used: str = ""
    cost_usd: float = 0.04


class BaseResearchProvider(ABC):
    @abstractmethod
    def research(self, topic: str, source_url: Optional[str] = None) -> ResearchResult:
        """Extract citations and synthesize research summary."""
        pass


class BaseTextProvider(ABC):
    @abstractmethod
    def generate_caption(
        self,
        topic: str,
        research_summary: Optional[str] = None,
        tone: str = "professional",
        target_platforms: Optional[List[str]] = None,
        language: str = "english",
    ) -> CaptionResult:
        """Generate engaging platform-tailored caption and hashtags."""
        pass


class BaseImageProvider(ABC):
    @abstractmethod
    def generate_image(self, prompt: str, style: str = "modern") -> ImageGenResult:
        """Generate high quality marketing imagery."""
        pass

