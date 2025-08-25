from __future__ import annotations

import asyncio
import uuid
import time
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, FileResponse
from loguru import logger

from ..core.config import get_settings
from ..models.schemas import (
    URLAnalysisRequest, TextAnalysisRequest, ImageAnalysisRequest,
    AnalysisJob, AnalysisResults, AnalysisResultsResponse, JobStatusResponse,
    CTAEditRequest, ExportRequest, ExportResponse, APIResponse, HealthCheck,
    InputType, AnalysisStatus
)
from ..services.crawler_service import CrawlerService
from ..services.scraper_service import ScraperService
from ..services.analysis_service import AnalysisService
from ..services.ocr_service import OCRService

router = APIRouter()

# In-memory job storage (in production, use Redis or database)
job_storage: Dict[str, AnalysisJob] = {}
results_storage: Dict[str, AnalysisResults] = {}

settings = get_settings()


@router.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint."""
    start_time = time.time()
    
    # Check service dependencies
    services = {
        "api": "healthy",
        "openai": "unknown",
        "tesseract": "unknown"
    }
    
    # Test OpenAI connectivity
    try:
        analysis_service = AnalysisService()
        # Simple test - we'll assume it's healthy if we can initialize
        services["openai"] = "healthy"
    except Exception as e:
        services["openai"] = f"error: {str(e)[:50]}"
    
    # Test Tesseract OCR
    try:
        ocr_service = OCRService()
        services["tesseract"] = "healthy"
    except Exception as e:
        services["tesseract"] = f"error: {str(e)[:50]}"
    
    return HealthCheck(
        status="healthy",
        version=settings.app_version,
        services=services,
        uptime_seconds=time.time() - start_time  # This is just for the request, not actual uptime
    )


@router.post("/analyze/url", response_model=JobStatusResponse)
async def analyze_url(
    request: URLAnalysisRequest,
    background_tasks: BackgroundTasks
):
    """Start URL-based CTA analysis."""
    logger.info(f"Starting URL analysis for: {request.url}")
    
    # Create job
    job_id = str(uuid.uuid4())
    job = AnalysisJob(
        job_id=job_id,
        input_type=InputType.URL,
        status=AnalysisStatus.PENDING
    )
    job_storage[job_id] = job
    
    # Start background processing
    background_tasks.add_task(
        _process_url_analysis,
        job_id,
        request
    )
    
    return JobStatusResponse(
        success=True,
        message="URL analysis started",
        data=job
    )


@router.post("/analyze/text", response_model=JobStatusResponse)
async def analyze_text(
    request: TextAnalysisRequest,
    background_tasks: BackgroundTasks
):
    """Start text-based CTA analysis."""
    logger.info(f"Starting text analysis: {len(request.text)} characters")
    
    job_id = str(uuid.uuid4())
    job = AnalysisJob(
        job_id=job_id,
        input_type=InputType.TEXT,
        status=AnalysisStatus.PENDING
    )
    job_storage[job_id] = job
    
    background_tasks.add_task(
        _process_text_analysis,
        job_id,
        request
    )
    
    return JobStatusResponse(
        success=True,
        message="Text analysis started",
        data=job
    )


@router.post("/analyze/image", response_model=JobStatusResponse)
async def analyze_image(
    request: ImageAnalysisRequest,
    background_tasks: BackgroundTasks
):
    """Start image-based CTA analysis."""
    logger.info(f"Starting image analysis: {request.filename or 'unnamed'}")
    
    job_id = str(uuid.uuid4())
    job = AnalysisJob(
        job_id=job_id,
        input_type=InputType.IMAGE,
        status=AnalysisStatus.PENDING
    )
    job_storage[job_id] = job
    
    background_tasks.add_task(
        _process_image_analysis,
        job_id,
        request
    )
    
    return JobStatusResponse(
        success=True,
        message="Image analysis started",
        data=job
    )


@router.post("/upload-image", response_model=JobStatusResponse)
async def upload_image(
    file: UploadFile = File(...),
    context: Optional[str] = None,
    background_tasks: BackgroundTasks = None
):
    """Upload and analyze image file."""
    logger.info(f"Processing uploaded image: {file.filename}")
    
    # Validate file type
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Read file content
    try:
        import base64
        content = await file.read()
        image_data = base64.b64encode(content).decode('utf-8')
        
        # Create analysis request
        request = ImageAnalysisRequest(
            image_data=f"data:{file.content_type};base64,{image_data}",
            filename=file.filename,
            context=context
        )
        
        return await analyze_image(request, background_tasks)
        
    except Exception as e:
        logger.error(f"Failed to process uploaded image: {e}")
        raise HTTPException(status_code=500, detail=f"Image processing failed: {str(e)}")


@router.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get job status."""
    if job_id not in job_storage:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_storage[job_id]
    return JobStatusResponse(
        success=True,
        message="Job status retrieved",
        data=job
    )


