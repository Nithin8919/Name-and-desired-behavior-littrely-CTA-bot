from flask import Flask, render_template, request, jsonify, send_file
import os
import json
from datetime import datetime
import io
import csv

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cta-optimization-bot-secret-key'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Store analysis history in memory (in production, use a database)
analysis_history = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/analyze-url', methods=['POST'])
def analyze_url():
    data = request.get_json()
    url = data.get('url')
    max_pages = data.get('max_pages', 5)
    scan_depth = data.get('scan_depth', 2)
    
    # Simulate API call to backend
    # In production, this would call your FastAPI backend
    analysis_id = f"url_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Mock results for demonstration
    mock_results = [
        {
            'original_cta': 'Get Started',
            'suggested_improvement': 'Start Your Free Trial Today',
            'confidence': 'high',
            'source': 'Homepage Hero Section'
        },
        {
            'original_cta': 'Learn More',
            'suggested_improvement': 'Discover How It Works',
            'confidence': 'medium',
            'source': 'Features Section'
        },
        {
            'original_cta': 'Download',
            'suggested_improvement': 'Download Free Version Now',
            'confidence': 'high',
            'source': 'Download Section'
        }
    ]
    
    # Save to history
    analysis_history.append({
        'id': analysis_id,
        'type': 'url',
        'input': url,
        'timestamp': datetime.now().isoformat(),
        'results': mock_results
    })
    
    return jsonify({
        'success': True,
        'analysis_id': analysis_id,
        'results': mock_results,
        'stats': {
            'ctas_analyzed': len(mock_results),
            'suggestions_provided': len(mock_results)
        }
    })

@app.route('/api/analyze-image', methods=['POST'])
def analyze_image():
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image uploaded'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    # Simulate OCR processing
    analysis_id = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Mock results for demonstration
    mock_results = [
        {
            'original_cta': 'Sign Up Now',
            'suggested_improvement': 'Create Your Account in 30 Seconds',
            'confidence': 'high',
            'source': 'Image Upload'
        },
        {
            'original_cta': 'Contact Us',
            'suggested_improvement': 'Get in Touch Today',
            'confidence': 'medium',
            'source': 'Image Upload'
        }
    ]
    
    # Save to history
    analysis_history.append({
        'id': analysis_id,
        'type': 'image',
        'input': file.filename,
        'timestamp': datetime.now().isoformat(),
        'results': mock_results
    })
    
    return jsonify({
        'success': True,
        'analysis_id': analysis_id,
        'results': mock_results,
        'stats': {
            'ctas_analyzed': len(mock_results),
            'suggestions_provided': len(mock_results)
        }
    })

@app.route('/api/analyze-text', methods=['POST'])
def analyze_text():
    data = request.get_json()
    text = data.get('text', '')
    
    if not text.strip():
        return jsonify({'success': False, 'error': 'No text provided'}), 400
    
    # Split text into lines and analyze each
    ctas = [line.strip() for line in text.split('\n') if line.strip()]
    
    analysis_id = f"text_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Mock results for demonstration
    mock_results = []
    for cta in ctas:
        mock_results.append({
            'original_cta': cta,
            'suggested_improvement': f"Optimized: {cta}",
            'confidence': 'high' if len(cta) > 10 else 'medium',
            'source': 'Direct Text Input'
        })
    
    # Save to history
    analysis_history.append({
        'id': analysis_id,
        'type': 'text',
        'input': text,
        'timestamp': datetime.now().isoformat(),
        'results': mock_results
    })
    
    return jsonify({
        'success': True,
        'analysis_id': analysis_id,
        'results': mock_results,
        'stats': {
            'ctas_analyzed': len(mock_results),
            'suggestions_provided': len(mock_results)
        }
    })

@app.route('/api/export-results', methods=['POST'])
def export_results():
    data = request.get_json()
    results = data.get('results', [])
    format_type = data.get('format', 'csv')
    
    if format_type == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Original CTA', 'Suggested Improvement', 'Confidence', 'Source'])
        
        for result in results:
            writer.writerow([
                result['original_cta'],
                result['suggested_improvement'],
                result['confidence'],
                result.get('source', '')
            ])
        
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'cta_optimization_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
    
    elif format_type == 'json':
        return jsonify(results)
    
    return jsonify({'success': False, 'error': 'Unsupported format'}), 400

@app.route('/api/history')
def get_history():
    return jsonify(analysis_history)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5005)
