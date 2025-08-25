// Global variables
let currentResults = [];
let currentAnalysisId = null;

// DOM elements
const elements = {
    inputSection: document.getElementById('inputSection'),
    resultsSection: document.getElementById('resultsSection'),
    loadingOverlay: document.getElementById('loadingOverlay'),
    messageContainer: document.getElementById('messageContainer'),
    resultsTableBody: document.getElementById('resultsTableBody'),
    resultsStats: document.getElementById('resultsStats'),
    selectAll: document.getElementById('selectAll'),
    bulkActions: document.getElementById('bulkActions'),
    urlInput: document.getElementById('urlInput'),
    imageInput: document.getElementById('imageInput'),
    textInput: document.getElementById('textInput'),
    scanWebsiteBtn: document.getElementById('scanWebsiteBtn'),
    analyzeImageBtn: document.getElementById('analyzeImageBtn'),
    analyzeTextBtn: document.getElementById('analyzeTextBtn'),
    uploadZone: document.getElementById('uploadZone'),
    historyList: document.getElementById('historyList')
};

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
    loadHistory();
});

function setupEventListeners() {
    // URL analysis
    elements.scanWebsiteBtn.addEventListener('click', analyzeUrl);
    
    // Image analysis
    elements.analyzeImageBtn.addEventListener('click', analyzeImage);
    elements.imageInput.addEventListener('change', handleImageUpload);
    setupDragAndDrop();
    
    // Text analysis
    elements.analyzeTextBtn.addEventListener('click', analyzeText);
    
    // Table interactions
    elements.selectAll.addEventListener('change', toggleSelectAll);
    elements.bulkActions.addEventListener('change', handleBulkAction);
    
    // Navigation tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', handleTabClick);
    });
}

// URL Analysis
async function analyzeUrl() {
    const url = elements.urlInput.value.trim();
    if (!url) {
        showMessage('Please enter a valid URL', 'error');
        return;
    }
    
    const maxPages = document.getElementById('maxPages').value;
    const scanDepth = document.getElementById('scanDepth').value;
    
    showLoading(true);
    
    try {
        const response = await fetch('/api/analyze-url', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url: url,
                max_pages: parseInt(maxPages),
                scan_depth: parseInt(scanDepth)
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            handleAnalysisSuccess(data);
        } else {
            showMessage(data.error || 'Analysis failed', 'error');
        }
    } catch (error) {
        showMessage('Network error. Please try again.', 'error');
        console.error('Error:', error);
    } finally {
        showLoading(false);
    }
}

// Image Analysis
async function analyzeImage() {
    const file = elements.imageInput.files[0];
    if (!file) {
        showMessage('Please select an image first', 'error');
        return;
    }
    
    showLoading(true);
    
    try {
        const formData = new FormData();
        formData.append('image', file);
        
        const response = await fetch('/api/analyze-image', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            handleAnalysisSuccess(data);
        } else {
            showMessage(data.error || 'Analysis failed', 'error');
        }
    } catch (error) {
        showMessage('Network error. Please try again.', 'error');
        console.error('Error:', error);
    } finally {
        showLoading(false);
    }
}

// Text Analysis
async function analyzeText() {
    const text = elements.textInput.value.trim();
    if (!text) {
        showMessage('Please enter some text to analyze', 'error');
        return;
    }
    
    showLoading(true);
    
    try {
        const response = await fetch('/api/analyze-text', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ text: text })
        });
        
        const data = await response.json();
        
        if (data.success) {
            handleAnalysisSuccess(data);
        } else {
            showMessage(data.error || 'Analysis failed', 'error');
        }
    } catch (error) {
        showMessage('Network error. Please try again.', 'error');
        console.error('Error:', error);
    } finally {
        showLoading(false);
    }
}

// Handle successful analysis
function handleAnalysisSuccess(data) {
    currentResults = data.results;
    currentAnalysisId = data.analysis_id;
    
    // Update stats
    elements.resultsStats.textContent = `${data.stats.ctas_analyzed} CTAs analyzed · ${data.stats.suggestions_provided} suggestions provided`;
    
    // Populate results table
    populateResultsTable(data.results);
    
    // Show results section
    showResultsSection();
    
    // Enable results tab
    document.querySelector('[data-tab="results"]').disabled = false;
    
    // Switch to results tab
    switchToTab('results');
    
    showMessage('Analysis completed successfully!', 'success');
    
    // Refresh history
    loadHistory();
}

