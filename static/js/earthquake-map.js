// Earthquake Map JavaScript
// This file handles the interactive map functionality for the PHIVOLCS Earthquake Monitor

// Global variables
let map;
let earthquakeMarkers = [];
let earthquakeData = [];
let drawControl;
let drawnItems;
let selectedBounds = null;

// Initialize the map when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing earthquake map...');
    initializeMap();
    loadDateRange(); // Load available date range first
    initializeSearchForm();
    loadEarthquakeData();
});

// Initialize Leaflet map centered on Philippines
function initializeMap() {
    // Create map centered on Philippines
    map = L.map('map').setView([12.8797, 121.7740], 6);
    
    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
    
    // Initialize drawing functionality
    drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);
    
    // Create draw control (initially hidden)
    drawControl = new L.Control.Draw({
        position: 'topright',
        draw: {
            polygon: false,
            circle: false,
            marker: false,
            polyline: false,
            circlemarker: false,
            rectangle: {
                shapeOptions: {
                    color: '#3498db',
                    weight: 2,
                    opacity: 0.8,
                    fillOpacity: 0.1
                }
            }
        },
        edit: {
            featureGroup: drawnItems,
            remove: true
        }
    });
    
    // Handle rectangle drawing
    map.on('draw:created', function(e) {
        drawnItems.clearLayers();
        drawnItems.addLayer(e.layer);
        selectedBounds = e.layer.getBounds();
        updateAreaStatus();
        
        // Hide draw control after drawing
        map.removeControl(drawControl);
        document.getElementById('select-area-btn').style.display = 'block';
        document.getElementById('clear-area-btn').style.display = 'block';
    });
    
    map.on('draw:deleted', function(e) {
        selectedBounds = null;
        updateAreaStatus();
        document.getElementById('clear-area-btn').style.display = 'none';
    });
    
    console.log('Map initialized successfully');
}

// Load available date range and set dynamic limits
async function loadDateRange() {
    try {
        console.log('Loading available date range...');
        const response = await fetch('/api/date-range');
        
        if (!response.ok) {
            throw new Error(`Failed to load date range: ${response.status}`);
        }
        
        const dateInfo = await response.json();
        console.log('Date range loaded:', dateInfo);
        
        // Set dynamic min/max on date inputs
        const dateFromInput = document.getElementById('date-from');
        const dateToInput = document.getElementById('date-to');
        
        dateFromInput.min = dateInfo.min_date;
        dateFromInput.max = dateInfo.max_date;
        dateToInput.min = dateInfo.min_date;
        dateToInput.max = dateInfo.max_date;
        
        // Update info text
        const dateRangeInfo = document.getElementById('date-range-info');
        const minDate = new Date(dateInfo.min_date).toLocaleDateString('en-US', {year: 'numeric', month: 'long'});
        const maxDate = new Date(dateInfo.max_date).toLocaleDateString('en-US', {year: 'numeric', month: 'long'});
        dateRangeInfo.textContent = `📊 Available data: ${minDate} - ${maxDate}`;
        
        // Store available dates globally for validation
        window.availableDates = new Set(dateInfo.available_dates);
        
        console.log(`✅ Date range set: ${dateInfo.min_date} to ${dateInfo.max_date}`);
        
    } catch (error) {
        console.error('❌ Failed to load date range:', error);
        
        // Fallback to static dates
        const dateFromInput = document.getElementById('date-from');
        const dateToInput = document.getElementById('date-to');
        dateFromInput.min = '2018-01-01';
        dateFromInput.max = '2025-12-31';
        dateToInput.min = '2018-01-01';
        dateToInput.max = '2025-12-31';
        
        document.getElementById('date-range-info').textContent = '📊 Available data: January 2018 - December 2025 (estimated)';
    }
}

// Load earthquake data from your Flask API
async function loadEarthquakeData() {
    try {
        console.log('Fetching earthquake data from API...');
        
        // Call your Flask API endpoint
        const response = await fetch('/api/earthquakes');
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Earthquake data received:', data);
        
        // Handle both old format (earthquakes directly) and new format (with metadata)
        const earthquakes = data.earthquakes || data;
        const total = data.total_count || data.total || (Array.isArray(data) ? data.length : earthquakes.length);
        
        // Store the earthquake data globally
        earthquakeData = earthquakes;
        
        // Update the count display
        updateEarthquakeCount(total);
        
        // Show override notification if applicable
        if (data.override_applied) {
            showOverrideNotification(data.override_reason, data.current_date_range);
        } else {
            hideOverrideNotification();
        }
        
        // Plot earthquakes on map
        plotEarthquakes(earthquakes);
        
    } catch (error) {
        console.error('Error loading earthquake data:', error);
        document.getElementById('earthquake-count').innerHTML = 
            '<div style="color: red;">Error loading earthquake data</div>';
    }
}