@router.get("/jobs/{job_id}/results", response_model=AnalysisResultsResponse)
async def get_analysis_results(job_id: str):
    """Get analysis results."""
    if job_id not in results_storage:
        # Check if job exists but isn't complete
        if job_id in job_storage:
            job = job_storage[job_id]
            if job.status == AnalysisStatus.PROCESSING:
                raise HTTPException(status_code=202, detail="Analysis still processing")
            elif job.status == AnalysisStatus.FAILED:
                raise HTTPException(status_code=500, detail=job.error_message or "Analysis failed")
            else:
                raise HTTPException(status_code=404, detail="Results not found")
        else:
            raise HTTPException(status_code=404, detail="Job not found")
    
    results = results_storage[job_id]
    return AnalysisResultsResponse(
        success=True,
        message="Results retrieved successfully",
        data=results
    )


@router.put("/jobs/{job_id}/edit-cta")
async def edit_cta(job_id: str, edit_request: CTAEditRequest):
    """Edit an optimized CTA."""
    if job_id not in results_storage:
        raise HTTPException(status_code=404, detail="Job results not found")
    
    results = results_storage[job_id]
    
    # Find and update the CTA
    cta_found = False
    for optimized_cta in results.optimized_ctas:
        if optimized_cta.original_cta_id == edit_request.cta_id:
            optimized_cta.optimized_text = edit_request.new_text
            if edit_request.notes:
                optimized_cta.improvement_rationale += f" (User note: {edit_request.notes})"
            cta_found = True
            break
    
    if not cta_found:
        raise HTTPException(status_code=404, detail="CTA not found")
    
    return APIResponse(
        success=True,
        message="CTA updated successfully"
    )


@router.post("/jobs/{job_id}/export", response_model=ExportResponse)
async def export_results(job_id: str, export_request: ExportRequest):
    """Export analysis results."""
    if job_id not in results_storage:
        raise HTTPException(status_code=404, detail="Job results not found")
    
    results = results_storage[job_id]
    
    try:
        # Generate export file
        export_path = await _generate_export_file(results, export_request)
        
        return ExportResponse(
            success=True,
            message="Export generated successfully",
            data={
                "download_url": f"/download/{export_path}",
                "format": export_request.format,
                "filename": export_path
            }
        )
        
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/download/{filename}")
async def download_file(filename: str):
    """Download exported file."""
    import os
    file_path = os.path.join("exports", filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/octet-stream'
    )


