from __future__ import annotations

import re
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from loguru import logger


class HTMLParser:
    """Enhanced HTML parser for CTA extraction and analysis."""
    
    def __init__(self):
        self.processed_elements: Set[str] = set()
    
    def clean_html(self, html: str) -> str:
        """Clean HTML content for better parsing."""
        soup = BeautifulSoup(html, 'lxml')
        
        # Remove unwanted elements
        unwanted_tags = ['script', 'style', 'noscript', 'meta', 'link']
        for tag_name in unwanted_tags:
            for tag in soup.find_all(tag_name):
                tag.decompose()
        
        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, type(soup.new_tag('').string))):
            comment.extract()
        
        return str(soup)
    
    def extract_semantic_sections(self, html: str) -> Dict[str, BeautifulSoup]:
        """Extract semantic sections from HTML."""
        soup = BeautifulSoup(html, 'lxml')
        sections = {}
        
        # Define semantic section mapping
        section_selectors = {
            'header': ['header', '[role="banner"]', '.header', '.site-header'],
            'navigation': ['nav', '[role="navigation"]', '.nav', '.menu', '.navbar'],
            'hero': ['.hero', '.banner', '.jumbotron', '.hero-section'],
            'main': ['main', '[role="main"]', '.main', '.content'],
            'sidebar': ['aside', '[role="complementary"]', '.sidebar', '.aside'],
            'footer': ['footer', '[role="contentinfo"]', '.footer', '.site-footer'],
            'forms': ['form', '.form', '.contact-form', '.signup-form'],
            'pricing': ['.pricing', '.plans', '.pricing-table'],
            'testimonials': ['.testimonials', '.reviews', '.testimonial'],
            'cta_sections': ['.cta', '.call-to-action', '.action-section']
        }
        
        for section_name, selectors in section_selectors.items():
            section_elements = []
            
            for selector in selectors:
                elements = soup.select(selector)
                section_elements.extend(elements)
            
            if section_elements:
                # Create a new soup with all elements from this section
                section_soup = BeautifulSoup('', 'lxml')
                for element in section_elements:
                    section_soup.append(element)
                
                sections[section_name] = section_soup
        
        logger.debug(f"Extracted {len(sections)} semantic sections")
        return sections
    
    def find_interactive_elements(self, soup: BeautifulSoup) -> List[Dict[str, any]]:
        """Find all interactive elements that could be CTAs."""
        interactive_elements = []
        
        # Buttons
        buttons = soup.find_all(['button', 'input'], type=['button', 'submit'])
        for button in buttons:
            element_info = self._analyze_element(button, 'button')
            if element_info:
                interactive_elements.append(element_info)
        
        # Links that look like buttons
        button_like_links = soup.find_all('a', class_=re.compile(r'btn|button|cta', re.I))
        for link in button_like_links:
            element_info = self._analyze_element(link, 'button_link')
            if element_info:
                interactive_elements.append(element_info)
        
        # Form submits
        forms = soup.find_all('form')
        for form in forms:
            submit_elements = form.find_all(['input', 'button'], type=['submit', 'button'])
            for submit_elem in submit_elements:
                element_info = self._analyze_element(submit_elem, 'form_submit', parent_form=form)
                if element_info:
                    interactive_elements.append(element_info)
        
        # Clickable divs/spans with event handlers
        clickable_divs = soup.find_all(['div', 'span'], 
                                     attrs={'onclick': True})
        clickable_divs.extend(soup.find_all(['div', 'span'], 
                                          class_=re.compile(r'click|tap|select', re.I)))
        
        for div in clickable_divs:
            element_info = self._analyze_element(div, 'clickable_div')
            if element_info:
                interactive_elements.append(element_info)
        
        logger.debug(f"Found {len(interactive_elements)} interactive elements")
        return interactive_elements
    
    def _analyze_element(self, element: Tag, element_type: str, parent_form: Optional[Tag] = None) -> Optional[Dict[str, any]]:
        """Analyze an individual element for CTA potential."""
        # Get element text
        text = self._get_element_text(element)
        if not text or len(text) < 1:
            return None
        
        # Skip if already processed (based on text and position)
        element_key = f"{text}_{element.get('id', '')}_{element.get('class', '')}"
        if element_key in self.processed_elements:
            return None
        
        self.processed_elements.add(element_key)
        
        # Analyze element properties
        analysis = {
            'element': element,
            'text': text,
            'type': element_type,
            'html_tag': element.name,
            'classes': element.get('class', []),
            'id': element.get('id', ''),
            'attributes': dict(element.attrs),
            'context': self._get_element_context(element),
            'visual_prominence': self._assess_visual_prominence(element),
            'semantic_role': self._determine_semantic_role(element),
            'cta_likelihood': self._calculate_cta_likelihood(element, text)
        }
        
        # Add form context if applicable
        if parent_form:
            analysis['form_context'] = self._analyze_form_context(parent_form)
        
        return analysis
    
    def _get_element_text(self, element: Tag) -> str:
        """Extract text from element handling various input types."""
        if element.name == 'input':
            return (element.get('value') or 
                   element.get('placeholder') or 
                   element.get('aria-label') or 
                   element.get('title') or '')
        
        # For other elements, get text content
        text = element.get_text(strip=True)
        
        # Also check for aria-label and title attributes
        if not text:
            text = (element.get('aria-label') or 
                   element.get('title') or 
                   element.get('alt') or '')
        
        return text.strip()
    
    def _get_element_context(self, element: Tag, max_length: int = 300) -> str:
        """Get surrounding context for the element."""
        context_parts = []
        
        # Check parent elements for context
        for parent in element.parents:
            if parent.name in ['section', 'article', 'div', 'main', 'header', 'footer']:
                # Get heading within parent
                heading = parent.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                if heading:
                    context_parts.append(f"Section: {heading.get_text(strip=True)}")
                    break
        
        # Get nearby text
        nearby_text = []
        
        # Check previous siblings
        for sibling in element.previous_siblings:
            if hasattr(sibling, 'get_text'):
                text = sibling.get_text(strip=True)
                if text and len(text) > 10:
                    nearby_text.append(text[:100])
                    break
        
        # Check next siblings  
        for sibling in element.next_siblings:
            if hasattr(sibling, 'get_text'):
                text = sibling.get_text(strip=True)
                if text and len(text) > 10:
                    nearby_text.append(text[:100])
                    break
        
        if nearby_text:
            context_parts.append(" | ".join(nearby_text))
        
        context = " | ".join(context_parts)
        return context[:max_length] if context else "No context available"
    
    def _assess_visual_prominence(self, element: Tag) -> int:
        """Assess how visually prominent an element likely is (1-10 scale)."""
        prominence = 5  # Base score
        
        classes = ' '.join(element.get('class', [])).lower()
        
        # High prominence indicators
        if any(keyword in classes for keyword in ['primary', 'main', 'hero', 'featured']):
            prominence += 2
        
        # Button styling indicators
        if any(keyword in classes for keyword in ['btn', 'button', 'cta']):
            prominence += 1
        
        # Size indicators
        if any(keyword in classes for keyword in ['large', 'big', 'xl', 'lg']):
            prominence += 1
        elif any(keyword in classes for keyword in ['small', 'sm', 'xs', 'mini']):
            prominence -= 1
        
        # Color indicators (assume these are more prominent)
        if any(keyword in classes for keyword in ['red', 'orange', 'green', 'blue', 'primary']):
            prominence += 1
        
        # Position indicators
        if any(keyword in classes for keyword in ['top', 'header', 'above-fold']):
            prominence += 1
        
        return max(1, min(10, prominence))
    
    def _determine_semantic_role(self, element: Tag) -> str:
        """Determine the semantic role of the element."""
        # Check explicit ARIA role
        role = element.get('role')
        if role:
            return role
        
        # Infer from element type and classes
        classes = ' '.join(element.get('class', [])).lower()
        
        if element.name == 'button' or 'btn' in classes or 'button' in classes:
            return 'button'
        elif element.name == 'a':
            return 'link'
        elif element.get('type') == 'submit':
            return 'submit'
        elif 'nav' in classes or 'menu' in classes:
            return 'navigation'
        elif 'cta' in classes or 'call-to-action' in classes:
            return 'call-to-action'
        else:
            return 'interactive'
    
    def _calculate_cta_likelihood(self, element: Tag, text: str) -> float:
        """Calculate likelihood that this element is a CTA (0.0-1.0)."""
        likelihood = 0.3  # Base likelihood
        
        text_lower = text.lower()
        classes = ' '.join(element.get('class', [])).lower()
        
        # Text-based scoring
        cta_keywords = [
            'buy', 'purchase', 'order', 'get started', 'sign up', 'subscribe',
            'download', 'try', 'start', 'join', 'contact', 'call', 'book'
        ]
        
        strong_cta_words = sum(1 for keyword in cta_keywords if keyword in text_lower)
        if strong_cta_words > 0:
            likelihood += 0.3 * strong_cta_words
        
        # Element type scoring
        if element.name == 'button':
            likelihood += 0.2
        elif element.get('type') == 'submit':
            likelihood += 0.25
        
        # Class-based scoring
        if 'cta' in classes or 'call-to-action' in classes:
            likelihood += 0.3
        elif 'btn' in classes or 'button' in classes:
            likelihood += 0.2
        
        # Urgency indicators
        urgency_words = ['now', 'today', 'limited', 'hurry', 'fast', 'quick']
        if any(word in text_lower for word in urgency_words):
            likelihood += 0.1
        
        # Length penalty for very long text (probably not a CTA)
        if len(text.split()) > 8:
            likelihood -= 0.2
        
        return max(0.0, min(1.0, likelihood))
    
    def _analyze_form_context(self, form: Tag) -> Dict[str, any]:
        """Analyze form context for better CTA understanding."""
        form_analysis = {
            'action': form.get('action', ''),
            'method': form.get('method', 'GET').upper(),
            'fields': [],
            'field_count': 0,
            'has_required_fields': False,
            'form_type': 'unknown'
        }
        
        # Analyze form fields
        fields = form.find_all(['input', 'select', 'textarea'])
        form_analysis['field_count'] = len(fields)
        
        for field in fields:
            field_type = field.get('type', 'text')
            field_name = field.get('name', '')
            field_placeholder = field.get('placeholder', '')
            is_required = field.has_attr('required')
            
            if is_required:
                form_analysis['has_required_fields'] = True
            
            form_analysis['fields'].append({
                'type': field_type,
                'name': field_name,
                'placeholder': field_placeholder,
                'required': is_required
            })
        
        # Determine form type based on fields
        field_types = [field.get('type', 'text') for field in fields]
        field_names = [field.get('name', '').lower() for field in fields]
        
        if 'email' in field_types or any('email' in name for name in field_names):
            if any(word in ' '.join(field_names) for word in ['password', 'login']):
                form_analysis['form_type'] = 'login'
            else:
                form_analysis['form_type'] = 'signup'
        elif any(word in ' '.join(field_names) for word in ['search', 'query']):
            form_analysis['form_type'] = 'search'
        elif any(word in ' '.join(field_names) for word in ['contact', 'message', 'inquiry']):
            form_analysis['form_type'] = 'contact'
        elif len(fields) > 5:
            form_analysis['form_type'] = 'detailed_form'
        
        return form_analysis
    
    def extract_links_with_context(self, html: str, base_url: str) -> List[Dict[str, any]]:
        """Extract all links with their context for crawling prioritization."""
        soup = BeautifulSoup(html, 'lxml')
        links_with_context = []
        
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            
            # Skip non-HTTP links
            if href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                continue
            
            # Convert to absolute URL
            absolute_url = urljoin(base_url, href)
            
            # Only include same-domain links
            if urlparse(absolute_url).netloc != urlparse(base_url).netloc:
                continue
            
            link_info = {
                'url': absolute_url,
                'text': link.get_text(strip=True),
                'title': link.get('title', ''),
                'classes': link.get('class', []),
                'context': self._get_element_context(link),
                'priority_score': self._calculate_link_priority(link, absolute_url)
            }
            
            links_with_context.append(link_info)
        
        # Sort by priority score
        links_with_context.sort(key=lambda x: x['priority_score'], reverse=True)
        
        return links_with_context
    
    def _calculate_link_priority(self, link: Tag, url: str) -> int:
        """Calculate priority score for link crawling."""
        priority = 0
        
        text = link.get_text(strip=True).lower()
        url_lower = url.lower()
        classes = ' '.join(link.get('class', [])).lower()
        
        # High priority URL patterns
        high_priority_patterns = [
            'pricing', 'signup', 'register', 'contact', 'demo', 'trial',
            'buy', 'purchase', 'order', 'subscribe', 'join'
        ]
        
        for pattern in high_priority_patterns:
            if pattern in url_lower or pattern in text:
                priority += 10
                break
        
        # Medium priority patterns
        medium_priority_patterns = [
            'about', 'product', 'service', 'feature', 'solution',
            'how-it-works', 'benefits'
        ]
        
        for pattern in medium_priority_patterns:
            if pattern in url_lower or pattern in text:
                priority += 5
                break
        
        # Button-like styling
        if any(keyword in classes for keyword in ['btn', 'button', 'cta']):
            priority += 8
        
        # Navigation penalty (these are usually less important for CTA analysis)
        if any(keyword in classes for keyword in ['nav', 'menu', 'breadcrumb']):
            priority -= 5
        
        return priority