// Update the earthquake count display
function updateEarthquakeCount(count) {
    const countElement = document.getElementById('earthquake-count');
    countElement.innerHTML = `
        <strong>${count}</strong> Earthquakes record<br>
        <small>Current month data</small>
    `;
}

// Plot earthquakes as markers on the map
function plotEarthquakes(earthquakes) {
    console.log(`Plotting ${earthquakes.length} earthquakes on map...`);
    
    // Clear existing markers
    earthquakeMarkers.forEach(marker => map.removeLayer(marker));
    earthquakeMarkers = [];
    
    // Add new markers for each earthquake
    earthquakes.forEach(earthquake => {
        // Skip if no coordinates
        if (!earthquake.latitude_str || !earthquake.longitude_str) {
            console.warn('Skipping earthquake without coordinates:', earthquake);
            return;
        }
        
        // Parse coordinates (they're stored as strings)
        const lat = parseFloat(earthquake.latitude_str);
        const lng = parseFloat(earthquake.longitude_str);
        
        // Validate coordinates
        if (isNaN(lat) || isNaN(lng)) {
            console.warn('Invalid coordinates for earthquake:', earthquake);
            return;
        }
        
        // Get magnitude and depth for styling
        const magnitude = earthquake.magnitude_str || 'Unknown';
        const depthStr = earthquake.depth_str || '0';
        
        // Extract numeric values
        const magValue = extractMagnitude(magnitude);
        const depthValue = extractDepth(depthStr);
        
        // Determine marker size based on magnitude (HazardHunter style)
        const markerRadius = getMagnitudeRadius(magValue);
        
        // Determine marker color based on depth (HazardHunter style)
        const markerColor = getDepthColor(depthValue);
        
        // Create marker with magnitude-based size and depth-based color
        const marker = L.circleMarker([lat, lng], {
            radius: markerRadius,
            fillColor: markerColor,
            color: '#fff',
            weight: 1,
            opacity: 0.9,
            fillOpacity: 0.7
        });
        
        // Create popup content
        const popupContent = createPopupContent(earthquake);
        marker.bindPopup(popupContent);
        
        // Popup shows all needed info, no need for info panel display
        
        // Add marker to map and store reference
        marker.addTo(map);
        earthquakeMarkers.push(marker);
    });
    
    console.log(`Successfully plotted ${earthquakeMarkers.length} earthquake markers`);
}

// HazardHunter-style earthquake visualization functions

// Extract numeric magnitude from magnitude string
function extractMagnitude(magnitudeStr) {
    const magMatch = magnitudeStr.match(/(\d+\.?\d*)/);
    return magMatch ? parseFloat(magMatch[1]) : 1.0;
}

// Extract numeric depth from depth string
function extractDepth(depthStr) {
    const depthMatch = depthStr.match(/(\d+\.?\d*)/);
    return depthMatch ? parseFloat(depthMatch[1]) : 10;
}

// Determine marker radius based on magnitude (HazardHunter style)
function getMagnitudeRadius(magnitude) {
    if (magnitude >= 8.0) return 14;      // 8.0 - 8.9
    if (magnitude >= 7.0) return 12;      // 7.0 - 7.9
    if (magnitude >= 6.0) return 10;      // 6.0 - 6.9
    if (magnitude >= 5.0) return 8;       // 5.0 - 5.9
    if (magnitude >= 4.0) return 6;       // 4.0 - 4.9
    if (magnitude >= 3.0) return 5;       // 3.0 - 3.9
    if (magnitude >= 2.0) return 4;       // 2.0 - 2.9
    return 3;                              // 1.0 - 1.9
}

// Determine marker color based on depth (HazardHunter style)
function getDepthColor(depth) {
    if (depth > 300) return '#3498db';     // > 300 km (Blue)
    if (depth > 150) return '#27ae60';     // 151 - 300 km (Green)
    if (depth > 70) return '#f1c40f';      // 71 - 150 km (Yellow)
    if (depth > 33) return '#e67e22';      // 34 - 70 km (Orange)
    return '#e74c3c';                      // 0 - 33 km (Red)
}