// Populate results table
function populateResultsTable(results) {
    elements.resultsTableBody.innerHTML = '';
    
    results.forEach((result, index) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <input type="checkbox" class="result-checkbox" data-index="${index}">
            </td>
            <td>${escapeHtml(result.original_cta)}</td>
            <td>
                <input type="text" class="suggestion-input" value="${escapeHtml(result.suggested_improvement)}" data-index="${index}">
            </td>
            <td>
                <span class="confidence-${result.confidence}">${result.confidence}</span>
            </td>
            <td>${escapeHtml(result.source || 'N/A')}</td>
            <td class="action-buttons">
                <button class="action-btn accept" onclick="acceptSuggestion(${index})" title="Accept suggestion">
                    <i class="fas fa-check"></i>
                </button>
                <button class="action-btn refresh" onclick="regenerateSuggestion(${index})" title="Regenerate suggestion">
                    <i class="fas fa-sync-alt"></i>
                </button>
                <button class="action-btn copy" onclick="copyToClipboard(${index})" title="Copy to clipboard">
                    <i class="fas fa-copy"></i>
                </button>
            </td>
        `;
        elements.resultsTableBody.appendChild(row);
    });
    
    // Reset select all checkbox
    elements.selectAll.checked = false;
    elements.selectAll.indeterminate = false;
}

// Show results section
function showResultsSection() {
    elements.inputSection.style.display = 'none';
    elements.resultsSection.style.display = 'block';
}

// Show input section
function showInputSection() {
    elements.resultsSection.style.display = 'none';
    elements.inputSection.style.display = 'block';
}

// Tab navigation
function handleTabClick(event) {
    const tab = event.target;
    const tabName = tab.dataset.tab;
    
    if (tab.disabled) return;
    
    switchToTab(tabName);
}

function switchToTab(tabName) {
    // Update tab states
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    
    // Show appropriate section
    if (tabName === 'results') {
        showResultsSection();
    } else {
        showInputSection();
    }
}

// Image upload handling
function handleImageUpload(event) {
    const file = event.target.files[0];
    if (file) {
        elements.analyzeImageBtn.disabled = false;
        showMessage(`Image "${file.name}" selected`, 'success');
    }
}

// Drag and drop setup
function setupDragAndDrop() {
    const uploadZone = elements.uploadZone;
    
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadZone.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadZone.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        uploadZone.addEventListener(eventName, unhighlight, false);
    });
    
    function highlight(e) {
        uploadZone.classList.add('dragover');
    }
    
    function unhighlight(e) {
        uploadZone.classList.remove('dragover');
    }
    
    uploadZone.addEventListener('drop', handleDrop, false);
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        
        if (files.length > 0) {
            elements.imageInput.files = files;
            elements.analyzeImageBtn.disabled = false;
            showMessage(`Image "${files[0].name}" uploaded`, 'success');
        }
    }
}

// Table interactions
function toggleSelectAll() {
    const checkboxes = document.querySelectorAll('.result-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = elements.selectAll.checked;
    });
}

function handleBulkAction() {
    const action = elements.bulkActions.value;
    if (!action) return;
    
    const checkboxes = document.querySelectorAll('.result-checkbox:checked');
    if (checkboxes.length === 0) {
        showMessage('Please select items first', 'error');
        return;
    }
    
    switch (action) {
        case 'accept-all':
            checkboxes.forEach(checkbox => {
                const index = parseInt(checkbox.dataset.index);
                acceptSuggestion(index);
            });
            break;
        case 'revert-all':
            checkboxes.forEach(checkbox => {
                const index = parseInt(checkbox.dataset.index);
                revertSuggestion(index);
            });
            break;
    }
    
    // Reset bulk actions
    elements.bulkActions.value = '';
}

// Individual actions
function acceptSuggestion(index) {
    const suggestionInput = document.querySelector(`.suggestion-input[data-index="${index}"]`);
    const originalCta = currentResults[index].original_cta;
    
    // Update the original CTA with the suggestion
    currentResults[index].original_cta = suggestionInput.value;
    
    // Update the table row
    const row = suggestionInput.closest('tr');
    const originalCell = row.cells[1];
    originalCell.textContent = suggestionInput.value;
    
    showMessage('Suggestion accepted', 'success');
}

function regenerateSuggestion(index) {
    // In a real implementation, this would call the API to regenerate
    showMessage('Regenerating suggestion...', 'success');
    
    // For demo purposes, just show a message
    setTimeout(() => {
        showMessage('Suggestion regenerated', 'success');
    }, 1000);
}

function revertSuggestion(index) {
    const suggestionInput = document.querySelector(`.suggestion-input[data-index="${index}"]`);
    const originalCta = currentResults[index].original_cta;
    
    // Revert to original suggestion
    suggestionInput.value = originalCta;
    
    showMessage('Suggestion reverted', 'success');
}

async function copyToClipboard(index) {
    const suggestionInput = document.querySelector(`.suggestion-input[data-index="${index}"]`);
    const text = suggestionInput.value;
    
    try {
        await navigator.clipboard.writeText(text);
        showMessage('Copied to clipboard!', 'success');
    } catch (err) {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        showMessage('Copied to clipboard!', 'success');
    }
}

// Export functionality
async function exportResults(format) {
    if (!currentResults || currentResults.length === 0) {
        showMessage('No results to export', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/export-results', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                results: currentResults,
                format: format
            })
        });
        
        if (format === 'csv') {
            // Download CSV file
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `cta_optimization_results_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } else {
            // Show JSON in new window
            const data = await response.json();
            const newWindow = window.open();
            newWindow.document.write('<pre>' + JSON.stringify(data, null, 2) + '</pre>');
        }
        
        showMessage(`Results exported as ${format.toUpperCase()}`, 'success');
    } catch (error) {
        showMessage('Export failed', 'error');
        console.error('Export error:', error);
    }
}

