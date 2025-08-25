from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import aiohttp
import requests
from bs4 import BeautifulSoup
from loguru import logger

from ..core.config import get_settings
from ..models.schemas import ExtractedCTA, PageAnalysis
from ..utils.cta_extractor import CTAExtractor


class ScraperService:
    """Enhanced scraper service focused on CTA extraction."""
    
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    def __init__(self):
        self.settings = get_settings()
        self.cta_extractor = CTAExtractor()
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=3)
        timeout = aiohttp.ClientTimeout(total=self.settings.scraper_timeout)
        
        self.session = aiohttp.ClientSession(
            headers=self.DEFAULT_HEADERS,
            connector=connector,
            timeout=timeout
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    def fetch_html_sync(self, url: str) -> str:
        """Synchronous HTML fetching for simple cases."""
        logger.info(f"Fetching HTML from {url}")
        
        try:
            response = requests.get(
                url, 
                headers=self.DEFAULT_HEADERS,
                timeout=self.settings.scraper_timeout
            )
            response.raise_for_status()
            
            content_type = response.headers.get("Content-Type", "").lower()
            if "html" not in content_type and "xml" not in content_type:
                logger.warning(f"Non-HTML content type: {content_type}")
            
            return response.text
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            raise
    
    async def fetch_html_async(self, url: str) -> str:
        """Asynchronous HTML fetching."""
        if not self.session:
            raise RuntimeError("ScraperService not initialized with async context manager")
        
        logger.info(f"Async fetching HTML from {url}")
        
        try:
            async with self.session.get(url) as response:
                response.raise_for_status()
                
                content_type = response.headers.get("Content-Type", "").lower()
                if "html" not in content_type and "xml" not in content_type:
                    logger.warning(f"Non-HTML content type: {content_type}")
                
                html = await response.text()
                return html
                
        except aiohttp.ClientError as e:
            logger.error(f"Failed to fetch {url}: {e}")
            raise
    
    def analyze_single_page(self, url: str, capture_screenshot: bool = False) -> PageAnalysis:
        """Analyze a single page for CTAs."""
        start_time = time.time()
        
        try:
            html = self.fetch_html_sync(url)
            soup = BeautifulSoup(html, 'lxml')
            
            # Extract basic page info
            title = soup.title.string if soup.title else None
            meta_desc = None
            meta_tag = soup.find('meta', attrs={'name': 'description'})
            if meta_tag:
                meta_desc = meta_tag.get('content')
            
            # Extract CTAs
            ctas = self.cta_extractor.extract_from_html(html, url)
            
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            analysis = PageAnalysis(
                url=url,
                title=title,
                description=meta_desc,
                response_time_ms=response_time,
                ctas_found=len(ctas),
                extracted_ctas=ctas
            )
            
            logger.info(f"Analyzed {url}: found {len(ctas)} CTAs in {response_time:.0f}ms")
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze {url}: {e}")
            return PageAnalysis(
                url=url,
                response_time_ms=(time.time() - start_time) * 1000,
                ctas_found=0,
                extracted_ctas=[],
                error=str(e)
            )
    
    async def analyze_multiple_pages(self, urls: List[str]) -> List[PageAnalysis]:
        """Analyze multiple pages concurrently."""
        logger.info(f"Starting concurrent analysis of {len(urls)} pages")
        
        async def analyze_single_async(url: str) -> PageAnalysis:
            start_time = time.time()
            
            try:
                html = await self.fetch_html_async(url)
                soup = BeautifulSoup(html, 'lxml')
                
                # Extract basic page info
                title = soup.title.string if soup.title else None
                meta_desc = None
                meta_tag = soup.find('meta', attrs={'name': 'description'})
                if meta_tag:
                    meta_desc = meta_tag.get('content')
                
                # Extract CTAs
                ctas = self.cta_extractor.extract_from_html(html, url)
                
                response_time = (time.time() - start_time) * 1000
                
                return PageAnalysis(
                    url=url,
                    title=title,
                    description=meta_desc,
                    response_time_ms=response_time,
                    ctas_found=len(ctas),
                    extracted_ctas=ctas
                )
                
            except Exception as e:
                logger.error(f"Failed to analyze {url}: {e}")
                return PageAnalysis(
                    url=url,
                    response_time_ms=(time.time() - start_time) * 1000,
                    ctas_found=0,
                    extracted_ctas=[],
                    error=str(e)
                )
        
        # Analyze pages with controlled concurrency
        semaphore = asyncio.Semaphore(5)  # Limit concurrent requests
        
        async def bounded_analyze(url: str) -> PageAnalysis:
            async with semaphore:
                await asyncio.sleep(0.5)  # Respectful delay
                return await analyze_single_async(url)
        
        tasks = [bounded_analyze(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        analyses = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task failed for {urls[i]}: {result}")
                analyses.append(PageAnalysis(
                    url=urls[i],
                    ctas_found=0,
                    extracted_ctas=[],
                    error=str(result)
                ))
            else:
                analyses.append(result)
        
        logger.info(f"Completed analysis of {len(analyses)} pages")
        return analyses
    
    def extract_page_links(self, html: str, base_url: str) -> List[str]:
        """Extract internal links from a page for crawling."""
        soup = BeautifulSoup(html, 'lxml')
        base_domain = urlparse(base_url).netloc
        links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Skip anchor links, mailto, tel, etc.
            if href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
                continue
            
            # Convert relative URLs to absolute
            absolute_url = urljoin(base_url, href)
            
            # Only include same-domain links
            if urlparse(absolute_url).netloc == base_domain:
                # Clean up URL (remove fragments, query params if needed)
                clean_url = absolute_url.split('#')[0]
                if clean_url not in links and clean_url != base_url:
                    links.append(clean_url)
        
        logger.info(f"Found {len(links)} internal links from {base_url}")
        return links
    
    def is_cta_rich_page(self, html: str) -> bool:
        """Determine if a page is likely to contain many CTAs."""
        soup = BeautifulSoup(html, 'lxml')
        
        # Count potential CTA indicators
        cta_indicators = 0
        
        # Count buttons and form submits
        buttons = soup.find_all(['button', 'input'], type=['button', 'submit'])
        cta_indicators += len(buttons)
        
        # Count links with CTA-like classes
        cta_links = soup.find_all('a', class_=re.compile(r'btn|button|cta|primary|call-to-action'))
        cta_indicators += len(cta_links)
        
        # Count forms
        forms = soup.find_all('form')
        cta_indicators += len(forms)
        
        # Check for CTA-oriented content
        text = soup.get_text().lower()
        cta_keywords = ['sign up', 'get started', 'buy now', 'subscribe', 'download', 'contact us']
        keyword_count = sum(1 for keyword in cta_keywords if keyword in text)
        
        total_score = cta_indicators + (keyword_count * 0.5)
        
        logger.debug(f"CTA richness score: {total_score}")
        return total_score >= 3
    
    def needs_javascript_rendering(self, html: str) -> bool:
        """Heuristic to detect if a page needs JavaScript rendering."""
        # Check for suspiciously small HTML
        if len(html) < 5000:
            return True
        
        # Check for empty body or minimal content
        if "<body></body>" in html or "<body><div></div></body>" in html:
            return True
        
        # Check for heavy JavaScript presence with minimal HTML content
        script_count = html.count("<script")
        div_count = html.count("<div")
        if script_count > 0 and div_count < 5:
            return True
        
        # Check for common SPA indicators
        spa_indicators = ["ng-app", "data-reactroot", "id=\"root\"", "id=\"app\""]
        if any(indicator in html for indicator in spa_indicators):
            return True
        
        return False
    
    def clean_html_for_analysis(self, html: str) -> str:
        """Clean HTML to improve CTA extraction accuracy."""
        soup = BeautifulSoup(html, 'lxml')
        
        # Remove script and style tags
        for tag in soup(['script', 'style', 'noscript']):
            tag.decompose()
        
        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, type(soup.new_tag('').string))):
            comment.extract()
        
        # Remove hidden elements
        for hidden in soup.find_all(style=re.compile(r'display:\s*none|visibility:\s*hidden')):
            hidden.decompose()
        
        return str(soup)
    
    def get_page_screenshot_path(self, url: str) -> Optional[str]:
        """Generate screenshot path for a URL (placeholder for future implementation)."""
        # This would integrate with Playwright or similar for screenshots
        domain = urlparse(url).netloc.replace(".", "_")
        timestamp = int(time.time())
        screenshot_path = Path(self.settings.screenshot_dir) / f"{domain}_{timestamp}.png"
        
        # For now, return None since we're not implementing screenshots yet
        return None
    
    def validate_url(self, url: str) -> bool:
        """Validate if URL is accessible and returns HTML."""
        try:
            response = requests.head(url, timeout=10, headers=self.DEFAULT_HEADERS)
            content_type = response.headers.get('Content-Type', '').lower()
            
            # Check if it's likely to be HTML content
            return (
                response.status_code == 200 and 
                ('html' in content_type or 'xml' in content_type or content_type == '')
            )
        except requests.RequestException:
            return False