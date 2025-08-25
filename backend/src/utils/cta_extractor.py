from __future__ import annotations

import re
import uuid
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from loguru import logger

from ..models.schemas import CTAType, ExtractedCTA


class CTAExtractor:
    """Enhanced CTA extractor that identifies and categorizes call-to-action elements."""
    
    # CTA-oriented keywords and patterns
    CTA_KEYWORDS = {
        'primary': [
            'buy', 'purchase', 'order', 'get started', 'start now', 'sign up', 'register',
            'subscribe', 'download', 'try', 'start free', 'book', 'schedule', 'contact',
            'call', 'email', 'request', 'apply', 'join', 'enroll', 'reserve', 'claim'
        ],
        'secondary': [
            'learn more', 'read more', 'see more', 'view', 'explore', 'discover',
            'find out', 'watch', 'listen', 'browse', 'search', 'compare'
        ],
        'urgency': [
            'now', 'today', 'limited', 'hurry', 'fast', 'quick', 'instant',
            'immediate', 'urgent', 'don\'t wait', 'act now', 'expires', 'deadline'
        ]
    }
    
    # CSS selectors that commonly indicate CTAs
    CTA_SELECTORS = [
        'button',
        'a[class*="btn"]',
        'a[class*="button"]',
        'a[class*="cta"]',
        'a[class*="call-to-action"]',
        'input[type="submit"]',
        'input[type="button"]',
        '[role="button"]',
        'a[class*="primary"]',
        'a[class*="secondary"]',
        '.btn, .button, .cta',
        '[data-track*="cta"]',
        '[data-event*="click"]'
    ]
    
    def __init__(self):
        self.seen_ctas: Set[str] = set()
        
    def extract_from_html(self, html: str, source_url: Optional[str] = None) -> List[ExtractedCTA]:
        """Extract CTAs from HTML content with enhanced context analysis."""
        soup = BeautifulSoup(html, 'lxml')
        ctas = []
        
        logger.info(f"Starting CTA extraction from HTML ({len(html)} chars)")
        
        # Extract from various element types
        ctas.extend(self._extract_button_ctas(soup, source_url))
        ctas.extend(self._extract_link_ctas(soup, source_url))
        ctas.extend(self._extract_form_ctas(soup, source_url))
        ctas.extend(self._extract_text_ctas(soup, source_url))
        
        # Deduplicate while preserving context
        unique_ctas = self._deduplicate_ctas(ctas)
        
        logger.info(f"Extracted {len(unique_ctas)} unique CTAs from HTML")
        return unique_ctas
    
    def extract_from_text(self, text: str, context: Optional[str] = None) -> List[ExtractedCTA]:
        """Extract CTAs from plain text content."""
        ctas = []
        
        # Split text into potential CTA segments
        sentences = re.split(r'[.!?]\s+', text)
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if self._is_potential_cta(sentence):
                cta = ExtractedCTA(
                    id=str(uuid.uuid4()),
                    original_text=sentence,
                    cta_type=CTAType.TEXT_CTA,
                    context=context or self._get_surrounding_context(sentences, i),
                    location=f"Text segment {i + 1}"
                )
                ctas.append(cta)
        
        logger.info(f"Extracted {len(ctas)} CTAs from text")
        return ctas
    
    def _extract_button_ctas(self, soup: BeautifulSoup, source_url: Optional[str]) -> List[ExtractedCTA]:
        """Extract CTAs from button elements."""
        ctas = []
        
        buttons = soup.find_all(['button', 'input'], type=['button', 'submit'])
        
        for button in buttons:
            text = self._get_element_text(button)
            if not text or not self._is_potential_cta(text):
                continue
                
            context = self._get_element_context(button)
            location = self._get_element_location(button)
            
            cta = ExtractedCTA(
                id=str(uuid.uuid4()),
                original_text=text,
                cta_type=CTAType.BUTTON if button.name == 'button' else CTAType.FORM_SUBMIT,
                context=context,
                location=location,
                url=source_url,
                html_element=str(button)[:500],
                css_selector=self._generate_css_selector(button)
            )
            ctas.append(cta)
        
        return ctas
    
    def _extract_link_ctas(self, soup: BeautifulSoup, source_url: Optional[str]) -> List[ExtractedCTA]:
        """Extract CTAs from link elements."""
        ctas = []
        
        # Find links that look like CTAs
        links = soup.find_all('a', href=True)
        
        for link in links:
            # Skip navigation and footer links
            if self._is_navigation_link(link):
                continue
                
            text = self._get_element_text(link)
            if not text or not self._is_potential_cta(text):
                continue
            
            # Check if link has CTA-like styling or classes
            if not self._has_cta_styling(link):
                continue
                
            context = self._get_element_context(link)
            location = self._get_element_location(link)
            
            cta = ExtractedCTA(
                id=str(uuid.uuid4()),
                original_text=text,
                cta_type=CTAType.LINK,
                context=context,
                location=location,
                url=source_url,
                html_element=str(link)[:500],
                css_selector=self._generate_css_selector(link)
            )
            ctas.append(cta)
        
        return ctas
    
    def _extract_form_ctas(self, soup: BeautifulSoup, source_url: Optional[str]) -> List[ExtractedCTA]:
        """Extract CTAs from form submission elements."""
        ctas = []
        
        forms = soup.find_all('form')
        
        for form in forms:
            # Find submit buttons within the form
            submit_elements = form.find_all(['input', 'button'], type=['submit', 'button'])
            
            for submit_elem in submit_elements:
                text = self._get_element_text(submit_elem)
                if not text:
                    continue
                
                # Get form context
                form_context = self._get_form_context(form)
                location = self._get_element_location(form)
                
                cta = ExtractedCTA(
                    id=str(uuid.uuid4()),
                    original_text=text,
                    cta_type=CTAType.FORM_SUBMIT,
                    context=form_context,
                    location=location,
                    url=source_url,
                    html_element=str(submit_elem)[:500],
                    css_selector=self._generate_css_selector(submit_elem)
                )
                ctas.append(cta)
        
        return ctas
    
    def _extract_text_ctas(self, soup: BeautifulSoup, source_url: Optional[str]) -> List[ExtractedCTA]:
        """Extract CTAs from text content that might not be in buttons/links."""
        ctas = []
        
        # Look for text patterns that suggest CTAs
        text_elements = soup.find_all(['p', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        
        for elem in text_elements:
            text = elem.get_text(strip=True)
            if not text or len(text) > 100:  # Skip very long text blocks
                continue
                
            # Check if this looks like a standalone CTA
            if self._is_standalone_cta(text):
                context = self._get_element_context(elem)
                location = self._get_element_location(elem)
                
                cta = ExtractedCTA(
                    id=str(uuid.uuid4()),
                    original_text=text,
                    cta_type=CTAType.TEXT_CTA,
                    context=context,
                    location=location,
                    url=source_url,
                    html_element=str(elem)[:500]
                )
                ctas.append(cta)
        
        return ctas
    
    def _is_potential_cta(self, text: str) -> bool:
        """Determine if text could be a CTA based on keywords and patterns."""
        if not text or len(text) < 2 or len(text) > 100:
            return False
            
        text_lower = text.lower().strip()
        
        # Check for CTA keywords
        all_keywords = (
            self.CTA_KEYWORDS['primary'] + 
            self.CTA_KEYWORDS['secondary'] + 
            self.CTA_KEYWORDS['urgency']
        )
        
        if any(keyword in text_lower for keyword in all_keywords):
            return True
        
        # Check for imperative patterns (action words)
        imperative_patterns = [
            r'^(get|start|try|buy|sign|join|call|email|book|download|subscribe)',
            r'(now|today)$',
            r'^[a-z]+ (free|now|today)',
            r'(click|tap) (here|now)',
        ]
        
        if any(re.search(pattern, text_lower) for pattern in imperative_patterns):
            return True
        
        return False
    
    def _is_standalone_cta(self, text: str) -> bool:
        """Check if text appears to be a standalone CTA (not part of regular content)."""
        text_lower = text.lower().strip()
        
        # Must contain CTA keywords
        if not self._is_potential_cta(text):
            return False
        
        # Should be relatively short and action-oriented
        if len(text.split()) > 8:
            return False
        
        # Should start with an action word or contain strong CTA patterns
        strong_patterns = [
            r'^(get|start|try|buy|sign|join|download|subscribe|call|email|book)',
            r'(free trial|get started|sign up|learn more|contact us)',
            r'(now|today|free)$'
        ]
        
        return any(re.search(pattern, text_lower) for pattern in strong_patterns)
    
    def _has_cta_styling(self, element: Tag) -> bool:
        """Check if element has CSS classes or styles that suggest it's a CTA."""
        classes = element.get('class', [])
        if not classes:
            classes = []
        
        class_string = ' '.join(classes).lower()
        
        cta_indicators = [
            'btn', 'button', 'cta', 'call-to-action', 'primary', 'secondary',
            'action', 'submit', 'download', 'signup', 'register', 'purchase'
        ]
        
        return any(indicator in class_string for indicator in cta_indicators)
    
    def _is_navigation_link(self, link: Tag) -> bool:
        """Check if link is likely navigation rather than a CTA."""
        text = self._get_element_text(link).lower()
        href = link.get('href', '').lower()
        classes = ' '.join(link.get('class', [])).lower()
        
        # Common navigation indicators
        nav_indicators = [
            'home', 'about', 'contact', 'blog', 'news', 'faq', 'help',
            'privacy', 'terms', 'policy', 'sitemap', 'menu', 'nav'
        ]
        
        if any(indicator in text for indicator in nav_indicators):
            return True
        
        if any(indicator in href for indicator in nav_indicators):
            return True
        
        if any(indicator in classes for indicator in nav_indicators):
            return True
        
        return False
    
    def _get_element_text(self, element: Tag) -> str:
        """Get the text content of an element, handling various cases."""
        if element.name == 'input':
            return element.get('value', '') or element.get('placeholder', '')
        
        return element.get_text(strip=True)
    
    def _get_element_context(self, element: Tag, context_length: int = 200) -> str:
        """Get surrounding context for an element."""
        # Try to find the containing section or parent with meaningful content
        for parent in element.parents:
            if parent.name in ['section', 'article', 'div', 'main']:
                # Get text from the parent, excluding the element itself
                parent_text = parent.get_text(strip=True)
                element_text = self._get_element_text(element)
                
                # Remove the element's text from context to avoid duplication
                context = parent_text.replace(element_text, '').strip()
                
                if len(context) > 50:  # Only use if we get meaningful context
                    return context[:context_length]
        
        # Fallback: get text from immediate siblings
        siblings = []
        for sibling in element.previous_siblings:
            if hasattr(sibling, 'get_text'):
                siblings.append(sibling.get_text(strip=True))
        
        for sibling in element.next_siblings:
            if hasattr(sibling, 'get_text'):
                siblings.append(sibling.get_text(strip=True))
        
        context = ' '.join(filter(None, siblings))
        return context[:context_length] if context else "No context available"