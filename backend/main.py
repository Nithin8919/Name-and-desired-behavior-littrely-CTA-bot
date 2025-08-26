from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
import os, time
from werkzeug.utils import secure_filename
from pathlib import Path
import traceback

# Import our analyzer (will create next)
from cta_analyzer import CTALiteralAnalyzer

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configuration
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize analyzer
analyzer = None
try:
    analyzer = CTALiteralAnalyzer()
    print("✅ CTA Literal Analyzer initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize analyzer: {e}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Main page with three input options"""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """Main analysis endpoint handling URL, image, or text input"""
    if not analyzer:
        flash('Analyzer not initialized. Check OpenAI API key.', 'error')
        return redirect(url_for('index'))
        
    try:
        start_time = time.time()
        source_type = None
        source_url = None
        
        # Handle URL analysis
        if 'url' in request.form and request.form['url'].strip():
            url = request.form['url'].strip()
            print(f"🔍 Analyzing URL: {url}")
            results = analyzer.analyze_url(url)
            source_type = 'url'
            source_url = url
            
        # Handle image upload
        elif 'image' in request.files and request.files['image'].filename:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = str(int(time.time()))
                filename = f"{timestamp}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                print(f"📷 Analyzing image: {filename}")
                results = analyzer.analyze_image(filepath)
                source_type = 'image'
                source_url = filepath
            else:
                flash('Invalid image file. Please upload PNG, JPG, or GIF.', 'error')
                return redirect(url_for('index'))
                
        # Handle direct text input
        elif 'text' in request.form and request.form['text'].strip():
            text = request.form['text'].strip()
            print(f"📝 Analyzing text: {text[:100]}...")
            results = analyzer.analyze_text(text)
            source_type = 'text'
            
        else:
            flash('Please provide a URL, upload an image, or enter text to analyze.', 'error')
            return redirect(url_for('index'))
            
        if results.get('error'):
            flash(f'Analysis failed: {results["error"]}', 'error')
            return redirect(url_for('index'))
            
        # Process results for template
        extracted_ctas = results.get('extracted_ctas', [])
        optimizations = results.get('optimizations', [])
        
        # Calculate statistics
        total_ctas = len(extracted_ctas)
        avg_literalness = sum(opt.get('literalness_score', 0) for opt in optimizations) / max(len(optimizations), 1)
        processing_time = time.time() - start_time
        
        # Prepare data for template
        analysis_data = {
            'total_ctas': total_ctas,
            'avg_literalness': round(avg_literalness, 1),
            'processing_time': f"{processing_time:.1f}s",
            'source_type': source_type,
            'source_url': source_url,
            'extracted_ctas': extracted_ctas,
            'optimizations': optimizations,
            'has_improvements': len([opt for opt in optimizations if opt.get('literalness_improvement', 0) > 2]) > 0
        }
        
        return render_template('results.html', data=analysis_data)
        
    except Exception as e:
        print(f"❌ Analysis failed: {str(e)}")
        traceback.print_exc()
        flash(f'Analysis failed: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/api/update-cta', methods=['POST'])
def update_cta():
    """API endpoint to update CTA text in the editable table"""
    try:
        data = request.get_json()
        cta_id = data.get('cta_id')
        new_text = data.get('new_text', '').strip()
        
        if not cta_id or not new_text:
            return jsonify({'success': False, 'error': 'Missing CTA ID or text'})
            
        # In a real app, you'd save this to database
        # For now, just return success
        return jsonify({
            'success': True, 
            'message': f'CTA updated successfully',
            'updated_text': new_text
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/export', methods=['POST'])
def export_results():
    """Export results as CSV"""
    try:
        data = request.get_json()
        format_type = data.get('format', 'csv')
        
        # In a real app, you'd generate and return the file
        # For now, just simulate
        return jsonify({
            'success': True,
            'download_url': '/static/exports/cta_improvements.csv',
            'message': f'Results exported as {format_type.upper()}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.errorhandler(413)
def too_large(e):
    flash('File too large. Maximum size is 10MB.', 'error')
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))  # Changed default port to 8000
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    print(f"""
🎯 CTA Literally Bot Server Starting...
   
   📍 URL: http://localhost:{port}
   🔧 Debug: {debug_mode}
   🤖 Analyzer: {"✅ Ready" if analyzer else "❌ Not initialized"}
   
   Ready to make your CTAs literally better! 🚀
""")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)