// Create popup content for earthquake markers
function createPopupContent(earthquake) {
    const date = new Date(earthquake.datetime).toLocaleString();
    
    return `
        <div style="min-width: 180px; padding: 5px;">
            <h3 style="margin: 0 0 5px 0; color: #2c3e50; font-size: 16px;">
                Earthquake #${earthquake.eq_no || 'Unknown'}
            </h3>
            <p style="margin: 3px 0; font-size: 13px;"><strong>Date:</strong> ${date}</p>
            <p style="margin: 3px 0; font-size: 13px;"><strong>Location:</strong> ${earthquake.region || 'Unknown'}</p>
            <p style="margin: 3px 0; font-size: 13px;"><strong>Magnitude:</strong> ${earthquake.magnitude_str || 'Unknown'}</p>
            <p style="margin: 3px 0; font-size: 13px;"><strong>Depth:</strong> ${earthquake.depth_str || 'Unknown'}</p>
        </div>
    `;
}

// Right panel now dedicated to filters only - earthquake details show in popups

// Utility function to handle API errors
function handleApiError(error) {
    console.error('API Error:', error);
    
    const countElement = document.getElementById('earthquake-count');
    countElement.innerHTML = `
        <div style="color: red;">
            <strong>Error</strong><br>
            <small>Failed to load earthquake data</small>
        </div>
    `;
    
    const infoElement = document.getElementById('earthquake-info');
    infoElement.innerHTML = `
        <div style="color: red; text-align: center;">
            <h3>⚠️ Connection Error</h3>
            <p>Could not load earthquake data. Please check your connection and try refreshing the page.</p>
        </div>
    `;
}

// Initialize search form functionality
function initializeSearchForm() {
    // Set default date range to current month
    const now = new Date();
    const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
    const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    
    document.getElementById('date-from').value = firstDay.toISOString().split('T')[0];
    document.getElementById('date-to').value = lastDay.toISOString().split('T')[0];
    
    // Initialize magnitude sliders
    const magMin = document.getElementById('magnitude-min');
    const magMax = document.getElementById('magnitude-max');
    const magMinValue = document.getElementById('mag-min-value');
    const magMaxValue = document.getElementById('mag-max-value');
    
    magMin.addEventListener('input', function() {
        const minVal = parseFloat(this.value);
        const maxVal = parseFloat(magMax.value);
        
        // Ensure min doesn't exceed max
        if (minVal >= maxVal) {
            this.value = (maxVal - 0.1).toFixed(1);
            magMinValue.textContent = this.value;
        } else {
            magMinValue.textContent = this.value;
        }
    });
    
    magMax.addEventListener('input', function() {
        const minVal = parseFloat(magMin.value);
        const maxVal = parseFloat(this.value);
        
        // Ensure max doesn't go below min
        if (maxVal <= minVal) {
            this.value = (minVal + 0.1).toFixed(1);
            magMaxValue.textContent = this.value;
        } else {
            magMaxValue.textContent = this.value;
        }
    });
    
    // Area selection buttons
    document.getElementById('select-area-btn').addEventListener('click', function() {
        map.addControl(drawControl);
        this.style.display = 'none';
        updateAreaStatus('Click and drag on map to select area');
    });
    
    document.getElementById('clear-area-btn').addEventListener('click', function() {
        drawnItems.clearLayers();
        selectedBounds = null;
        updateAreaStatus();
        this.style.display = 'none';
    });
    
    // Filter buttons
    document.getElementById('apply-filters-btn').addEventListener('click', applyFilters);
    document.getElementById('reset-filters-btn').addEventListener('click', resetFilters);
}

// Update area selection status
function updateAreaStatus(message = null) {
    const statusElement = document.getElementById('area-status');
    
    if (message) {
        statusElement.textContent = message;
    } else if (selectedBounds) {
        const north = selectedBounds.getNorth().toFixed(3);
        const south = selectedBounds.getSouth().toFixed(3);
        const east = selectedBounds.getEast().toFixed(3);
        const west = selectedBounds.getWest().toFixed(3);
        statusElement.textContent = `Area selected: ${north}°N, ${south}°S, ${east}°E, ${west}°W`;
    } else {
        statusElement.textContent = 'Click button to draw area on map';
    }
}

