from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Dict, List, Set, Tuple
from urllib.parse import urljoin, urlparse

from loguru import logger

from ..core.config import get_settings
from ..models.schemas import ExtractedCTA, PageAnalysis
from ..services.scraper_service import ScraperService


class CrawlerService:
    """CTA-focused web crawler that prioritizes pages with conversion elements."""
    
    def __init__(self):
        self.settings = get_settings()
        self.scraper = ScraperService()
        self.visited_urls: Set[str] = set()
        self.crawl_queue: deque = deque()
        self.page_analyses: List[PageAnalysis] = []
        
    def normalize_url(self, url: str) -> str:
        """Normalize URL for consistent comparison."""
        parsed = urlparse(url)
        # Remove fragment and normalize
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized.rstrip('/')
    
    def is_same_domain(self, base_url: str, candidate_url: str) -> bool:
        """Check if URLs belong to the same domain."""
        base_domain = urlparse(base_url).netloc
        candidate_domain = urlparse(candidate_url).netloc
        return base_domain == candidate_domain
    
    def should_crawl_url(self, url: str, base_domain: str) -> bool:
        """Determine if URL should be crawled based on CTA optimization criteria."""
        parsed = urlparse(url)
        
        # Skip non-HTTP URLs
        if parsed.scheme not in ['http', 'https']:
            return False
        
        # Skip different domains
        if parsed.netloc != base_domain:
            return False
        
        # Skip file downloads
        skip_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.doc', '.docx']
        if any(url.lower().endswith(ext) for ext in skip_extensions):
            return False
        
        # Skip common non-content URLs
        skip_patterns = [
            'admin', 'wp-admin', 'login', 'logout', 'register',
            'api/', 'ajax/', 'json', 'xml', 'rss', 'feed',
            'terms', 'privacy', 'legal', 'sitemap'
        ]
        
        url_lower = url.lower()
        if any(pattern in url_lower for pattern in skip_patterns):
            return False
        
        return True
    
    def prioritize_url(self, url: str, html_content: str) -> int:
        """Assign priority score to URLs for CTA-focused crawling."""
        priority = 0
        url_lower = url.lower()
        
        # High priority for conversion-focused pages
        high_priority_keywords = [
            'pricing', 'plans', 'signup', 'register', 'subscribe',
            'buy', 'purchase', 'checkout', 'contact', 'demo',
            'trial', 'free', 'get-started', 'start'
        ]
        
        for keyword in high_priority_keywords:
            if keyword in url_lower:
                priority += 10
                break
        
        # Medium priority for product/service pages
        medium_priority_keywords = [
            'product', 'service', 'solution', 'feature',
            'about', 'how-it-works', 'benefits'
        ]
        
        for keyword in medium_priority_keywords:
            if keyword in url_lower:
                priority += 5
                break
        
        # Analyze HTML content for CTA richness
        if self.scraper.is_cta_rich_page(html_content):
            priority += 8
        
        # Check page depth (shorter paths often more important)
        path_segments = len(parsed_url.path.strip('/').split('/')) if urlparse(url).path.strip('/') else 0
        if path_segments <= 1:
            priority += 3
        elif path_segments <= 2:
            priority += 1
        
        return priority
    
    async def crawl_website(
        self, 
        start_url: str, 
        max_pages: int = 10, 
        max_depth: int = 2
    ) -> List[PageAnalysis]:
        """Crawl website focusing on CTA-rich pages."""
        logger.info(f"Starting CTA-focused crawl of {start_url}")
        logger.info(f"Max pages: {max_pages}, Max depth: {max_depth}")
        
        start_time = time.time()
        base_domain = urlparse(start_url).netloc
        
        # Initialize crawl state
        self.visited_urls.clear()
        self.crawl_queue.clear()
        self.page_analyses.clear()
        
        # Add start URL to queue
        self.crawl_queue.append((start_url, 0))
        
        async with self.scraper:
            while self.crawl_queue and len(self.page_analyses) < max_pages:
                current_url, depth = self.crawl_queue.popleft()
                
                # Skip if already visited
                normalized_url = self.normalize_url(current_url)
                if normalized_url in self.visited_urls:
                    continue
                
                self.visited_urls.add(normalized_url)
                
                logger.info(f"Crawling: {current_url} (depth: {depth})")
                
                try:
                    # Fetch and analyze page
                    page_analysis = await self._analyze_page_async(current_url)
                    self.page_analyses.append(page_analysis)
                    
                    # Extract links for next depth level if within limits
                    if depth < max_depth and not page_analysis.error:
                        html = await self.scraper.fetch_html_async(current_url)
                        new_links = self.scraper.extract_page_links(html, current_url)
                        
                        # Prioritize and add links to queue
                        prioritized_links = []
                        for link in new_links:
                            if (self.should_crawl_url(link, base_domain) and 
                                self.normalize_url(link) not in self.visited_urls):
                                
                                try:
                                    link_html = await self.scraper.fetch_html_async(link)
                                    priority = self.prioritize_url(link, link_html)
                                    prioritized_links.append((priority, link, depth + 1))
                                except Exception as e:
                                    logger.warning(f"Failed to fetch {link} for prioritization: {e}")
                                    prioritized_links.append((0, link, depth + 1))
                        
                        # Sort by priority (highest first) and add to queue
                        prioritized_links.sort(key=lambda x: x[0], reverse=True)
                        
                        for priority, link, link_depth in prioritized_links:
                            if len(self.crawl_queue) < max_pages * 2:  # Limit queue size
                                self.crawl_queue.append((link, link_depth))
                                logger.debug(f"Queued: {link} (priority: {priority})")
                
                except Exception as e:
                    logger.error(f"Failed to crawl {current_url}: {e}")
                    # Add error page analysis
                    error_analysis = PageAnalysis(
                        url=current_url,
                        ctas_found=0,
                        extracted_ctas=[],
                        error=str(e)
                    )
                    self.page_analyses.append(error_analysis)
                
                # Respectful delay between requests
                await asyncio.sleep(self.settings.scraper_delay)
        
        crawl_time = time.time() - start_time
        total_ctas = sum(analysis.ctas_found for analysis in self.page_analyses)
        
        logger.info(f"Crawl completed in {crawl_time:.2f}s")
        logger.info(f"Pages analyzed: {len(self.page_analyses)}")
        logger.info(f"Total CTAs found: {total_ctas}")
        
        return self.page_analyses
    
    async def _analyze_page_async(self, url: str) -> PageAnalysis:
        """Analyze a single page asynchronously."""
        start_time = time.time()
        
        try:
            html = await self.scraper.fetch_html_async(url)
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')
            
            # Extract basic page info
            title = soup.title.string if soup.title else None
            meta_desc = None
            meta_tag = soup.find('meta', attrs={'name': 'description'})
            if meta_tag:
                meta_desc = meta_tag.get('content')
            
            # Extract CTAs
            ctas = self.scraper.cta_extractor.extract_from_html(html, url)
            
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            analysis = PageAnalysis(
                url=url,
                title=title,
                description=meta_desc,
                response_time_ms=response_time,
                ctas_found=len(ctas),
                extracted_ctas=ctas
            )
            
            logger.debug(f"Analyzed {url}: found {len(ctas)} CTAs in {response_time:.0f}ms")
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
    
    def get_crawl_summary(self) -> Dict[str, any]:
        """Get summary statistics of the crawl."""
        if not self.page_analyses:
            return {}
        
        successful_analyses = [a for a in self.page_analyses if not a.error]
        failed_analyses = [a for a in self.page_analyses if a.error]
        
        all_ctas = []
        for analysis in successful_analyses:
            all_ctas.extend(analysis.extracted_ctas)
        
        # CTA type distribution
        cta_types = {}
        for cta in all_ctas:
            cta_type = cta.cta_type.value
            cta_types[cta_type] = cta_types.get(cta_type, 0) + 1
        
        # Location distribution
        locations = {}
        for cta in all_ctas:
            location = cta.location or 'Unknown'
            locations[location] = locations.get(location, 0) + 1
        
        # Page performance
        response_times = [a.response_time_ms for a in successful_analyses if a.response_time_ms]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # Pages by CTA count
        cta_rich_pages = [a for a in successful_analyses if a.ctas_found >= 5]
        moderate_cta_pages = [a for a in successful_analyses if 2 <= a.ctas_found < 5]
        low_cta_pages = [a for a in successful_analyses if a.ctas_found < 2]
        
        return {
            'crawl_stats': {
                'total_pages': len(self.page_analyses),
                'successful_pages': len(successful_analyses),
                'failed_pages': len(failed_analyses),
                'total_ctas_found': len(all_ctas),
                'avg_ctas_per_page': len(all_ctas) / len(successful_analyses) if successful_analyses else 0,
                'avg_response_time_ms': avg_response_time
            },
            'cta_distribution': {
                'by_type': cta_types,
                'by_location': locations
            },
            'page_categories': {
                'cta_rich_pages': len(cta_rich_pages),  # 5+ CTAs
                'moderate_cta_pages': len(moderate_cta_pages),  # 2-4 CTAs
                'low_cta_pages': len(low_cta_pages)  # 0-1 CTAs
            },
            'top_pages_by_cta_count': [
                {
                    'url': analysis.url,
                    'cta_count': analysis.ctas_found,
                    'title': analysis.title
                }
                for analysis in sorted(successful_analyses, key=lambda x: x.ctas_found, reverse=True)[:5]
            ]
        }
    
    def filter_pages_by_cta_density(self, min_ctas: int = 3) -> List[PageAnalysis]:
        """Filter pages by minimum CTA count for focused optimization."""
        return [
            analysis for analysis in self.page_analyses 
            if analysis.ctas_found >= min_ctas and not analysis.error
        ]
    
    def get_all_ctas(self) -> List[ExtractedCTA]:
        """Get all CTAs from all crawled pages."""
        all_ctas = []
        for analysis in self.page_analyses:
            if not analysis.error:
                all_ctas.extend(analysis.extracted_ctas)
        return all_ctas
    
    def get_unique_cta_texts(self) -> List[str]:
        """Get unique CTA texts across all pages."""
        all_ctas = self.get_all_ctas()
        unique_texts = list(set(cta.original_text for cta in all_ctas))
        return sorted(unique_texts)
    
    async def quick_crawl(self, start_url: str, max_pages: int = 5) -> List[PageAnalysis]:
        """Quick crawl focusing only on the most important pages."""
        logger.info(f"Starting quick crawl of {start_url}")
        
        # Start with the main page
        main_analysis = await self._analyze_page_async(start_url)
        analyses = [main_analysis]
        
        if main_analysis.error:
            logger.warning(f"Failed to analyze main page: {main_analysis.error}")
            return analyses
        
        async with self.scraper:
            try:
                # Get HTML for link extraction
                html = await self.scraper.fetch_html_async(start_url)
                links = self.scraper.extract_page_links(html, start_url)
                
                # Prioritize links based on URL patterns
                high_priority_urls = []
                base_domain = urlparse(start_url).netloc
                
                for link in links:
                    if not self.should_crawl_url(link, base_domain):
                        continue
                    
                    # Quick prioritization based on URL only
                    url_lower = link.lower()
                    priority = 0
                    
                    # High priority patterns
                    if any(keyword in url_lower for keyword in ['pricing', 'signup', 'contact', 'demo']):
                        priority = 10
                    elif any(keyword in url_lower for keyword in ['product', 'service', 'about']):
                        priority = 5
                    
                    if priority > 0:
                        high_priority_urls.append((priority, link))
                
                # Sort by priority and limit
                high_priority_urls.sort(key=lambda x: x[0], reverse=True)
                priority_links = [url for _, url in high_priority_urls[:max_pages-1]]
                
                # Analyze priority pages
                for url in priority_links:
                    if len(analyses) >= max_pages:
                        break
                    
                    try:
                        analysis = await self._analyze_page_async(url)
                        analyses.append(analysis)
                        await asyncio.sleep(0.5)  # Brief delay
                    except Exception as e:
                        logger.warning(f"Failed to analyze {url}: {e}")
            
            except Exception as e:
                logger.error(f"Error during quick crawl link extraction: {e}")
        
        logger.info(f"Quick crawl completed: {len(analyses)} pages analyzed")
        return analyses