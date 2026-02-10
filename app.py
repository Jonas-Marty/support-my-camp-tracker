#!/usr/bin/env python3
"""
Migros SupportMyCamp Voucher Tracker - Web Interface

Flask application serving a mobile-optimized website for viewing club voucher statistics.
"""

import json
import logging
from pathlib import Path

from flask import Flask, render_template_string, send_from_directory

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
LATEST_FILE = DATA_DIR / "latest.json"

# HTML Template with inline CSS and JavaScript
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Migros SupportMyCamp - Voucher Tracker</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            color: #333;
            padding: 10px;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        header {
            background: linear-gradient(135deg, #ff6b00 0%, #ff8c00 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        h1 {
            font-size: 1.8em;
            margin-bottom: 10px;
        }
        
        .header-info {
            display: flex;
            flex-direction: column;
            gap: 8px;
            font-size: 0.95em;
        }
        
        .voucher-worth {
            font-size: 1.3em;
            font-weight: bold;
            background: rgba(255, 255, 255, 0.2);
            padding: 10px;
            border-radius: 5px;
            margin-top: 10px;
        }
        
        .search-container {
            background: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        
        .search-input {
            width: 100%;
            padding: 12px;
            font-size: 16px;
            border: 2px solid #ddd;
            border-radius: 5px;
            transition: border-color 0.3s;
        }
        
        .search-input:focus {
            outline: none;
            border-color: #ff6b00;
        }
        
        .stats-summary {
            background: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        .clubs-container {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        
        .club-card {
            background: white;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .club-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
        }
        
        .club-name {
            font-size: 1.1em;
            font-weight: bold;
            color: #ff6b00;
            margin-bottom: 8px;
        }
        
        .club-stats {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            font-size: 0.9em;
        }
        
        .stat-item {
            display: flex;
            flex-direction: column;
        }
        
        .stat-label {
            color: #666;
            font-size: 0.85em;
            margin-bottom: 2px;
        }
        
        .stat-value {
            font-weight: bold;
            color: #333;
        }
        
        .stat-value.highlight {
            color: #ff6b00;
            font-size: 1.1em;
        }
        
        .no-results {
            background: white;
            padding: 40px 20px;
            border-radius: 10px;
            text-align: center;
            color: #666;
            font-size: 1.1em;
        }
        
        .error-message {
            background: #fee;
            color: #c33;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
            border: 2px solid #fcc;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            font-size: 1.2em;
            color: #666;
        }
        
        /* Tablet and Desktop */
        @media (min-width: 768px) {
            h1 {
                font-size: 2.2em;
            }
            
            .header-info {
                flex-direction: row;
                justify-content: space-between;
                align-items: center;
            }
            
            .clubs-container {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
                gap: 15px;
            }
            
            .stats-summary {
                flex-direction: row;
                justify-content: space-around;
                align-items: center;
            }
        }
        
        @media (min-width: 1024px) {
            .clubs-container {
                grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎫 Migros SupportMyCamp</h1>
            <div class="header-info">
                <div>Voucher Tracker 2025</div>
                <div id="lastUpdate">Wird geladen...</div>
            </div>
            <div class="voucher-worth" id="voucherWorth">Wird geladen...</div>
        </header>
        
        <div class="search-container">
            <input 
                type="text" 
                id="searchInput" 
                class="search-input" 
                placeholder="🔍 Verein suchen..."
                autocomplete="off"
            >
        </div>
        
        <div class="stats-summary" id="statsSummary">
            <div><strong>Clubs:</strong> <span id="totalClubs">-</span></div>
            <div><strong>Vouchers:</strong> <span id="totalVouchers">-</span></div>
            <div><strong>Prize Pool:</strong> CHF 3'000'000</div>
        </div>
        
        <div id="clubsContainer" class="loading">
            Daten werden geladen...
        </div>
    </div>
    
    <script>
        let allClubs = [];
        let searchTimeout = null;
        const DEBOUNCE_DELAY = 300; // ms
        
        // Format number with thousands separator
        function formatNumber(num) {
            return num.toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g, "'");
        }
        
        // Format currency
        function formatCurrency(amount) {
            return `CHF ${formatNumber(amount.toFixed(2))}`;
        }
        
        // Format date
        function formatDate(isoString) {
            const date = new Date(isoString);
            return date.toLocaleString('de-CH', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        }
        
        // Render clubs
        function renderClubs(clubs) {
            const container = document.getElementById('clubsContainer');
            
            if (clubs.length === 0) {
                container.innerHTML = '<div class="no-results">Keine Vereine gefunden</div>';
                return;
            }
            
            container.innerHTML = clubs.map(club => `
                <div class="club-card">
                    <div class="club-name">${escapeHtml(club.name)}</div>
                    <div class="club-stats">
                        <div class="stat-item">
                            <span class="stat-label">Vouchers</span>
                            <span class="stat-value highlight">${formatNumber(club.voucherCount)}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Voraussichtlich</span>
                            <span class="stat-value highlight">${formatCurrency(club.estimatedPayout)}</span>
                        </div>
                        ${club.leaderboardRank ? `
                        <div class="stat-item">
                            <span class="stat-label">Rang</span>
                            <span class="stat-value">${formatNumber(club.leaderboardRank)}</span>
                        </div>
                        ` : ''}
                        ${club.fanCount ? `
                        <div class="stat-item">
                            <span class="stat-label">Fans</span>
                            <span class="stat-value">${formatNumber(club.fanCount)}</span>
                        </div>
                        ` : ''}
                    </div>
                </div>
            `).join('');
        }
        
        // Escape HTML to prevent XSS
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Filter clubs based on search query
        function filterClubs(query) {
            const lowerQuery = query.toLowerCase().trim();
            
            if (!lowerQuery) {
                return allClubs;
            }
            
            return allClubs.filter(club => 
                club.name.toLowerCase().includes(lowerQuery)
            );
        }
        
        // Handle search input with debouncing
        function handleSearch(event) {
            const query = event.target.value;
            
            // Clear previous timeout
            if (searchTimeout) {
                clearTimeout(searchTimeout);
            }
            
            // Set new timeout for debouncing
            searchTimeout = setTimeout(() => {
                const filteredClubs = filterClubs(query);
                renderClubs(filteredClubs);
            }, DEBOUNCE_DELAY);
        }
        
        // Load data
        async function loadData() {
            try {
                const response = await fetch('/data/latest.json');
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const data = await response.json();
                
                // Store clubs data
                allClubs = data.clubs || [];
                
                // Sort clubs by voucher count (descending)
                allClubs.sort((a, b) => b.voucherCount - a.voucherCount);
                
                // Update header info
                const metadata = data.metadata || {};
                document.getElementById('voucherWorth').textContent = 
                    `1 Voucher = ${formatCurrency(metadata.voucherWorth || 0)}`;
                document.getElementById('lastUpdate').textContent = 
                    `Stand: ${formatDate(metadata.timestamp)}`;
                
                // Update stats summary
                document.getElementById('totalClubs').textContent = 
                    formatNumber(metadata.totalClubs || 0);
                document.getElementById('totalVouchers').textContent = 
                    formatNumber(metadata.totalVouchers || 0);
                
                // Render all clubs initially
                renderClubs(allClubs);
                
            } catch (error) {
                console.error('Error loading data:', error);
                document.getElementById('clubsContainer').innerHTML = `
                    <div class="error-message">
                        <strong>Fehler beim Laden der Daten</strong><br>
                        ${escapeHtml(error.message)}<br><br>
                        Bitte versuchen Sie es später erneut oder kontaktieren Sie den Administrator.
                    </div>
                `;
            }
        }
        
        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            // Set up search input listener
            document.getElementById('searchInput').addEventListener('input', handleSearch);
            
            // Load data
            loadData();
        });
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """Render the main page"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/data/<path:filename>')
def serve_data(filename):
    """Serve data files"""
    return send_from_directory(DATA_DIR, filename)


if __name__ == '__main__':
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)
