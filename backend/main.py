# main.py - CTA Optimization Bot
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, send_file
from flask_cors import CORS
import os, time, base64, requests, json, re
from io import BytesIO
from PIL import Image
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

# Import the analyzer (using the same robust analyzer but with updated system prompt)
try:
    from robust_analyzer import RobustCTAAnalyzer
    ANALYZER_TYPE = "robust"
except ImportError:
    try:
        from enhanced_analyzer import FixedCTAAnalyzer as RobustCTAAnalyzer
        ANALYZER_TYPE = "enhanced"
    except ImportError:
        from analyzer import CTAAnalyzer as RobustCTAAnalyzer
        ANALYZER_TYPE = "basic"

# Pillow compatibility
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

app = Flask(__name__)
app.secret_key = 'cta-optimization-bot-secret-key-2024'
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# Initialize the robust analyzer
try:
    analyzer = RobustCTAAnalyzer()
    print(f"✅ {ANALYZER_TYPE.title()} CTA Optimization Bot initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize analyzer: {e}")
    analyzer = None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png','jpg','jpeg','gif','bmp','webp'}

def _ensure_min_width(img: Image.Image, min_w: int = 1024):
    """Upscale narrow screenshots for better OCR"""
    if img.width >= min_w:
        return img, None
    scale = float(min_w) / float(img.width)
    new_size = (min_w, int(round(img.height * scale)))
    up = img.resize(new_size, Image.LANCZOS)
    buf = BytesIO()
    up.save(buf, format="PNG")
    return up, buf.getvalue()

# CTA optimization is now handled by the RobustCTAAnalyzer class methods

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/optimize', methods=['POST'])
def optimize_ctas():
    """Main CTA optimization endpoint"""
    if not analyzer:
        flash('Analyzer not initialized. Please check server configuration.', 'error')
        return redirect(url_for('index'))
    
    design_url = request.form.get('design_url', '').strip()
    desired_behavior = request.form.get('desired_behavior', '').strip()
    
    try:
        start = time.time()
        results = None
        image_bytes = b''
        filename = None
        
        # URL Analysis
        if design_url:
            print(f"🌐 Starting CTA optimization for URL: {design_url}")
            
            # Use the new CTA optimization method
            optimization_results = analyzer.optimize_from_url(design_url, desired_behavior)
            
            if optimization_results.get('error'):
                flash(f'URL analysis failed: {optimization_results.get("message", "Unknown error")}', 'error')
                return redirect(url_for('index'))
            
            source_type = 'URL'
            filename = design_url.split('/')[-1] or 'webpage-analysis'
            meta = optimization_results.get('meta', {})
            image_dims = f"{meta.get('width', 'N/A')}x{meta.get('height', 'N/A')}"
            
        # File Upload Analysis
        elif 'file' in request.files and request.files['file'].filename:
            print("📁 Starting file upload CTA optimization")
            file = request.files['file']
            if not allowed_file(file.filename):
                flash('Invalid file type. Upload PNG/JPG/JPEG/GIF/BMP/WebP', 'error')
                return redirect(url_for('index'))
                
            try:
                source_type = 'Upload'
                image_bytes = file.read()
                image = Image.open(BytesIO(image_bytes)).convert('RGB')
                filename = secure_filename(file.filename)
                
                # Optional upscale for better OCR
                image, up_bytes = _ensure_min_width(image, min_w=1024)
                if up_bytes is not None:
                    image_bytes = up_bytes

                # Use the new CTA optimization method for images
                optimization_results = analyzer.optimize_from_image(image, desired_behavior)
                
                if optimization_results.get('error'):
                    flash(f'Image analysis failed: {optimization_results.get("message", "Unknown error")}', 'error')
                    return redirect(url_for('index'))
                
                image_dims = f"{image.width}x{image.height}"
                
            except Exception as e:
                flash(f'Error processing upload: {str(e)}', 'error')
                return redirect(url_for('index'))
        else:
            flash('Provide a design URL or upload an image', 'error')
            return redirect(url_for('index'))

        processing_time = round(time.time() - start, 2)
        print(f"✅ CTA Optimization completed in {processing_time}s")

        # Process results for template
        optimizations = optimization_results.get('optimizations', [])
        summary = optimization_results.get('summary', {})
        
        optimization_data = {
            'optimizations': optimizations,
            'summary': summary,
            'image_data': base64.b64encode(image_bytes).decode('utf-8') if image_bytes else '',
            'filename': filename,
            'processing_time': processing_time,
            'image_dims': image_dims if 'image_dims' in locals() else 'N/A',
            'desired_behavior': desired_behavior,
            'design_source': source_type,
            'source_url': design_url if design_url else None,
            'analyzer_type': ANALYZER_TYPE,
            'total_ctas_found': len(optimizations)
        }
        
        return render_template('results.html', data=optimization_data)
        
    except Exception as e:
        print(f"❌ Optimization failed: {str(e)}")
        flash(f'CTA optimization failed: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/api/optimize', methods=['POST'])
