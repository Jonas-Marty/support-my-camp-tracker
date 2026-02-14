#!/usr/bin/env python3
"""
Migros SupportMyCamp Voucher Tracker - Web Interface

Flask application serving a mobile-optimized website for viewing club voucher statistics.
"""

import json
import logging
import csv
from pathlib import Path

from flask import Flask, render_template_string, send_from_directory, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
LATEST_FILE = DATA_DIR / "latest.json"
PREDICTIONS_DIR = DATA_DIR / "predictions"
PREDICTIONS_FILE = PREDICTIONS_DIR / "predictions_latest.csv"
WORTH_TIMELINE_FILE = PREDICTIONS_DIR / "voucher_worth_timeline_latest.csv"

# HTML Template with inline CSS and JavaScript
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Migros SupportMyCamp - Voucher Tracker</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
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
                <div>Migros Vereinsbon Tracker 2026</div>
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
        
        <!-- Charts Section -->
        <div class="charts-section" style="background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);">
            <h2 style="margin-bottom: 20px; font-size: 1.3em;">📈 Bon-Wert & Bon-Anzahl Prognose</h2>
            <div style="height: 350px; position: relative;">
                <canvas id="worthChart"></canvas>
            </div>
        </div>

        <div id="clubChartSection" style="display: none; background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);">
            <h2 id="clubChartTitle" style="margin-bottom: 20px; font-size: 1.3em;"></h2>
            <div style="height: 350px; position: relative;">
                <canvas id="clubChart"></canvas>
            </div>
            <button onclick="document.getElementById('clubChartSection').style.display='none'" 
                    style="margin-top: 15px; padding: 10px 20px; background: #ff6b00; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 1em;">
                Schliessen
            </button>
        </div>
        
        <div class="stats-summary" id="statsSummary">
            <div><strong>Vereine:</strong> <span id="totalClubs">-</span></div>
            <div><strong>Total eingelöste Vereinsbons:</strong> <span id="totalVouchers">-</span></div>
            <div><strong>Fördertopf:</strong> CHF 3'000'000</div>
        </div>
        
        <div id="clubsContainer" class="loading">
            Daten werden geladen...
        </div>
    </div>
    
    <script>
        let allClubs = [];
        let searchTimeout = null;
        const DEBOUNCE_DELAY = 300; // ms
        let worthChart = null;
        let clubChart = null;
        
        // Format number with thousands separator
        function formatNumber(num) {
            return num.toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g, "'");
        }
        
        // Format currency
        function formatCurrency(amount) {
            return `CHF ${formatNumber(amount.toFixed(2))}`;
        }
        
        // Format date (converts UTC to local timezone)
        function formatDate(isoString) {
            // Ensure the timestamp is treated as UTC by adding 'Z' if not present
            let utcString = isoString;
            if (!isoString.endsWith('Z') && !isoString.includes('+') && !isoString.includes('Z')) {
                utcString = isoString + 'Z';
            }
            const date = new Date(utcString);
            return date.toLocaleString('de-CH', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        }
        
        // Load voucher worth timeline chart
        async function loadWorthTimeline() {
            try {
                const response = await fetch('/api/predictions/worth-timeline');
                if (!response.ok) {
                    console.log('Predictions not yet available');
                    return;
                }
                
                const data = await response.json();
                const ctx = document.getElementById('worthChart').getContext('2d');
                
                if (worthChart) {
                    worthChart.destroy();
                }
                
                worthChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: data.map(d => new Date(d.timestamp).toLocaleDateString('de-CH', {day: '2-digit', month: '2-digit'})),
                        datasets: [
                            {
                                label: 'Bon-Wert (CHF)',
                                data: data.map(d => d.worth),
                                borderColor: '#ff6b00',
                                backgroundColor: 'rgba(255, 107, 0, 0.1)',
                                yAxisID: 'y',
                                tension: 0.4,
                                fill: true,
                                pointRadius: 2,
                                pointHoverRadius: 6
                            },
                            {
                                label: 'Prognostizierte Bons (Total)',
                                data: data.map(d => d.vouchers),
                                borderColor: '#0066cc',
                                backgroundColor: 'rgba(0, 102, 204, 0.1)',
                                yAxisID: 'y1',
                                tension: 0.4,
                                fill: true,
                                pointRadius: 2,
                                pointHoverRadius: 6
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {
                            mode: 'index',
                            intersect: false,
                        },
                        plugins: {
                            legend: {
                                display: true,
                                position: 'top'
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        if (context.datasetIndex === 0) {
                                            return context.dataset.label + ': CHF ' + context.parsed.y.toFixed(2);
                                        } else {
                                            return context.dataset.label + ': ' + context.parsed.y.toLocaleString('de-CH');
                                        }
                                    }
                                }
                            }
                        },
                        scales: {
                            y: {
                                type: 'linear',
                                display: true,
                                position: 'left',
                                title: {
                                    display: true,
                                    text: 'Bon-Wert (CHF)'
                                },
                                beginAtZero: false,
                                ticks: {
                                    callback: function(value) {
                                        return 'CHF ' + value.toFixed(2);
                                    }
                                }
                            },
                            y1: {
                                type: 'linear',
                                display: true,
                                position: 'right',
                                title: {
                                    display: true,
                                    text: 'Total Bons'
                                },
                                grid: {
                                    drawOnChartArea: false,
                                },
                                ticks: {
                                    callback: function(value) {
                                        return value.toLocaleString('de-CH');
                                    }
                                }
                            }
                        }
                    }
                });
            } catch (error) {
                console.error('Error loading worth timeline:', error);
            }
        }

        // Load club predictions chart
        async function loadClubPredictions(clubId, clubName) {
            try {
                const response = await fetch(`/api/predictions/club/${clubId}`);
                if (!response.ok) {
                    console.log('Club predictions not available');
                    return;
                }
                
                const data = await response.json();
                
                document.getElementById('clubChartTitle').textContent = `📊 Prognose für ${clubName}`;
                document.getElementById('clubChartSection').style.display = 'block';
                
                const ctx = document.getElementById('clubChart').getContext('2d');
                
                if (clubChart) {
                    clubChart.destroy();
                }
                
                clubChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: data.snapshots.map(s => new Date(s.date).toLocaleDateString('de-CH', {day: '2-digit', month: '2-digit'})),
                        datasets: [
                            {
                                label: 'Prognostizierte Auszahlung (CHF)',
                                data: data.snapshots.map(s => s.payout),
                                borderColor: '#ff6b00',
                                backgroundColor: 'rgba(255, 107, 0, 0.1)',
                                yAxisID: 'y',
                                tension: 0.4,
                                fill: true,
                                pointRadius: 3,
                                pointHoverRadius: 7
                            },
                            {
                                label: 'Prognostizierte Bons',
                                data: data.snapshots.map(s => s.vouchers),
                                borderColor: '#0066cc',
                                backgroundColor: 'rgba(0, 102, 204, 0.1)',
                                yAxisID: 'y1',
                                tension: 0.4,
                                fill: true,
                                pointRadius: 3,
                                pointHoverRadius: 7
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {
                            mode: 'index',
                            intersect: false,
                        },
                        plugins: {
                            legend: {
                                display: true,
                                position: 'top'
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        if (context.datasetIndex === 0) {
                                            return context.dataset.label + ': CHF ' + context.parsed.y.toFixed(2);
                                        } else {
                                            return context.dataset.label + ': ' + context.parsed.y.toLocaleString('de-CH');
                                        }
                                    }
                                }
                            }
                        },
                        scales: {
                            y: {
                                type: 'linear',
                                display: true,
                                position: 'left',
                                title: {
                                    display: true,
                                    text: 'Auszahlung (CHF)'
                                },
                                ticks: {
                                    callback: function(value) {
                                        return 'CHF ' + value.toFixed(0);
                                    }
                                }
                            },
                            y1: {
                                type: 'linear',
                                display: true,
                                position: 'right',
                                title: {
                                    display: true,
                                    text: 'Anzahl Bons'
                                },
                                grid: {
                                    drawOnChartArea: false,
                                }
                            }
                        }
                    }
                });
                
                // Scroll to chart
                document.getElementById('clubChartSection').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            } catch (error) {
                console.error('Error loading club predictions:', error);
            }
        }
        
        // Render clubs
        function renderClubs(clubs) {
            const container = document.getElementById('clubsContainer');
            
            if (clubs.length === 0) {
                container.innerHTML = '<div class="no-results">Keine Vereine gefunden</div>';
                return;
            }
            
            container.innerHTML = clubs.map(club => `
                <div class="club-card" data-club-id="${club.publicId}" data-club-name="${escapeHtml(club.name)}" style="cursor: pointer; transition: transform 0.2s;">
                    <div class="club-name">${escapeHtml(club.name)}</div>
                    <div class="club-stats">
                        <div class="stat-item">
                            <span class="stat-label">Bons</span>
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
            
            // Add click handlers for predictions
            container.querySelectorAll('.club-card').forEach(card => {
                card.addEventListener('click', function() {
                    const clubId = this.dataset.clubId;
                    const clubName = this.dataset.clubName;
                    loadClubPredictions(clubId, clubName);
                });
                
                // Add hover effect
                card.addEventListener('mouseenter', function() {
                    this.style.transform = 'translateY(-2px)';
                    this.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15)';
                });
                card.addEventListener('mouseleave', function() {
                    this.style.transform = 'translateY(0)';
                    this.style.boxShadow = '0 2px 4px rgba(0, 0, 0, 0.1)';
                });
            });
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
                    `1 Vereinsbon = ${formatCurrency(metadata.voucherWorth || 0)}`;
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
            
            // Load data and predictions
            loadData();
            loadWorthTimeline();
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


@app.route('/api/predictions/worth-timeline')
def get_worth_timeline():
    """Get voucher worth timeline predictions"""
    try:
        if not WORTH_TIMELINE_FILE.exists():
            return jsonify({"error": "Predictions not yet available"}), 404
        
        timeline = []
        with open(WORTH_TIMELINE_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                timeline.append({
                    "timestamp": row["ds"],
                    "worth": float(row["predicted_worth"]),
                    "vouchers": int(float(row["predicted_vouchers"]))
                })
        
        return jsonify(timeline)
    except Exception as e:
        logger.error(f"Error loading worth timeline: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/predictions/club/<club_id>')
def get_club_predictions(club_id):
    """Get predictions for a specific club"""
    try:
        if not PREDICTIONS_FILE.exists():
            return jsonify({"error": "Predictions not yet available"}), 404
        
        with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["publicId"] == club_id:
                    # Extract snapshot predictions
                    snapshots = []
                    for key, value in row.items():
                        if key.startswith("payout_by_"):
                            date = key.replace("payout_by_", "")
                            vouchers_key = f"vouchers_by_{date}"
                            snapshots.append({
                                "date": date,
                                "payout": float(value),
                                "vouchers": int(row[vouchers_key])
                            })
                    
                    return jsonify({
                        "publicId": row["publicId"],
                        "name": row["name"],
                        "current_vouchers": int(row["current_vouchers"]),
                        "current_payout": float(row["current_payout"]),
                        "snapshots": snapshots
                    })
        
        return jsonify({"error": "Club not found"}), 404
    except Exception as e:
        logger.error(f"Error loading club predictions: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)
