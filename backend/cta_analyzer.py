import os, json, re, time, requests
from typing import Dict, Any, List, Optional
from pathlib import Path
from PIL import Image
import easyocr
from openai import OpenAI
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

# Load environment variables
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(), override=False)
except Exception:
    pass

# CTA detection patterns
CTA_PATTERNS = {
    "action_verbs": {
        "get", "start", "try", "book", "buy", "download", "sign", "register", "join",
        "subscribe", "contact", "call", "learn", "see", "view", "watch", "play",
        "claim", "grab", "save", "upgrade", "unlock", "access", "discover", "explore",
        "request", "order", "checkout", "add", "select", "choose", "pick", "find",
        "create", "build", "make", "generate", "calculate", "estimate", "compare"
    },
    "vague_words": {
        "more", "here", "now", "today", "click", "submit", "go", "next", "continue",
        "proceed", "enter", "visit", "check", "read", "info", "details"
    }
}

LITERAL_OPTIMIZATION_PROMPT = """You are a conversion rate optimization expert specializing in making CTAs literally describe the required user behavior.

CORE MISSION: Transform vague CTAs into specific, behavior-explicit alternatives that tell users EXACTLY what to do.

KEY PRINCIPLES:
1. LITERAL BEHAVIOR: Spell out the exact action needed
2. ACTION-ORIENTED: Use strong, specific action verbs
3. VALUE-CLEAR: Make the benefit immediately obvious
4. SPECIFICITY: Avoid vague language like "more", "here", "now"

TRANSFORMATION EXAMPLES:
❌ "Learn More" → ✅ "Watch Our 3-Minute Product Demo"
❌ "Click Here" → ✅ "Download Free Marketing Guide" 
❌ "Get Started" → ✅ "Create Your Free Account in 30 Seconds"
❌ "Submit" → ✅ "Get My Personalized Quote Now"
❌ "Try Now" → ✅ "Start Your 14-Day Free Trial"
❌ "Sign Up" → ✅ "Join 50,000+ Marketing Professionals"

SCORING CRITERIA (1-10):
- 1-3: Very vague ("Click Here", "More Info")
- 4-6: Somewhat specific ("Sign Up", "Learn More") 
- 7-8: Good specificity ("Start Free Trial")
- 9-10: Perfectly literal ("Enter Email to Download Guide")

CTAs TO ANALYZE:
{cta_list}

STRICT JSON OUTPUT REQUIRED:
{{
  "optimizations": [
    {{
      "original_text": "Learn More",
      "literalness_score": 2,
      "optimized_text": "Watch Our 5-Minute Product Demo",
      "improvement_rationale": "Specifies exact action (watch) and time commitment (5 minutes) instead of vague 'learn more'",
      "literalness_improvement": 8,
      "action_words_added": ["Watch"],
      "specificity_added": "5-Minute Product Demo",
      "urgency_level": 6,
      "confidence_score": 0.9
    }}
  ],
  "summary": {{
    "total_analyzed": 5,
    "avg_original_literalness": 3.2,
    "avg_improved_literalness": 8.1,
    "total_improvement": 4.9
  }}
}}"""

