"""Provider adapters. Keep adapters thin and preserve provider-native raw responses."""
from .ollama import OllamaAdapter
from .reference import DevelopmentReferenceAgent

__all__ = ["DevelopmentReferenceAgent", "OllamaAdapter"]
