from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl, validator


class InputType(str, Enum):
    """Types of input for CTA analysis."""
    URL = "url"
    IMAGE = "image"
    TEXT = "text"


class CTAType(str, Enum):
    """Types of CTAs detected."""
    BUTTON = "button"
    LINK = "link"
    FORM_SUBMIT = "form_submit"
    IMAGE_BUTTON = "image_button"
    TEXT_CTA = "text_cta"


class AnalysisStatus(str, Enum):
    """Status of analysis job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# Request Models
class URLAnalysisRequest(BaseModel):
    """Request model for URL-based CTA analysis."""
    url: HttpUrl = Field(..., description="Website URL to analyze")
    max_pages: int = Field(default=5, ge=1, le=20, description="Maximum pages to crawl")
    max_depth: int = Field(default=2, ge=1, le=3, description="Maximum crawl depth")
    include_screenshots: bool = Field(default=False, description="Capture screenshots during crawling")
    
    @validator('url')
    def validate_url(cls, v):
        if not str(v).startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v


class TextAnalysisRequest(BaseModel):
    """Request model for direct text analysis."""
    text: str = Field(..., min_length=1, max_length=10000, description="Text containing CTAs to analyze")
    context: Optional[str] = Field(default=None, max_length=1000, description="Additional context about the text")


class ImageAnalysisRequest(BaseModel):
    """Request model for image-based analysis."""
    image_data: str = Field(..., description="Base64 encoded image data")
    filename: Optional[str] = Field(default=None, description="Original filename")
    context: Optional[str] = Field(default=None, max_length=1000, description="Additional context about the image")


# Core Data Models
class ExtractedCTA(BaseModel):
    """Represents a CTA extracted from content."""
    id: str = Field(..., description="Unique identifier for the CTA")
    original_text: str = Field(..., description="Original CTA text")
    cta_type: CTAType = Field(..., description="Type of CTA element")
    context: Optional[str] = Field(default=None, description="Surrounding context")
    location: Optional[str] = Field(default=None, description="Location/section where CTA was found")
    url: Optional[str] = Field(default=None, description="Source URL (if from web crawling)")
    coordinates: Optional[Dict[str, int]] = Field(default=None, description="Position coordinates (for images)")
    html_element: Optional[str] = Field(default=None, description="HTML element containing the CTA")
    css_selector: Optional[str] = Field(default=None, description="CSS selector for the element")
    
    class Config:
        use_enum_values = True


class OptimizedCTA(BaseModel):
    """Represents an AI-optimized CTA suggestion."""
    original_cta_id: str = Field(..., description="Reference to the original CTA")
    optimized_text: str = Field(..., description="AI-suggested optimized text")
    improvement_rationale: str = Field(..., description="Explanation of why this is better")
    confidence_score: float = Field(..., ge=0, le=1, description="AI confidence in this suggestion")
    optimization_type: str = Field(..., description="Type of optimization applied")
    action_oriented: bool = Field(..., description="Whether the new text is more action-oriented")
    value_proposition: Optional[str] = Field(default=None, description="Value proposition highlighted")
    urgency_level: int = Field(default=0, ge=0, le=10, description="Urgency level (0-10)")
    
    class Config:
        use_enum_values = True


class PageAnalysis(BaseModel):
    """Analysis results for a single page."""
    url: str = Field(..., description="Page URL")
    title: Optional[str] = Field(default=None, description="Page title")
    description: Optional[str] = Field(default=None, description="Page meta description")
    screenshot_path: Optional[str] = Field(default=None, description="Path to screenshot")
    response_time_ms: Optional[float] = Field(default=None, description="Page load time")
    ctas_found: int = Field(..., description="Number of CTAs found")
    extracted_ctas: List[ExtractedCTA] = Field(default=[], description="CTAs extracted from this page")
    error: Optional[str] = Field(default=None, description="Error message if processing failed")
    processed_at: datetime = Field(default_factory=datetime.utcnow, description="Processing timestamp")


# Response Models
class AnalysisJob(BaseModel):
    """Analysis job tracking model."""
    job_id: str = Field(..., description="Unique job identifier")
    input_type: InputType = Field(..., description="Type of input being analyzed")
    status: AnalysisStatus = Field(..., description="Current status of the job")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Job creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    completed_at: Optional[datetime] = Field(default=None, description="Job completion time")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    progress: int = Field(default=0, ge=0, le=100, description="Progress percentage")
    
    # Results
    pages_analyzed: int = Field(default=0, description="Number of pages processed")
    total_ctas_found: int = Field(default=0, description="Total CTAs extracted")
    total_optimizations: int = Field(default=0, description="Total optimizations generated")
    
    class Config:
        use_enum_values = True


class AnalysisResults(BaseModel):
    """Complete analysis results."""
    job_id: str = Field(..., description="Job identifier")
    input_type: InputType = Field(..., description="Type of input analyzed")
    status: AnalysisStatus = Field(..., description="Analysis status")
    
    # Input details
    source_url: Optional[str] = Field(default=None, description="Source URL (if URL analysis)")
    source_text: Optional[str] = Field(default=None, description="Source text (if text analysis)")
    source_image: Optional[str] = Field(default=None, description="Source image path (if image analysis)")
    
    # Analysis metadata
    pages_analyzed: List[PageAnalysis] = Field(default=[], description="Per-page analysis results")
    total_pages: int = Field(..., description="Total pages analyzed")
    total_ctas_found: int = Field(..., description="Total CTAs found")
    processing_time_seconds: float = Field(..., description="Total processing time")
    
    # CTA results
    extracted_ctas: List[ExtractedCTA] = Field(default=[], description="All extracted CTAs")
    optimized_ctas: List[OptimizedCTA] = Field(default=[], description="AI-optimized CTAs")
    
    # Summary insights
    improvement_summary: Dict[str, Any] = Field(default={}, description="Summary of improvements")
    recommendations: List[str] = Field(default=[], description="General optimization recommendations")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
    
    class Config:
        use_enum_values = True


class CTAEditRequest(BaseModel):
    """Request to edit an optimized CTA."""
    cta_id: str = Field(..., description="CTA identifier to edit")
    new_text: str = Field(..., min_length=1, max_length=200, description="New CTA text")
    notes: Optional[str] = Field(default=None, max_length=500, description="User notes about the edit")


class ExportRequest(BaseModel):
    """Request to export analysis results."""
    job_id: str = Field(..., description="Job ID to export")
    format: str = Field(default="csv", regex="^(csv|json|xlsx)$", description="Export format")
    include_original: bool = Field(default=True, description="Include original CTAs")
    include_optimized: bool = Field(default=True, description="Include optimized CTAs")
    include_analysis: bool = Field(default=False, description="Include analysis metadata")


# API Response Models
class APIResponse(BaseModel):
    """Standard API response wrapper."""
    success: bool = Field(..., description="Whether the request was successful")
    message: str = Field(..., description="Response message")
    data: Optional[Any] = Field(default=None, description="Response data")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class JobStatusResponse(APIResponse):
    """Response for job status queries."""
    data: Optional[AnalysisJob] = None


class AnalysisResultsResponse(APIResponse):
    """Response for analysis results."""
    data: Optional[AnalysisResults] = None


class ExportResponse(APIResponse):
    """Response for export requests."""
    data: Optional[Dict[str, str]] = None  # Contains download_url and other export info


# Health Check Model
class HealthCheck(BaseModel):
    """Health check response model."""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Application version")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, str] = Field(..., description="Status of dependent services")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")