class CTALiteralAnalyzer:
    """Analyzes and optimizes CTAs for literal, action-oriented language"""
    
    def __init__(self):
        self.api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        if not self.api_key:
            raise RuntimeError("Missing OPENAI_API_KEY environment variable")
            
        self.client = OpenAI(api_key=self.api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.ocr = easyocr.Reader(['en'], gpu=False, verbose=False)
        
        print("🎯 CTA Literal Analyzer initialized")
        
    def analyze_url(self, url: str, max_pages: int = 5) -> Dict[str, Any]:
        """Extract and analyze CTAs from website URL"""
        try:
            print(f"🔍 Extracting CTAs from URL: {url}")
            
            # Extract CTAs from website
            ctas = self._extract_ctas_from_url(url, max_pages)
            
            if not ctas:
                return {
                    'error': 'No CTAs found on the website',
                    'extracted_ctas': [],
                    'optimizations': []
                }
                
            # Analyze with OpenAI
            optimizations = self._analyze_cta_literalness(ctas)
            
            return {
                'extracted_ctas': ctas,
                'optimizations': optimizations,
                'meta': {
                    'source': 'url',
                    'url': url,
                    'total_ctas': len(ctas),
                    'pages_crawled': min(max_pages, 5)
                }
            }
            
        except Exception as e:
            print(f"❌ URL analysis error: {e}")
            return {'error': str(e)}
            
    def analyze_image(self, image_path: str) -> Dict[str, Any]:
        """Extract and analyze CTAs from image using OCR"""
        try:
            print(f"📷 Analyzing image: {image_path}")
            
            # Extract text using OCR
            ocr_results = self.ocr.readtext(image_path)
            texts = [result[1] for result in ocr_results if result[2] > 0.5]  # confidence > 50%
            
            if not texts:
                return {
                    'error': 'No text found in image',
                    'extracted_ctas': [],
                    'optimizations': []
                }
                
            # Filter for potential CTAs
            ctas = self._filter_potential_ctas(texts)
            
            if not ctas:
                return {
                    'error': 'No CTAs detected in image text',
                    'extracted_ctas': [],
                    'optimizations': []
                }
                
            # Convert to CTA objects
            cta_objects = [
                {
                    'id': f'img_cta_{i}',
                    'text': cta,
                    'type': 'image_text',
                    'context': 'Extracted from image',
                    'location': 'image'
                }
                for i, cta in enumerate(ctas)
            ]
            
            # Analyze with OpenAI
            optimizations = self._analyze_cta_literalness(cta_objects)
            
            return {
                'extracted_ctas': cta_objects,
                'optimizations': optimizations,
                'meta': {
                    'source': 'image',
                    'image_path': image_path,
                    'total_texts_found': len(texts),
                    'total_ctas': len(cta_objects)
                }
            }
            
        except Exception as e:
            print(f"❌ Image analysis error: {e}")
            return {'error': str(e)}
            
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """Analyze CTAs in provided text"""
        try:
            print(f"📝 Analyzing text input")
            
            # Split text and find potential CTAs
            potential_ctas = self._filter_potential_ctas(text.split('\n'))
            
            if not potential_ctas:
                # If no obvious CTAs, treat whole text as potential CTA
                potential_ctas = [text.strip()]
                
            # Convert to CTA objects
            cta_objects = [
                {
                    'id': f'text_cta_{i}',
                    'text': cta.strip(),
                    'type': 'text_input',
                    'context': 'Direct text input',
                    'location': 'user_input'
                }
                for i, cta in enumerate(potential_ctas) if cta.strip()
            ]
            
            # Analyze with OpenAI
            optimizations = self._analyze_cta_literalness(cta_objects)
            
            return {
                'extracted_ctas': cta_objects,
                'optimizations': optimizations,
                'meta': {
                    'source': 'text',
                    'total_ctas': len(cta_objects)
                }
            }
            
        except Exception as e:
            print(f"❌ Text analysis error: {e}")
            return {'error': str(e)}
            
    def _extract_ctas_from_url(self, url: str, max_pages: int = 5) -> List[Dict[str, Any]]:
        """Extract CTAs from website"""
        ctas = []
        pages_crawled = 0
        
        try:
            # Start with main page
            response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            
            # Extract CTAs from current page
            page_ctas = self._extract_ctas_from_page(soup, url, base_url)
            ctas.extend(page_ctas)
            pages_crawled += 1
            
            print(f"Found {len(page_ctas)} CTAs on main page")
            
            # Get additional pages if requested (simplified for speed)
            if max_pages > 1:
                links = [urljoin(base_url, a.get('href', '')) for a in soup.find_all('a', href=True)]
                internal_links = [link for link in links if urlparse(link).netloc == urlparse(base_url).netloc][:max_pages-1]
                
                for link in internal_links:
                    try:
                        response = requests.get(link, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
                        response.raise_for_status()
                        soup = BeautifulSoup(response.content, 'html.parser')
                        page_ctas = self._extract_ctas_from_page(soup, link, base_url)
                        ctas.extend(page_ctas)
                        pages_crawled += 1
                        print(f"Found {len(page_ctas)} CTAs on {link}")
                    except:
                        continue
                        
            return ctas[:20]  # Limit to 20 CTAs for analysis speed
            
        except Exception as e:
            print(f"Error crawling {url}: {e}")
            return []
            
    def _extract_ctas_from_page(self, soup: BeautifulSoup, page_url: str, base_url: str) -> List[Dict[str, Any]]:
        """Extract CTAs from a single page"""
        ctas = []
        
        # CTA selectors (buttons, links, forms)
        selectors = [
            'button', 'input[type="submit"]', 'input[type="button"]',
            'a[class*="btn"]', 'a[class*="cta"]', 'a[class*="button"]',
            '.cta', '.call-to-action', '[data-track*="cta"]'
        ]
        
        for i, selector in enumerate(selectors):
            elements = soup.select(selector)
            
            for j, element in enumerate(elements):
                text = element.get_text().strip()
                
                if text and len(text) < 100 and self._is_potential_cta(text):
                    context = self._get_element_context(element)
                    
                    cta = {
                        'id': f'url_cta_{i}_{j}',
                        'text': text,
                        'type': element.name or 'unknown',
                        'context': context,
                        'location': page_url,
                        'element_class': element.get('class', []),
                        'element_id': element.get('id', '')
                    }
                    
                    # Avoid duplicates
                    if not any(existing['text'].lower() == text.lower() for existing in ctas):
                        ctas.append(cta)
                        
        return ctas
        
    def _get_element_context(self, element) -> str:
        """Get surrounding context of CTA element"""
        try:
            parent = element.parent
            if parent:
                context_text = parent.get_text().strip()
                # Clean and limit context
                context = re.sub(r'\s+', ' ', context_text)[:200]
                return context
        except:
            pass
        return "No context available"
        
    def _is_potential_cta(self, text: str) -> bool:
        """Check if text looks like a CTA"""
        text_lower = text.lower()
        
        # Check for action verbs
        has_action_verb = any(verb in text_lower for verb in CTA_PATTERNS["action_verbs"])
        
        # Check for common CTA patterns
        cta_patterns = [r'\b(get|start|try|download|sign|join|buy)\b', r'\b(free|now|today)\b', r'[!]$']
        has_cta_pattern = any(re.search(pattern, text_lower) for pattern in cta_patterns)
        
        # Basic length and content checks
        is_reasonable_length = 2 <= len(text.split()) <= 8
        not_navigation = text_lower not in ['home', 'about', 'contact', 'privacy', 'terms']
        
        return (has_action_verb or has_cta_pattern) and is_reasonable_length and not_navigation
        
    def _filter_potential_ctas(self, texts: List[str]) -> List[str]:
        """Filter list of texts for potential CTAs"""
        return [text.strip() for text in texts if text.strip() and self._is_potential_cta(text.strip())]
        
    def _analyze_cta_literalness(self, ctas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Use OpenAI to analyze CTA literalness and generate improvements"""
        if not ctas:
            return []
            
        try:
            # Prepare CTA list for prompt
            cta_list = "\n".join([
                f"{i+1}. \"{cta['text']}\" (Context: {cta.get('context', 'No context')[:100]})"
                for i, cta in enumerate(ctas)
            ])
            
            prompt = LITERAL_OPTIMIZATION_PROMPT.format(cta_list=cta_list)
            
            print(f"🤖 Analyzing {len(ctas)} CTAs with OpenAI...")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a CTA optimization expert. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            
            try:
                result = json.loads(content)
                optimizations = result.get('optimizations', [])
                
                # Match optimizations with original CTAs
                for i, opt in enumerate(optimizations):
                    if i < len(ctas):
                        opt['original_cta_id'] = ctas[i]['id']
                        opt['original_context'] = ctas[i].get('context', '')
                        opt['original_location'] = ctas[i].get('location', '')
                        
                print(f"✅ Generated {len(optimizations)} CTA optimizations")
                return optimizations
                
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse OpenAI response as JSON: {e}")
                return []
                
        except Exception as e:
            print(f"❌ OpenAI analysis error: {e}")
            return []