@router.get("/jobs")
async def list_jobs():
    """List all jobs."""
    jobs = list(job_storage.values())
    # Sort by creation time, newest first
    jobs.sort(key=lambda x: x.created_at, reverse=True)
    
    return APIResponse(
        success=True,
        message=f"Retrieved {len(jobs)} jobs",
        data=jobs
    )


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its results."""
    deleted_items = []
    
    if job_id in job_storage:
        del job_storage[job_id]
        deleted_items.append("job")
    
    if job_id in results_storage:
        del results_storage[job_id]
        deleted_items.append("results")
    
    if not deleted_items:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return APIResponse(
        success=True,
        message=f"Deleted {', '.join(deleted_items)} for job {job_id}"
    )


# Background processing functions
async def _process_url_analysis(job_id: str, request: URLAnalysisRequest):
    """Process URL analysis in background."""
    job = job_storage[job_id]
    start_time = time.time()
    
    try:
        # Update job status
        job.status = AnalysisStatus.PROCESSING
        job.updated_at = datetime.utcnow()
        job.progress = 10
        
        logger.info(f"Starting URL crawl for job {job_id}")
        
        # Crawl website
        crawler = CrawlerService()
        pages = await crawler.crawl_website(
            str(request.url),
            max_pages=request.max_pages,
            max_depth=request.max_depth
        )
        
        job.pages_analyzed = len(pages)
        job.progress = 50
        
        # Extract all CTAs
        all_ctas = crawler.get_all_ctas()
        job.total_ctas_found = len(all_ctas)
        job.progress = 70
        
        # Optimize CTAs with AI
        analysis_service = AnalysisService()
        optimized_ctas = await analysis_service.optimize_ctas(all_ctas)
        
        job.total_optimizations = len(optimized_ctas)
        job.progress = 90
        
        # Create results
        results = AnalysisResults(
            job_id=job_id,
            input_type=InputType.URL,
            status=AnalysisStatus.COMPLETED,
            source_url=str(request.url),
            pages_analyzed=pages,
            total_pages=len(pages),
            total_ctas_found=len(all_ctas),
            processing_time_seconds=time.time() - start_time,
            extracted_ctas=all_ctas,
            optimized_ctas=optimized_ctas,
            completed_at=datetime.utcnow()
        )
        
        results_storage[job_id] = results
        
        # Complete job
        job.status = AnalysisStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.progress = 100
        
        logger.info(f"Completed URL analysis for job {job_id}")
        
    except Exception as e:
        logger.error(f"URL analysis failed for job {job_id}: {e}")
        job.status = AnalysisStatus.FAILED
        job.error_message = str(e)
        job.updated_at = datetime.utcnow()


async def _process_text_analysis(job_id: str, request: TextAnalysisRequest):
    """Process text analysis in background."""
    job = job_storage[job_id]
    start_time = time.time()
    
    try:
        job.status = AnalysisStatus.PROCESSING
        job.updated_at = datetime.utcnow()
        job.progress = 20
        
        # Extract CTAs from text
        scraper = ScraperService()
        ctas = scraper.cta_extractor.extract_from_text(request.text, request.context)
        
        job.total_ctas_found = len(ctas)
        job.progress = 60
        
        # Optimize CTAs
        analysis_service = AnalysisService()
        optimized_ctas = await analysis_service.optimize_ctas(ctas)
        
        job.total_optimizations = len(optimized_ctas)
        job.progress = 90
        
        # Create results
        results = AnalysisResults(
            job_id=job_id,
            input_type=InputType.TEXT,
            status=AnalysisStatus.COMPLETED,
            source_text=request.text[:1000],  # Truncate for storage
            pages_analyzed=[],
            total_pages=1,
            total_ctas_found=len(ctas),
            processing_time_seconds=time.time() - start_time,
            extracted_ctas=ctas,
            optimized_ctas=optimized_ctas,
            completed_at=datetime.utcnow()
        )
        
        results_storage[job_id] = results
        
        job.status = AnalysisStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.progress = 100
        
        logger.info(f"Completed text analysis for job {job_id}")
        
    except Exception as e:
        logger.error(f"Text analysis failed for job {job_id}: {e}")
        job.status = AnalysisStatus.FAILED
        job.error_message = str(e)


async def _process_image_analysis(job_id: str, request: ImageAnalysisRequest):
    """Process image analysis in background."""
    job = job_storage[job_id]
    start_time = time.time()
    
    try:
        job.status = AnalysisStatus.PROCESSING
        job.updated_at = datetime.utcnow()
        job.progress = 20
        
        # Process image with OCR
        ocr_service = OCRService()
        ctas = ocr_service.process_image_data(request.image_data, request.context)
        
        job.total_ctas_found = len(ctas)
        job.progress = 60
        
        # Optimize CTAs
        analysis_service = AnalysisService()
        optimized_ctas = await analysis_service.optimize_ctas(ctas)
        
        job.total_optimizations = len(optimized_ctas)
        job.progress = 90
        
        # Create results
        results = AnalysisResults(
            job_id=job_id,
            input_type=InputType.IMAGE,
            status=AnalysisStatus.COMPLETED,
            source_image=request.filename,
            pages_analyzed=[],
            total_pages=1,
            total_ctas_found=len(ctas),
            processing_time_seconds=time.time() - start_time,
            extracted_ctas=ctas,
            optimized_ctas=optimized_ctas,
            completed_at=datetime.utcnow()
        )
        
        results_storage[job_id] = results
        
        job.status = AnalysisStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.progress = 100
        
        logger.info(f"Completed image analysis for job {job_id}")
        
    except Exception as e:
        logger.error(f"Image analysis failed for job {job_id}: {e}")
        job.status = AnalysisStatus.FAILED
        job.error_message = str(e)


async def _generate_export_file(results: AnalysisResults, export_request: ExportRequest) -> str:
    """Generate export file."""
    import os
    import csv
    import json
    from pathlib import Path
    
    # Ensure export directory exists
    export_dir = Path("exports")
    export_dir.mkdir(exist_ok=True)
    
    timestamp = int(time.time())
    filename = f"cta_analysis_{results.job_id[:8]}_{timestamp}.{export_request.format}"
    file_path = export_dir / filename
    
    if export_request.format == "csv":
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Headers
            headers = ["Original CTA", "Optimized CTA", "Improvement Rationale", "Confidence Score", "Location", "CTA Type"]
            writer.writerow(headers)
            
            # Data
            for original in results.extracted_ctas:
                # Find corresponding optimization
                optimized = next(
                    (opt for opt in results.optimized_ctas if opt.original_cta_id == original.id),
                    None
                )
                
                if optimized:
                    writer.writerow([
                        original.original_text,
                        optimized.optimized_text,
                        optimized.improvement_rationale,
                        optimized.confidence_score,
                        original.location,
                        original.cta_type
                    ])
    
    elif export_request.format == "json":
        export_data = {
            "job_id": results.job_id,
            "analysis_date": results.created_at.isoformat(),
            "summary": {
                "total_ctas": len(results.extracted_ctas),
                "optimizations": len(results.optimized_ctas),
                "processing_time": results.processing_time_seconds
            },
            "ctas": []
        }
        
        for original in results.extracted_ctas:
            optimized = next(
                (opt for opt in results.optimized_ctas if opt.original_cta_id == original.id),
                None
            )
            
            cta_data = {
                "original": {
                    "text": original.original_text,
                    "type": original.cta_type,
                    "location": original.location,
                    "context": original.context
                }
            }
            
            if optimized:
                cta_data["optimized"] = {
                    "text": optimized.optimized_text,
                    "rationale": optimized.improvement_rationale,
                    "confidence": optimized.confidence_score,
                    "urgency_level": optimized.urgency_level
                }
            
            export_data["ctas"].append(cta_data)
        
        with open(file_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(export_data, jsonfile, indent=2, default=str)
    
    return filename