// Apply search filters
async function applyFilters() {
    try {
        // Get form values
        const dateFrom = document.getElementById('date-from').value;
        const dateTo = document.getElementById('date-to').value;
        const location = document.getElementById('location-filter').value;
        const origin = document.getElementById('origin-filter').value;
        const magMin = document.getElementById('magnitude-min').value;
        const magMax = document.getElementById('magnitude-max').value;
        
        // Validate required fields
        if (!dateFrom || !dateTo) {
            alert('Date range is required!');
            return;
        }
        
        // Validate date range is within available data
        const dateFromInput = document.getElementById('date-from');
        const dateToInput = document.getElementById('date-to');
        const minDate = new Date(dateFromInput.min);
        const maxDate = new Date(dateToInput.max);
        const fromDate = new Date(dateFrom);
        const toDate = new Date(dateTo);
        
        if (fromDate < minDate || toDate > maxDate || fromDate > maxDate || toDate < minDate) {
            const minDateStr = minDate.toLocaleDateString('en-US', {year: 'numeric', month: 'long'});
            const maxDateStr = maxDate.toLocaleDateString('en-US', {year: 'numeric', month: 'long'});
            alert(`Please select dates between ${minDateStr} and ${maxDateStr}.\n\nOur database contains earthquake data within this range only.`);
            return;
        }
        
        if (fromDate > toDate) {
            alert('Start date must be before or equal to end date.');
            return;
        }
        
        // Build query parameters
        let queryParams = new URLSearchParams({
            date_from: dateFrom,
            date_to: dateTo,
            magnitude_min: magMin,
            magnitude_max: magMax
        });
        
        if (location) queryParams.append('location', location);
        if (origin) queryParams.append('origin', origin);
        
        // Add geographic bounds if selected
        if (selectedBounds) {
            queryParams.append('lat_min', selectedBounds.getSouth());
            queryParams.append('lat_max', selectedBounds.getNorth());
            queryParams.append('lon_min', selectedBounds.getWest());
            queryParams.append('lon_max', selectedBounds.getEast());
        }
        
        // Update loading state
        document.getElementById('earthquake-count').innerHTML = 
            '<div class="loading">Searching earthquakes...</div>';
        
        // Call API with filters
        const response = await fetch(`/api/earthquakes?${queryParams}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Filtered earthquake data received:', data);
        
        // Handle both old format (earthquakes directly) and new format (with metadata)
        const earthquakes = data.earthquakes || data;
        const total = data.total_count || data.total || (Array.isArray(data) ? data.length : earthquakes.length);
        
        // Update display
        earthquakeData = earthquakes;
        updateEarthquakeCount(total);
        
        // Show override notification if applicable
        if (data.override_applied) {
            showOverrideNotification(data.override_reason, data.current_date_range);
        } else {
            hideOverrideNotification();
        }
        
        plotEarthquakes(earthquakes);
        
    } catch (error) {
        console.error('Error applying filters:', error);
        handleApiError(error);
    }
}

// Reset filters to current month
function resetFilters() {
    // Reset form to defaults
    const now = new Date();
    const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
    const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    
    document.getElementById('date-from').value = firstDay.toISOString().split('T')[0];
    document.getElementById('date-to').value = lastDay.toISOString().split('T')[0];
    document.getElementById('location-filter').value = '';
    document.getElementById('origin-filter').value = '';
    document.getElementById('magnitude-min').value = '1';
    document.getElementById('magnitude-max').value = '10';
    document.getElementById('mag-min-value').textContent = '1.0';
    document.getElementById('mag-max-value').textContent = '10.0';
    
    // Clear area selection
    if (drawnItems) {
        drawnItems.clearLayers();
    }
    selectedBounds = null;
    updateAreaStatus();
    document.getElementById('clear-area-btn').style.display = 'none';
    
    // Reload current month data
    loadEarthquakeData();
}

// Debug function to log earthquake data (can be called from browser console)
function debugEarthquakeData() {
    console.log('Current earthquake data:', earthquakeData);
    console.log('Active markers:', earthquakeMarkers.length);
    console.log('Selected bounds:', selectedBounds);
    return {
        earthquakes: earthquakeData.length,
        markers: earthquakeMarkers.length,
        mapCenter: map.getCenter(),
        mapZoom: map.getZoom(),
        selectedArea: selectedBounds
    };
}

// Override notification functions
function showOverrideNotification(reason, dateRange) {
    // Remove any existing notification
    hideOverrideNotification();
    
    // Create notification element
    const notification = document.createElement('div');
    notification.id = 'override-notification';
    notification.className = 'alert alert-warning override-notification';
    notification.innerHTML = `
        <div class="override-content">
            <strong>⚠️ Query Override Applied</strong>
            <p>${reason}</p>
            <p><strong>Data limited to:</strong> ${dateRange}</p>
            <button type="button" class="btn btn-sm btn-outline-warning" onclick="hideOverrideNotification()">Dismiss</button>
        </div>
    `;
    
    // Add to page (after the search form)
    const searchForm = document.querySelector('.search-form');
    if (searchForm) {
        searchForm.parentNode.insertBefore(notification, searchForm.nextSibling);
    } else {
        // Fallback: add to top of page
        document.body.insertBefore(notification, document.body.firstChild);
    }
    
    console.log('Override notification shown:', reason);
}

function hideOverrideNotification() {
    const notification = document.getElementById('override-notification');
    if (notification) {
        notification.remove();
    }
}