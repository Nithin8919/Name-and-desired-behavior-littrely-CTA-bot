# CTA Optimization Bot - Backend API

A powerful AI-powered backend service that analyzes and optimizes call-to-action (CTA) text to improve conversion rates. Built with FastAPI, OpenAI GPT, and advanced web scraping capabilities.

## Features

### 🎯 Core Functionality
- **Website Analysis**: Crawl websites and automatically extract CTAs from multiple pages
- **Text Analysis**: Analyze raw text content to identify potential CTAs
- **Image Analysis**: Use OCR to extract CTAs from images and screenshots
- **AI Optimization**: Leverage OpenAI GPT models to generate improved CTA alternatives
- **Smart Crawling**: Priority-based crawling that focuses on conversion-oriented pages

### 🛠 Advanced Capabilities
- **Context-Aware Extraction**: Understand CTA placement and surrounding content
- **CTA Classification**: Automatically categorize CTAs by type (button, link, form, etc.)
- **Semantic Analysis**: Extract CTAs from various HTML structures and patterns
- **Batch Processing**: Handle multiple CTAs efficiently with intelligent batching
- **Export Functionality**: Export results in CSV, JSON, and Excel formats

### 🧠 AI-Powered Features
- **Vague-to-Specific**: Transform vague CTAs like "Learn More" into specific actions
- **Action-Oriented**: Ensure CTAs use strong action verbs and create urgency
- **Value Proposition**: Highlight clear benefits and value in CTA text
- **Confidence Scoring**: Provide confidence scores for optimization suggestions
- **Rationale Explanation**: Get detailed explanations for each optimization

## Quick Start

### Prerequisites
- Python 3.11+
- OpenAI API Key
- Tesseract OCR (for image processing)

### Installation

1. **Clone and setup environment**:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your OpenAI API key and other settings
```

3. **Install Tesseract OCR**:

**Ubuntu/Debian**:
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-eng
```

**macOS**:
```bash
brew install tesseract
```

**Windows**:
Download from: https://github.com/UB-Mannheim/tesseract/wiki

4. **Run the server**:
```bash
python run_server.py
```

The API will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- **Interactive Docs**: `http://localhost:8000/docs`
- **Alternative Docs**: `http://localhost:8000/redoc`
- **Health Check**: `http://localhost:8000/api/v1/health`

### Key Endpoints

#### Website Analysis
```bash
POST /api/v1/analyze/url
Content-Type: application/json

{
  "url": "https://example.com",
  "max_pages": 5,
  "max_depth": 2
}
```

#### Text Analysis
```bash
POST /api/v1/analyze/text
Content-Type: application/json

{
  "text": "Your CTA text here",
  "context": "Optional context information"
}
```

#### Image Upload
```bash
POST /api/v1/upload-image
Content-Type: multipart/form-data

file: [image file]
context: "Optional context"
```

#### Job Status
```bash
GET /api/v1/jobs/{job_id}/status
```

#### Get Results
```bash
GET /api/v1/jobs/{job_id}/results
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (required) | - |
| `OPENAI_MODEL` | GPT model to use | `gpt-4` |
| `DEBUG` | Enable debug mode | `false` |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `MAX_PAGES_PER_SITE` | Max pages to crawl | `10` |
| `MAX_CRAWL_DEPTH` | Max crawl depth | `2` |
| `SCRAPER_TIMEOUT` | Request timeout (seconds) | `30` |

See `.env.example` for all available settings.

## Architecture

### Project Structure
```
backend/
├── src/
│   ├── api/                 # API endpoints and routing
│   ├── core/               # Configuration and app setup
│   ├── models/             # Pydantic schemas
│   ├── services/           # Business logic services
│   ├── utils/              # Utility functions
│   └── main.py            # FastAPI application
├── static/                # File uploads and screenshots
├── exports/              # Generated export files
├── logs/                 # Application logs
└── tests/               # Test suite
```

### Core Services

1. **CrawlerService**: Intelligent website crawling with CTA focus
2. **ScraperService**: HTML parsing and content extraction  
3. **AnalysisService**: OpenAI integration for CTA optimization
4. **OCRService**: Image text extraction using Tesseract
5. **CTAExtractor**: Specialized CTA detection and classification

## Usage Examples

### Python Client Example
```python
import httpx

# Start URL analysis
response = httpx.post("http://localhost:8000/api/v1/analyze/url", json={
    "url": "https://example.com",
    "max_pages": 5
})
job = response.json()["data"]
job_id = job["job_id"]

# Check status
status_response = httpx.get(f"http://localhost:8000/api/v1/jobs/{job_id}/status")
print(f"Status: {status_response.json()['data']['status']}")

# Get results when complete
results_response = httpx.get(f"http://localhost:8000/api/v1/jobs/{job_id}/results")
results = results_response.json()["data"]

print(f"Found {len(results['extracted_ctas'])} CTAs")
print(f"Generated {len(results['optimized_ctas'])} optimizations")
```

### cURL Examples
```bash
# Analyze a website
curl -X POST "http://localhost:8000/api/v1/analyze/url" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "max_pages": 3}'

# Upload and analyze an image
curl -X POST "http://localhost:8000/api/v1/upload-image" \
  -F "file=@screenshot.png" \
  -F "context=Landing page screenshot"

# Check job status
curl "http://localhost:8000/api/v1/jobs/your-job-id/status"
```

## Development

### Running Tests
```bash
python -m pytest tests/ -v
```

### Code Formatting
```bash
black src/ tests/
isort src/ tests/
flake8 src/ tests/
```

### Docker Development
```bash
# Build image
docker build -t cta-optimizer-api .

# Run container
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your_key_here \
  cta-optimizer-api
```

## Performance

### Optimization Features
- **Async Processing**: All I/O operations are asynchronous
- **Smart Batching**: CTAs are processed in optimized batches
- **Concurrent Crawling**: Multiple pages crawled simultaneously
- **Caching**: Response caching for repeated requests
- **Rate Limiting**: Built-in rate limiting to prevent abuse

### Scaling Recommendations
- Use Redis for job storage in production
- Implement database backend for persistence  
- Add horizontal scaling with load balancer
- Configure CDN for static file serving

## Troubleshooting

### Common Issues

**OpenAI API Errors**:
- Verify your API key is correct and has sufficient credits
- Check rate limits if getting 429 errors
- Ensure the model (gpt-4) is available for your account

**OCR Not Working**:
- Install Tesseract: `sudo apt-get install tesseract-ocr`
- Verify Tesseract path in environment variables
- Check image quality - very small or low-quality images may fail

**Crawling Issues**:
- Some websites block scrapers - this is expected behavior
- Adjust timeout settings for slow websites
- Check robots.txt compliance

### Logs and Debugging
```bash
# View logs in development
tail -f logs/app.log

# Enable debug logging
export LOG_LEVEL=DEBUG
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes with tests
4. Run the test suite: `python -m pytest`
5. Submit a pull request

## License

This project is licensed under the MIT License. See LICENSE file for details.

## Support

For issues, questions, or contributions:
- Create an issue on GitHub
- Check the documentation at `/docs` endpoint
- Review the API examples above

---

Built with ❤️ using FastAPI, OpenAI, and Python