// Download optimized CTAs
function downloadOptimizedCTAs() {
    if (!currentResults || currentResults.length === 0) {
        showMessage('No results to download', 'error');
        return;
    }
    
    // Create CSV content
    let csvContent = 'Original CTA,Optimized CTA,Confidence,Source\n';
    
    currentResults.forEach(result => {
        const original = `"${result.original_cta.replace(/"/g, '""')}"`;
        const optimized = `"${result.suggested_improvement.replace(/"/g, '""')}"`;
        const confidence = `"${result.confidence}"`;
        const source = `"${result.source || ''}"`;
        
        csvContent += `${original},${optimized},${confidence},${source}\n`;
    });
    
    // Download file
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `optimized_ctas_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    
    showMessage('Optimized CTAs downloaded', 'success');
}

// Start new analysis
function startNewAnalysis() {
    // Reset form inputs
    elements.urlInput.value = '';
    elements.imageInput.value = '';
    elements.textInput.value = '';
    elements.analyzeImageBtn.disabled = true;
    
    // Clear results
    currentResults = [];
    currentAnalysisId = null;
    
    // Reset table
    elements.resultsTableBody.innerHTML = '';
    elements.resultsStats.textContent = '0 CTAs analyzed · 0 suggestions provided';
    
    // Disable results tab
    document.querySelector('[data-tab="results"]').disabled = true;
    
    // Switch to input tab
    switchToTab('input');
    
    showMessage('Ready for new analysis', 'success');
}

// History functionality
async function loadHistory() {
    try {
        const response = await fetch('/api/history');
        const history = await response.json();
        
        populateHistory(history);
    } catch (error) {
        console.error('Failed to load history:', error);
    }
}

function populateHistory(history) {
    if (!elements.historyList) return;
    
    elements.historyList.innerHTML = '';
    
    if (history.length === 0) {
        elements.historyList.innerHTML = '<p style="color: #6b7280; text-align: center;">No analyses yet</p>';
        return;
    }
    
    // Show last 5 analyses
    const recentHistory = history.slice(-5).reverse();
    
    recentHistory.forEach(item => {
        const historyItem = document.createElement('div');
        historyItem.className = 'history-item';
        
        const date = new Date(item.timestamp).toLocaleDateString();
        const time = new Date(item.timestamp).toLocaleTimeString();
        
        historyItem.innerHTML = `
            <div class="history-info">
                <div class="history-type">${item.type}</div>
                <div class="history-input">${item.input.length > 50 ? item.input.substring(0, 50) + '...' : item.input}</div>
                <div class="history-date">${date} at ${time}</div>
            </div>
            <div class="history-cta-count">${item.results.length} CTAs</div>
        `;
        
        historyItem.addEventListener('click', () => loadHistoryResults(item));
        elements.historyList.appendChild(historyItem);
    });
}

function loadHistoryResults(historyItem) {
    currentResults = historyItem.results;
    currentAnalysisId = historyItem.id;
    
    // Update stats
    elements.resultsStats.textContent = `${historyItem.results.length} CTAs analyzed · ${historyItem.results.length} suggestions provided`;
    
    // Populate results table
    populateResultsTable(historyItem.results);
    
    // Show results section
    showResultsSection();
    
    // Enable results tab
    document.querySelector('[data-tab="results"]').disabled = false;
    
    // Switch to results tab
    switchToTab('results');
    
    showMessage('History results loaded', 'success');
}

// Utility functions
function showLoading(show) {
    elements.loadingOverlay.style.display = show ? 'flex' : 'none';
}

function showMessage(text, type = 'success') {
    const message = document.createElement('div');
    message.className = `message ${type}`;
    
    const icon = type === 'success' ? 'fas fa-check-circle' : 'fas fa-exclamation-circle';
    
    message.innerHTML = `
        <i class="${icon}"></i>
        <span>${text}</span>
    `;
    
    elements.messageContainer.appendChild(message);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (message.parentNode) {
            message.parentNode.removeChild(message);
        }
    }, 5000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function toggleOptions(optionId) {
    const optionsPanel = document.getElementById(optionId);
    optionsPanel.style.display = optionsPanel.style.display === 'none' ? 'block' : 'none';
}

function toggleHistory() {
    const historyContent = document.getElementById('historyContent');
    const historyChevron = document.getElementById('historyChevron');
    
    if (historyContent.style.display === 'none') {
        historyContent.style.display = 'block';
        historyChevron.style.transform = 'rotate(180deg)';
    } else {
        historyContent.style.display = 'none';
        historyChevron.style.transform = 'rotate(0deg)';
    }
}

// Global function exports for HTML onclick handlers
window.exportResults = exportResults;
window.downloadOptimizedCTAs = downloadOptimizedCTAs;
window.startNewAnalysis = startNewAnalysis;
window.acceptSuggestion = acceptSuggestion;
window.regenerateSuggestion = regenerateSuggestion;
window.copyToClipboard = copyToClipboard;
window.toggleOptions = toggleOptions;
window.toggleHistory = toggleHistory;
