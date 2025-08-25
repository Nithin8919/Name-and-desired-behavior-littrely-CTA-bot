from __future__ import annotations

import base64
import io
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from loguru import logger

from ..core.config import get_settings
from ..models.schemas import ExtractedCTA
from ..utils.cta_extractor import CTAExtractor


class OCRService:
    """OCR service for extracting CTAs from images."""
    
    def __init__(self):
        self.settings = get_settings()
        self.cta_extractor = CTAExtractor()
        
        # Configure Tesseract path if specified
        if self.settings.tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = self.settings.tesseract_path
    
    def process_image_data(self, image_data: str, context: Optional[str] = None) -> List[ExtractedCTA]:
        """Process base64 image data and extract CTAs."""
        logger.info("Processing image data for CTA extraction")
        
        try:
            # Decode base64 image
            if ',' in image_data:
                image_data = image_data.split(',', 1)[1]
            
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            logger.info(f"Image loaded: {image.size} pixels, mode: {image.mode}")
            
            # Extract text using OCR
            extracted_text = self.extract_text_from_image(image)
            
            # Extract CTAs from the text
            ctas = self.cta_extractor.extract_from_text(extracted_text, context)
            
            # Enhance CTAs with image-specific information
            enhanced_ctas = self._enhance_image_ctas(ctas, image.size)
            
            logger.info(f"Extracted {len(enhanced_ctas)} CTAs from image")
            return enhanced_ctas
            
        except Exception as e:
            logger.error(f"Failed to process image data: {e}")
            raise ValueError(f"Image processing failed: {e}")
    
    def process_image_file(self, file_path: str, context: Optional[str] = None) -> List[ExtractedCTA]:
        """Process image file and extract CTAs."""
        logger.info(f"Processing image file: {file_path}")
        
        try:
            image = Image.open(file_path)
            extracted_text = self.extract_text_from_image(image)
            ctas = self.cta_extractor.extract_from_text(extracted_text, context)
            enhanced_ctas = self._enhance_image_ctas(ctas, image.size)
            
            logger.info(f"Extracted {len(enhanced_ctas)} CTAs from {file_path}")
            return enhanced_ctas
            
        except Exception as e:
            logger.error(f"Failed to process image file {file_path}: {e}")
            raise ValueError(f"Image file processing failed: {e}")
    
    def extract_text_from_image(self, image: Image.Image) -> str:
        """Extract text from PIL Image using OCR with preprocessing."""
        logger.debug(f"Starting OCR on image: {image.size}")
        
        # Preprocess image for better OCR
        processed_image = self._preprocess_image(image)
        
        try:
            # Configure OCR settings
            custom_config = f'--oem 3 --psm 6 -l {self.settings.tesseract_lang}'
            
            # Extract text
            text = pytesseract.image_to_string(processed_image, config=custom_config)
            
            logger.debug(f"OCR extracted {len(text)} characters")
            return text.strip()
            
        except pytesseract.TesseractNotFoundError:
            logger.error("Tesseract not found. Please install Tesseract OCR.")
            raise RuntimeError(
                "Tesseract OCR not found. Please install Tesseract and ensure it's in your PATH."
            )
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            raise RuntimeError(f"OCR processing failed: {e}")
    
    def extract_text_with_coordinates(self, image: Image.Image) -> List[Tuple[str, dict]]:
        """Extract text with bounding box coordinates for position-aware CTA detection."""
        logger.debug("Extracting text with coordinates")
        
        processed_image = self._preprocess_image(image)
        
        try:
            # Get detailed OCR data
            custom_config = f'--oem 3 --psm 6 -l {self.settings.tesseract_lang}'
            
            data = pytesseract.image_to_data(
                processed_image, 
                config=custom_config, 
                output_type=pytesseract.Output.DICT
            )
            
            # Extract text with coordinates
            text_with_coords = []
            n_boxes = len(data['text'])
            
            for i in range(n_boxes):
                text = data['text'][i].strip()
                if text:  # Only include non-empty text
                    coords = {
                        'x': data['left'][i],
                        'y': data['top'][i],
                        'width': data['width'][i],
                        'height': data['height'][i],
                        'confidence': data['conf'][i]
                    }
                    text_with_coords.append((text, coords))
            
            logger.debug(f"Extracted {len(text_with_coords)} text segments with coordinates")
            return text_with_coords
            
        except Exception as e:
            logger.error(f"Coordinate-based OCR failed: {e}")
            raise RuntimeError(f"Coordinate OCR processing failed: {e}")
    
    def detect_button_regions(self, image: Image.Image) -> List[dict]:
        """Detect potential button/CTA regions in the image using basic image processing."""
        logger.debug("Detecting potential button regions")
        
        try:
            # Convert to grayscale for processing
            gray = image.convert('L')
            
            # Apply edge detection to find rectangular regions
            edges = gray.filter(ImageFilter.FIND_EDGES)
            
            # This is a simplified approach - in production, you might want to use
            # more sophisticated computer vision techniques like OpenCV
            
            # For now, we'll return the full image as a single region
            # This could be enhanced with actual button detection algorithms
            
            regions = [{
                'x': 0,
                'y': 0,
                'width': image.size[0],
                'height': image.size[1],
                'confidence': 0.5,
                'type': 'full_image'
            }]
            
            logger.debug(f"Detected {len(regions)} potential button regions")
            return regions
            
        except Exception as e:
            logger.warning(f"Button region detection failed: {e}")
            return []
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """Preprocess image to improve OCR accuracy."""
        logger.debug("Preprocessing image for OCR")
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize if image is too small (OCR works better on larger images)
        width, height = image.size
        if width < 300 or height < 300:
            scale_factor = max(300 / width, 300 / height)
            new_size = (int(width * scale_factor), int(height * scale_factor))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            logger.debug(f"Resized image to {new_size}")
        
        # Enhance contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.2)
        
        # Enhance sharpness
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.1)
        
        # Convert to grayscale for better OCR
        image = image.convert('L')
        
        return image
    
    def _enhance_image_ctas(self, ctas: List[ExtractedCTA], image_size: Tuple[int, int]) -> List[ExtractedCTA]:
        """Enhance CTAs with image-specific metadata."""
        enhanced_ctas = []
        
        for cta in ctas:
            # Update CTA type for image context
            cta.cta_type = "image_button"  # Override type for image CTAs
            
            # Add image dimensions as metadata
            if not cta.coordinates:
                cta.coordinates = {
                    'image_width': image_size[0],
                    'image_height': image_size[1]
                }
            
            # Enhance location information
            if not cta.location:
                cta.location = "Image Content"
            
            enhanced_ctas.append(cta)
        
        return enhanced_ctas
    
    def analyze_image_layout(self, image: Image.Image) -> dict:
        """Analyze image layout to understand CTA placement patterns."""
        width, height = image.size
        
        analysis = {
            'dimensions': {'width': width, 'height': height},
            'aspect_ratio': width / height if height > 0 else 1.0,
            'layout_type': self._determine_layout_type(width, height),
            'suggested_cta_zones': self._identify_cta_zones(width, height)
        }
        
        return analysis
    
    def _determine_layout_type(self, width: int, height: int) -> str:
        """Determine the layout type of the image."""
        aspect_ratio = width / height if height > 0 else 1.0
        
        if aspect_ratio > 2.0:
            return "banner"
        elif aspect_ratio > 1.5:
            return "landscape"
        elif aspect_ratio > 0.7:
            return "square"
        else:
            return "portrait"
    
    def _identify_cta_zones(self, width: int, height: int) -> List[dict]:
        """Identify common zones where CTAs are typically placed."""
        zones = []
        
        # Common CTA placement zones based on web design patterns
        
        # Top right (common for navigation CTAs)
        zones.append({
            'name': 'top_right',
            'x': int(width * 0.7),
            'y': 0,
            'width': int(width * 0.3),
            'height': int(height * 0.2),
            'priority': 'medium'
        })
        
        # Center (hero CTAs)
        zones.append({
            'name': 'center',
            'x': int(width * 0.3),
            'y': int(height * 0.4),
            'width': int(width * 0.4),
            'height': int(height * 0.2),
            'priority': 'high'
        })
        
        # Bottom center (footer CTAs)
        zones.append({
            'name': 'bottom_center',
            'x': int(width * 0.25),
            'y': int(height * 0.8),
            'width': int(width * 0.5),
            'height': int(height * 0.2),
            'priority': 'medium'
        })
        
        # Right side (sidebar CTAs)
        zones.append({
            'name': 'right_sidebar',
            'x': int(width * 0.8),
            'y': int(height * 0.3),
            'width': int(width * 0.2),
            'height': int(height * 0.4),
            'priority': 'low'
        })
        
        return zones
    
    def save_processed_image(self, image: Image.Image, filename: str) -> str:
        """Save processed image to disk and return path."""
        try:
            upload_dir = Path(self.settings.upload_dir)
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = upload_dir / filename
            image.save(str(file_path))
            
            logger.info(f"Saved processed image to {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Failed to save image: {e}")
            raise RuntimeError(f"Image save failed: {e}")
    
    def validate_image(self, image_data: str) -> bool:
        """Validate that image data is processable."""
        try:
            if ',' in image_data:
                image_data = image_data.split(',', 1)[1]
            
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            # Basic validation checks
            width, height = image.size
            
            # Check minimum dimensions
            if width < 50 or height < 50:
                logger.warning("Image too small for reliable OCR")
                return False
            
            # Check maximum dimensions (to prevent memory issues)
            if width > 5000 or height > 5000:
                logger.warning("Image too large, may cause processing issues")
                return False
            
            # Check file size (rough estimate)
            if len(image_bytes) > 10 * 1024 * 1024:  # 10MB
                logger.warning("Image file too large")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Image validation failed: {e}")
            return False
    
    def extract_ctas_with_confidence(self, image: Image.Image, confidence_threshold: float = 0.6) -> List[ExtractedCTA]:
        """Extract CTAs with confidence scoring based on OCR and positioning."""
        logger.info(f"Extracting CTAs with confidence threshold: {confidence_threshold}")
        
        # Get text with coordinates
        text_with_coords = self.extract_text_with_coordinates(image)
        
        # Filter by confidence
        high_confidence_text = [
            (text, coords) for text, coords in text_with_coords
            if coords['confidence'] >= confidence_threshold * 100  # Tesseract uses 0-100 scale
        ]
        
        logger.debug(f"Found {len(high_confidence_text)} high-confidence text segments")
        
        # Extract CTAs from high-confidence text
        ctas = []
        for text, coords in high_confidence_text:
            if self.cta_extractor._is_potential_cta(text):
                cta = ExtractedCTA(
                    id=f"img_cta_{len(ctas)}",
                    original_text=text,
                    cta_type="image_button",
                    context=f"OCR confidence: {coords['confidence']}%",
                    location=self._determine_text_location(coords, image.size),
                    coordinates=coords
                )
                ctas.append(cta)
        
        logger.info(f"Extracted {len(ctas)} high-confidence CTAs from image")
        return ctas
    
    def _determine_text_location(self, coords: dict, image_size: Tuple[int, int]) -> str:
        """Determine semantic location of text based on coordinates."""
        width, height = image_size
        x, y = coords['x'], coords['y']
        
        # Normalize coordinates to percentages
        x_pct = x / width if width > 0 else 0
        y_pct = y / height if height > 0 else 0
        
        # Determine location based on position
        if y_pct < 0.2:
            if x_pct > 0.7:
                return "Top Right"
            elif x_pct < 0.3:
                return "Top Left"
            else:
                return "Top Center"
        elif y_pct > 0.8:
            if x_pct > 0.7:
                return "Bottom Right"
            elif x_pct < 0.3:
                return "Bottom Left"
            else:
                return "Bottom Center"
        else:
            if x_pct > 0.7:
                return "Right Side"
            elif x_pct < 0.3:
                return "Left Side"
            else:
                return "Center"
    
    def get_ocr_statistics(self, image: Image.Image) -> dict:
        """Get OCR processing statistics for debugging."""
        try:
            processed_image = self._preprocess_image(image)
            
            # Get detailed OCR data
            data = pytesseract.image_to_data(
                processed_image, 
                output_type=pytesseract.Output.DICT
            )
            
            # Calculate statistics
            confidences = [conf for conf in data['conf'] if conf > 0]
            total_words = len([text for text in data['text'] if text.strip()])
            
            stats = {
                'total_text_segments': len(data['text']),
                'total_words': total_words,
                'average_confidence': sum(confidences) / len(confidences) if confidences else 0,
                'min_confidence': min(confidences) if confidences else 0,
                'max_confidence': max(confidences) if confidences else 0,
                'high_confidence_words': len([c for c in confidences if c > 80]),
                'low_confidence_words': len([c for c in confidences if c < 60]),
                'image_dimensions': image.size,
                'processed_image_mode': processed_image.mode
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to generate OCR statistics: {e}")
            return {'error': str(e)}