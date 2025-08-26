from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import openai
from loguru import logger

from ..core.config import get_settings
from ..models.schemas import ExtractedCTA, OptimizedCTA


import asyncio
from typing import Any, Dict, List, Optional
import openai
from loguru import logger
from ..core.config import get_settings
from ..models.schemas import ExtractedCTA, OptimizedCTA

class AnalysisService:
    """AI-powered CTA analysis and optimization service using OpenAI."""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = openai.OpenAI(api_key=self.settings.openai_api_key)
        
    def create_optimization_prompt(self, ctas: List[ExtractedCTA]) -> str:
        """Create a comprehensive prompt for CTA optimization."""
        
        prompt = """You are a conversion rate optimization expert specializing in call-to-action (CTA) improvement. Your task is to analyze and optimize CTA text to increase conversion rates.

OPTIMIZATION PRINCIPLES:
1. Action-Oriented: Use strong action verbs that create urgency
2. Value-Clear: Communicate clear value proposition  
3. Specific: Be concrete rather than vague
4. Benefit-Focused: Highlight what the user gains
5. Friction-Free: Remove uncertainty and hesitation
6. Urgent: Create appropriate sense of urgency when relevant

TRANSFORM VAGUE → SPECIFIC:
- "Learn More" → "See How [Benefit] in 5 Minutes"
- "Click Here" → "Start Free Trial Now"  
- "Submit" → "Get My Personalized Quote"
- "Sign Up" → "Join 50,000+ Professionals"

CTAs TO OPTIMIZE:
"""
        
        for i, cta in enumerate(ctas, 1):
            prompt += f"""
{i}. ORIGINAL: "{cta.original_text}"
   TYPE: {cta.cta_type.value if hasattr(cta.cta_type, 'value') else cta.cta_type}
   CONTEXT: {cta.context or 'No context available'}
   LOCATION: {cta.location or 'Unknown location'}
"""
        
        prompt += """

RESPONSE FORMAT (JSON):
{
  "optimizations": [
    {
      "original_cta_id": "cta_id_here",
      "optimized_text": "New optimized CTA text",
      "improvement_rationale": "Specific explanation of why this is better",
      "confidence_score": 0.85,
      "optimization_type": "action_oriented|value_focused|urgency_added|specificity_improved",
      "action_oriented": true,
      "value_proposition": "What value is highlighted",
      "urgency_level": 7
    }
  ],
  "general_recommendations": [
    "Overall recommendations for CTA strategy"
  ]
}

IMPORTANT: 
- Each optimized CTA should be significantly more action-oriented and specific
- Confidence score should reflect how much improvement is expected (0.0-1.0)
- Urgency level is 1-10 (1=no urgency, 10=maximum urgency)
- Always explain WHY the new version is better
- Keep CTAs concise but impactful (2-6 words ideal)
"""
        
        return prompt
    
    async def optimize_ctas(self, ctas: List[ExtractedCTA]) -> List[OptimizedCTA]:
        """Optimize CTAs using OpenAI API."""
        if not ctas:
            logger.warning("No CTAs provided for optimization")
            return []
        
        logger.info(f"Starting optimization of {len(ctas)} CTAs")
        
        # Split into batches to handle API limits
        batch_size = 10
        all_optimizations = []
        
        for i in range(0, len(ctas), batch_size):
            batch = ctas[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: {len(batch)} CTAs")
            
            try:
                batch_optimizations = await self._process_cta_batch(batch)
                all_optimizations.extend(batch_optimizations)
            except Exception as e:
                logger.error(f"Failed to process CTA batch: {e}")
                # Create fallback optimizations for this batch
                fallback_optimizations = self._create_fallback_optimizations(batch)
                all_optimizations.extend(fallback_optimizations)
        
        logger.info(f"Completed optimization: {len(all_optimizations)} results")
        return all_optimizations
    
    async def _process_cta_batch(self, ctas: List[ExtractedCTA]) -> List[OptimizedCTA]:
        """Process a batch of CTAs with OpenAI."""
        prompt = self.create_optimization_prompt(ctas)
        
        try:
            response = await self._call_openai_api(prompt)
            return self._parse_optimization_response(response, ctas)
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise
    
    async def _call_openai_api(self, prompt: str) -> str:
        """Make API call to OpenAI with error handling."""
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.settings.openai_model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert conversion rate optimization specialist. Always respond with valid JSON format."
                        },
                        {
                            "role": "user", 
                            "content": prompt
                        }
                    ],
                    max_tokens=self.settings.openai_max_tokens,
                    temperature=self.settings.openai_temperature,
                    response_format={"type": "json_object"}
                )
            )
            
            content = response.choices[0].message.content
            logger.debug(f"OpenAI response received: {len(content)} characters")
            
            return content
            
        except openai.RateLimitError as e:
            logger.error(f"OpenAI rate limit exceeded: {e}")
            raise
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling OpenAI: {e}")
            raise
