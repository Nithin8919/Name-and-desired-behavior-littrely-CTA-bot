from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from loguru import logger


def generate_unique_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    unique_id = str(uuid.uuid4())
    return f"{prefix}_{unique_id}" if prefix else unique_id


def normalize_text(text: str) -> str:
    """Normalize text for comparison and analysis."""
    if not text:
        return ""
    
    # Convert to lowercase and strip whitespace
    normalized = text.lower().strip()
    
    # Replace multiple whitespace with single space
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Remove special characters except basic punctuation
    normalized = re.sub(r'[^\w\s\-.,!?]', '', normalized)
    
    return normalized


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except Exception:
        return ""


def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two texts (0.0-1.0)."""
    if not text1 or not text2:
        return 0.0
    
    # Normalize texts
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)
    
    if norm1 == norm2:
        return 1.0
    
    # Simple word overlap similarity
    words1 = set(norm1.split())
    words2 = set(norm2.split())
    
    if not words1 and not words2:
        return 1.0
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union) if union else 0.0


def hash_content(content: str) -> str:
    """Create hash of content for deduplication."""
    return hashlib.md5(content.encode('utf-8')).hexdigest()[:12]


def validate_url_format(url: str) -> bool:
    """Validate URL format."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to maximum length with suffix."""
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """Extract keywords from text."""
    if not text:
        return []
    
    # Normalize text
    normalized = normalize_text(text)
    
    # Remove common stop words
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
        'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
        'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
    }
    
    words = [word for word in normalized.split() if len(word) > 2 and word not in stop_words]
    
    # Count word frequency
    word_freq = {}
    for word in words:
        word_freq[word] = word_freq.get(word, 0) + 1
    
    # Sort by frequency and return top keywords
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    
    return [word for word, freq in sorted_words[:max_keywords]]


def classify_cta_intent(text: str) -> str:
    """Classify the intent of a CTA text."""
    if not text:
        return "unknown"
    
    text_lower = text.lower()
    
    # Define intent patterns
    intent_patterns = {
        "purchase": ["buy", "purchase", "order", "checkout", "shop", "add to cart"],
        "signup": ["sign up", "register", "join", "create account", "get started"],
        "subscription": ["subscribe", "sign up", "newsletter", "updates"],
        "download": ["download", "get", "grab", "access"],
        "trial": ["free trial", "try", "test", "demo"],
        "contact": ["contact", "call", "email", "reach out", "get in touch"],
        "learn": ["learn more", "read more", "see more", "find out", "discover"],
        "navigate": ["view", "browse", "explore", "see", "check out"]
    }
    
    # Check for intent patterns
    for intent, patterns in intent_patterns.items():
        if any(pattern in text_lower for pattern in patterns):
            return intent
    
    return "action"  # Default for action-oriented CTAs


def assess_cta_urgency(text: str) -> int:
    """Assess urgency level of CTA text (1-10 scale)."""
    if not text:
        return 1
    
    text_lower = text.lower()
    urgency_score = 1
    
    # High urgency indicators
    high_urgency = ["now", "today", "immediately", "urgent", "hurry", "fast", "quick", "instant"]
    if any(word in text_lower for word in high_urgency):
        urgency_score += 4
    
    # Medium urgency indicators  
    medium_urgency = ["limited", "expires", "deadline", "soon", "don't wait", "act"]
    if any(word in text_lower for word in medium_urgency):
        urgency_score += 2
    
    # Time-based urgency
    time_patterns = ["24 hours", "this week", "today only", "ends soon"]
    if any(pattern in text_lower for pattern in time_patterns):
        urgency_score += 3
    
    # Scarcity indicators
    scarcity_words = ["only", "last", "few left", "limited", "exclusive"]
    if any(word in text_lower for word in scarcity_words):
        urgency_score += 2
    
    return min(10, urgency_score)


def format_confidence_score(score: float) -> str:
    """Format confidence score for display."""
    if score >= 0.9:
        return "Very High"
    elif score >= 0.8:
        return "High"
    elif score >= 0.7:
        return "Good"
    elif score >= 0.6:
        return "Medium"
    elif score >= 0.5:
        return "Low"
    else:
        return "Very Low"


def calculate_improvement_potential(original: str, optimized: str) -> Dict[str, Any]:
    """Calculate improvement metrics between original and optimized CTA."""
    metrics = {
        "length_change": len(optimized.split()) - len(original.split()),
        "character_change": len(optimized) - len(original),
        "action_words_added": 0,
        "specificity_improved": False,
        "urgency_added": False
    }
    
    # Count action words
    action_words = ["get", "start", "try", "buy", "join", "download", "subscribe", "book", "call"]
    
    original_actions = sum(1 for word in action_words if word in original.lower())
    optimized_actions = sum(1 for word in action_words if word in optimized.lower())
    
    metrics["action_words_added"] = optimized_actions - original_actions
    
    # Check for specificity improvement
    vague_words = ["click here", "learn more", "read more", "see more", "continue"]
    has_vague_original = any(phrase in original.lower() for phrase in vague_words)
    has_vague_optimized = any(phrase in optimized.lower() for phrase in vague_words)
    
    metrics["specificity_improved"] = has_vague_original and not has_vague_optimized
    
    # Check for urgency addition
    original_urgency = assess_cta_urgency(