def api_optimize():
    """API endpoint for CTA optimization"""
    if not analyzer:
        return jsonify({"error": "Analyzer not initialized"}), 500
        
    try:
        start = time.time()
        
        # Handle JSON requests (URL analysis)
        if request.is_json:
            data = request.get_json()
            design_url = data.get('design_url', '').strip()
            desired_behavior = data.get('desired_behavior', '').strip()
            
            if not design_url:
                return jsonify({"error": "No design_url provided"}), 400
                
            # Extract CTAs first
            raw_results = analyzer.analyze_url(design_url, desired_behavior=desired_behavior)
            
            if raw_results.get('error'):
                return jsonify({"error": raw_results.get('message', 'URL analysis failed')}), 500
                
            cta_texts = extract_cta_texts(raw_results.get('ctas', []))
            if not cta_texts:
                return jsonify({"error": "No CTAs found on webpage"}), 400
                
            # Optimize CTAs
            optimization_results = optimize_ctas_with_ai(cta_texts, desired_behavior, analyzer)
            
        # Handle file uploads
        else:
            if 'image' not in request.files:
                return jsonify({"error": "No image file provided"}), 400
                
            f = request.files['image']
            if f.filename == '':
                return jsonify({"error": "No image file selected"}), 400
                
            if not allowed_file(f.filename):
                return jsonify({"error": "Invalid file type"}), 400

            desired_behavior = request.form.get('desired_behavior', '').strip()

            image_bytes = f.read()
            image = Image.open(BytesIO(image_bytes)).convert('RGB')
            image, _ = _ensure_min_width(image, min_w=1024)

            # Extract CTAs first
            raw_results = analyzer.analyze(image, desired_behavior=desired_behavior)
            cta_texts = extract_cta_texts(raw_results.get('ctas', []))
            
            if not cta_texts:
                return jsonify({"error": "No CTAs found in image"}), 400
                
            # Optimize CTAs
            optimization_results = optimize_ctas_with_ai(cta_texts, desired_behavior, analyzer)

        processing_time = round(time.time() - start, 2)

        # Format API response
        api_response = {
            "success": True,
            "optimizations": optimization_results.get("optimizations", []),
            "summary": optimization_results.get("summary", {}),
            "meta": {
                "processing_time": f"{processing_time}s",
                "desired_behavior": desired_behavior or None,
                "analyzer_type": ANALYZER_TYPE,
                "total_ctas_optimized": len(optimization_results.get("optimizations", []))
            }
        }
        
        return jsonify(api_response)
        
    except Exception as e:
        print(f"❌ API Error: {e}")
        return jsonify({"error": f"Processing failed: {e}"}), 500

@app.get('/api/health')
def health():
    analyzer_status = "healthy" if analyzer else "error"
    
    return {
        "status": analyzer_status, 
        "service": "CTA Optimization Bot API", 
        "version": "1.0.0",
        "features": [
            "cta_extraction", 
            "ai_optimization", 
            "url_analysis",
            "image_analysis", 
            "editable_results",
            "csv_export"
        ],
        "analyzer_initialized": analyzer is not None,
        "analyzer_type": ANALYZER_TYPE
    }

@app.route('/debug')
def debug_analyzer():
    """Debug endpoint to check analyzer capabilities"""
    if not analyzer:
        return jsonify({"error": "Analyzer not initialized"})
    
    debug_info = {
        "analyzer_type": ANALYZER_TYPE,
        "methods_available": getattr(analyzer, 'methods', {}),
        "ocr_initialized": hasattr(analyzer, 'ocr'),
        "client_initialized": hasattr(analyzer, 'client'),
        "model": getattr(analyzer, 'model', 'unknown'),
        "optimization_mode": "enabled"
    }
    
    return jsonify(debug_info)

@app.route('/download-csv', methods=['POST'])
def download_csv():
    """Generate and download optimization results as CSV"""
    try:
        data = request.get_json()
        if not data or 'optimizations' not in data:
            return jsonify({"error": "No optimization data provided"}), 400
            
        import csv
        from io import StringIO
        
        # Create CSV in memory
        output = StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow([
            'Original CTA',
            'Optimized CTA', 
            'Original Score',
            'Improved Score',
            'Improvement',
            'Rationale',
            'Action Words Added',
            'Specificity Added',
            'Confidence Score'
        ])
        
        # Write data
        for opt in data.get('optimizations', []):
            writer.writerow([
                opt.get('original_text', ''),
                opt.get('optimized_text', ''),
                opt.get('literalness_score', ''),
                opt.get('literalness_improvement', ''),
                opt.get('literalness_improvement', 0) - opt.get('literalness_score', 0),
                opt.get('improvement_rationale', ''),
                ', '.join(opt.get('action_words_added', [])),
                opt.get('specificity_added', ''),
                opt.get('confidence_score', '')
            ])
        
        # Create response
        csv_content = output.getvalue()
        output.close()
        
        response = app.response_class(
            csv_content,
            mimetype='text/csv',
            headers={"Content-disposition": f"attachment; filename=cta-optimizations-{int(time.time())}.csv"}
        )
        
        return response
        
    except Exception as e:
        print(f"❌ CSV generation failed: {e}")
        return jsonify({"error": f"CSV generation failed: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    print("🚀 Starting CTA Optimization Bot...")
    print(f"📡 Server will run on port {port}")
    print(f"🔧 Debug mode: {debug_mode}")
    print(f"🤖 Analyzer type: {ANALYZER_TYPE}")
    
    if analyzer:
        print("✅ CTA Optimization Bot ready!")
        print("🎯 Transform vague CTAs into high-converting actions!")
    else:
        print("❌ Analyzer not initialized - check your configuration")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)