class AnalysisService:
    """AI-powered CTA analysis and optimization service using OpenAI."""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = openai.OpenAI(api_key=self.settings.openai_api_key)
        
    def create_optimization_prompt(self, ctas: List[ExtractedCTA]) -> str:
        """Create a comprehensive prompt for CTA optimization."""
        
        prompt = """You are a conversion rate optimization expert specializing in call-to-action (CTA) improvement. Your task is to analyze and optimize CTA text to increase conversion rates.

OPTIMIZATION PRINCIPLES:
1. Action-Oriented: Use strong action verbs that create urgency
2. Value-Clear: Communicate clear value proposition
3. Specific: Be concrete rather than vague
4. Benefit-Focused: Highlight what the user gains
5. Friction-Free: Remove uncertainty and hesitation
6. Urgent: Create appropriate sense of urgency when relevant

TRANSFORM VAGUE → SPECIFIC:
- "Learn More" → "See How [Benefit] in 5 Minutes"
- "Click Here" → "Start Free Trial Now"
- "Submit" → "Get My Personalized Quote"
- "Sign Up" → "Join 50,000+ Professionals"

CTAs TO OPTIMIZE:
"""
        
        for i, cta in enumerate(ctas, 1):
            prompt += f"""
{i}. ORIGINAL: "{cta.original_text}"
   TYPE: {cta.cta_type.value}
   CONTEXT: {cta.context or 'No context available'}
   LOCATION: {cta.location or 'Unknown location'}
"""
        
        prompt += """

RESPONSE FORMAT (JSON):
{
  "optimizations": [
    {
      "original_cta_id": "cta_id_here",
      "optimized_text": "New optimized CTA text",
      "improvement_rationale": "Specific explanation of why this is better",
      "confidence_score": 0.85,
      "optimization_type": "action_oriented|value_focused|urgency_added|specificity_improved",
      "action_oriented": true,
      "value_proposition": "What value is highlighted",
      "urgency_level": 7
    }
  ],
  "general_recommendations": [
    "Overall recommendations for CTA strategy"
  ]
}

IMPORTANT: 
- Each optimized CTA should be significantly more action-oriented and specific
- Confidence score should reflect how much improvement is expected (0.0-1.0)
- Urgency level is 1-10 (1=no urgency, 10=maximum urgency)
- Always explain WHY the new version is better
- Keep CTAs concise but impactful (2-6 words ideal)
"""
        
        return prompt
    
    async def optimize_ctas(self, ctas: List[ExtractedCTA]) -> List[OptimizedCTA]:
        """Optimize CTAs using OpenAI API."""
        if not ctas:
            logger.warning("No CTAs provided for optimization")
            return []
        
        logger.info(f"Starting optimization of {len(ctas)} CTAs")
        
        # Split into batches to handle API limits
        batch_size = 10
        all_optimizations = []
        
        for i in range(0, len(ctas), batch_size):
            batch = ctas[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: {len(batch)} CTAs")
            
            try:
                batch_optimizations = await self._process_cta_batch(batch)
                all_optimizations.extend(batch_optimizations)
            except Exception as e:
                logger.error(f"Failed to process CTA batch: {e}")
                # Create fallback optimizations for this batch
                fallback_optimizations = self._create_fallback_optimizations(batch)
                all_optimizations.extend(fallback_optimizations)
        
        logger.info(f"Completed optimization: {len(all_optimizations)} results")
        return all_optimizations
    
    async def _process_cta_batch(self, ctas: List[ExtractedCTA]) -> List[OptimizedCTA]:
        """Process a batch of CTAs with OpenAI."""
        prompt = self.create_optimization_prompt(ctas)
        
        try:
            response = await self._call_openai_api(prompt)
            return self._parse_optimization_response(response, ctas)
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise
    
    async def _call_openai_api(self, prompt: str) -> str:
        """Make API call to OpenAI with error handling."""
        try:
            response = self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert conversion rate optimization specialist. Always respond with valid JSON format."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=self.settings.openai_max_tokens,
                temperature=self.settings.openai_temperature,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            logger.debug(f"OpenAI response received: {len(content)} characters")
            
            return content
            
        except openai.RateLimitError as e:
            logger.error(f"OpenAI rate limit exceeded: {e}")
            raise
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling OpenAI: {e}")
            raise
    
    def _parse_optimization_response(self, response: str, original_ctas: List[ExtractedCTA]) -> List[OptimizedCTA]:
        """Parse OpenAI response into OptimizedCTA objects."""
        try:
            data = json.loads(response)
            optimizations = []
            
            # Create lookup for original CTAs
            cta_lookup = {cta.id: cta for cta in original_ctas}
            
            for opt_data in data.get("optimizations", []):
                original_cta_id = opt_data.get("original_cta_id")
                
                # Find matching CTA by ID or text
                matching_cta = None
                if original_cta_id in cta_lookup:
                    matching_cta = cta_lookup[original_cta_id]
                else:
                    # Fallback: match by text similarity
                    optimized_text = opt_data.get("optimized_text", "")
                    for cta in original_ctas:
                        # Simple text matching - could be improved
                        if len(optimizations) < len(original_ctas):
                            matching_cta = cta
                            break
                
                if matching_cta:
                    optimized_cta = OptimizedCTA(
                        original_cta_id=matching_cta.id,
                        optimized_text=opt_data.get("optimized_text", ""),
                        improvement_rationale=opt_data.get("improvement_rationale", ""),
                        confidence_score=min(1.0, max(0.0, opt_data.get("confidence_score", 0.7))),
                        optimization_type=opt_data.get("optimization_type", "general"),
                        action_oriented=opt_data.get("action_oriented", True),
                        value_proposition=opt_data.get("value_proposition"),
                        urgency_level=min(10, max(0, opt_data.get("urgency_level", 5)))
                    )
                    optimizations.append(optimized_cta)
            
            logger.info(f"Parsed {len(optimizations)} optimizations from AI response")
            return optimizations
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response content: {response[:500]}...")
            raise ValueError(f"Invalid JSON response from AI: {e}")
        except Exception as e:
            logger.error(f"Error parsing optimization response: {e}")
            raise
    
    def _create_fallback_optimizations(self, ctas: List[ExtractedCTA]) -> List[OptimizedCTA]:
        """Create basic fallback optimizations when AI fails."""
        logger.info("Creating fallback optimizations")
        
        fallback_optimizations = []
        
        for cta in ctas:
            optimized_text = self._apply_basic_optimization_rules(cta.original_text)
            
            optimization = OptimizedCTA(
                original_cta_id=cta.id,
                optimized_text=optimized_text,
                improvement_rationale="Basic optimization applied due to AI service unavailability",
                confidence_score=0.5,
                optimization_type="fallback",
                action_oriented=True,
                urgency_level=5
            )
            fallback_optimizations.append(optimization)
        
        return fallback_optimizations
    
    def _apply_basic_optimization_rules(self, original_text: str) -> str:
        """Apply basic CTA optimization rules as fallback."""
        text = original_text.strip()
        
        # Basic transformations
        transformations = {
            r'\blearn more\b': 'See How It Works',
            r'\bclick here\b': 'Get Started Now',
            r'\bsubmit\b': 'Send My Request',
            r'\bsign up\b': 'Join Free Today',
            r'\bregister\b': 'Create Account',
            r'\btry\b': 'Start Free Trial',
            r'\bbox now\b': 'Order Now',
            r'\bcontact us\b': 'Get Expert Help',
            r'\bdownload\b': 'Get Free Download',
            r'\bread more\b': 'Learn the Details'
        }
        
        text_lower = text.lower()
        for pattern, replacement in transformations.items():
            if re.search(pattern, text_lower):
                return replacement
        
        # Add action words if missing
        if not any(word in text_lower for word in ['get', 'start', 'try', 'join', 'see', 'discover']):
            if len(text.split()) <= 2:
                text = f"Get {text}"
        
        return text
    
    def analyze_cta_performance_potential(self, ctas: List[ExtractedCTA]) -> Dict[str, Any]:
        """Analyze CTAs to identify improvement potential."""
        if not ctas:
            return {}
        
        analysis = {
            'total_ctas': len(ctas),
            'improvement_potential': {
                'high': 0,
                'medium': 0,
                'low': 0
            },
            'common_issues': [],
            'optimization_priorities': []
        }
        
        vague_patterns = ['click here', 'learn more', 'read more', 'submit', 'continue']
        weak_action_words = ['see', 'view', 'check', 'browse']
        strong_action_words = ['get', 'start', 'join', 'buy', 'download', 'subscribe']
        
        for cta in ctas:
            text_lower = cta.original_text.lower()
            
            # Assess improvement potential
            potential_score = 0
            
            # High potential indicators
            if any(pattern in text_lower for pattern in vague_patterns):
                potential_score += 3
            
            if len(cta.original_text.split()) > 6:
                potential_score += 2
            
            if not any(word in text_lower for word in strong_action_words):
                potential_score += 2
            
            # Categorize potential
            if potential_score >= 5:
                analysis['improvement_potential']['high'] += 1
            elif potential_score >= 3:
                analysis['improvement_potential']['medium'] += 1
            else:
                analysis['improvement_potential']['low'] += 1
        
        # Common issues analysis
        issues = []
        vague_ctas = sum(1 for cta in ctas if any(pattern in cta.original_text.lower() for pattern in vague_patterns))
        if vague_ctas > len(ctas) * 0.3:
            issues.append(f"{vague_ctas} CTAs use vague language")
        
        long_ctas = sum(1 for cta in ctas if len(cta.original_text.split()) > 5)
        if long_ctas > 0:
            issues.append(f"{long_ctas} CTAs are too long")
        
        weak_action_ctas = sum(1 for cta in ctas if any(word in cta.original_text.lower() for word in weak_action_words))
        if weak_action_ctas > 0:
            issues.append(f"{weak_action_ctas} CTAs use weak action words")
        
        analysis['common_issues'] = issues
        
        # Optimization priorities
        priorities = []
        if analysis['improvement_potential']['high'] > 0:
            priorities.append("Focus on high-impact CTAs first")
        
        if vague_ctas > len(ctas) * 0.2:
            priorities.append("Replace vague CTAs with specific actions")
        
        if weak_action_ctas > len(ctas) * 0.3:
            priorities.append("Strengthen action language")
        
        analysis['optimization_priorities'] = priorities
        
        return analysis