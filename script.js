// Israel Water Infrastructure Map - Main Logic

document.addEventListener('DOMContentLoaded', () => {
    initMap();
});

let map;
let linesLayer;
let pointsLayer;
let strategicLayer;

// Styling constants
const COLORS = {
    stream: '#00d2ff',
    canal: '#3fe0d0',
    ditch: '#3fe0d0',
    drain: '#a8dadc',
    river: '#0088ff',
    waterfall: '#ffffff',
    dam: '#ff5e62',
    weir: '#ff9966',
    strategic: '#fce303',
    default: '#8892b0'
};

async function initMap() {
    // Initialize map centered on Israel
    map = L.map('map', {
        zoomControl: false,
        attributionControl: false
    }).setView([31.5, 34.9], 8);

    // Add CartoDB Dark Matter base layer
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 19
    }).addTo(map);

    // Add zoom control at bottom left
    L.control.zoom({
        position: 'bottomleft'
    }).addTo(map);

    // Load Data
    await loadStrategicInfrastructure();
    await loadWaterways();
    await loadInfrastructurePoints();

    // Set up Toggles
    setupToggles();
}

async function loadWaterways() {
    try {
        const response = await fetch('./data/hotosm_isr_waterways_lines_geojson/hotosm_isr_waterways_lines_geojson.geojson');
        const data = await response.json();

        linesLayer = L.geoJSON(data, {
            style: (feature) => {
                const type = feature.properties.waterway;
                return {
                    color: COLORS[type] || COLORS.default,
                    weight: type === 'river' ? 3 : 1.5,
                    opacity: 0.8,
                    lineCap: 'round'
                };
            },
            onEachFeature: (feature, layer) => {
                const props = feature.properties;
                const name = props.name || props['name:en'] || 'Unnamed Waterway';
                const type = props.waterway || 'Unknown';

                layer.bindPopup(`
                    <div class="popup-content">
                        <h4>${name}</h4>
                        <p><strong>Type:</strong> ${type}</p>
                        ${props.tunnel ? `<p><strong>Tunnel:</strong> ${props.tunnel}</p>` : ''}
                        <p><strong>Source:</strong> ${props.source || 'OpenStreetMap'}</p>
                    </div>
                `);

                layer.on('mouseover', function () {
                    this.setStyle({ weight: 4, opacity: 1 });
                });
                layer.on('mouseout', function () {
                    linesLayer.resetStyle(this);
                });
            }
        }).addTo(map);
    } catch (error) {
        console.error('Error loading waterways:', error);
    }
}

async function loadInfrastructurePoints() {
    try {
        const response = await fetch('./data/hotosm_isr_waterways_points_geojson/hotosm_isr_waterways_points_geojson.geojson');
        const data = await response.json();

        pointsLayer = L.geoJSON(data, {
            pointToLayer: (feature, latlng) => {
                const type = feature.properties.waterway;
                let markerStyle = {
                    radius: 5,
                    fillColor: COLORS[type] || COLORS.default,
                    color: "#fff",
                    weight: 1,
                    opacity: 1,
                    fillOpacity: 0.6
                };

                if (type === 'waterfall') {
                    markerStyle.fillColor = COLORS.waterfall;
                    markerStyle.weight = 2;
                }

                return L.circleMarker(latlng, markerStyle);
            },
            onEachFeature: (feature, layer) => {
                const props = feature.properties;
                const name = props.name || props['name:en'] || 'Unnamed Facility';
                const type = props.waterway || props.natural || 'Infrastructure';

                layer.bindPopup(`
                    <div class="popup-content">
                        <h4>${name}</h4>
                        <p><strong>Type:</strong> ${type}</p>
                        ${props.water ? `<p><strong>Details:</strong> ${props.water}</p>` : ''}
                        <p><strong>Source:</strong> ${props.source || 'OpenStreetMap'}</p>
                    </div>
                `);

                layer.on('mouseover', function () {
                    this.setRadius(7);
                });
                layer.on('mouseout', function () {
                    this.setRadius(5);
                });
            }
        }).addTo(map);
    } catch (error) {
        console.error('Error loading points:', error);
    }
}

async function loadStrategicInfrastructure() {
    try {
        const response = await fetch('./data/strategic_infrastructure.geojson');
        const data = await response.json();

        strategicLayer = L.geoJSON(data, {
            pointToLayer: (feature, latlng) => {
                return L.circleMarker(latlng, {
                    radius: 8,
                    fillColor: COLORS.strategic,
                    color: "#000",
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.9
                });
            },
            onEachFeature: (feature, layer) => {
                const props = feature.properties;

                layer.bindPopup(`
                    <div class="popup-content strategic-popup">
                        <h4 style="color: #fce303">${props.name}</h4>
                        <p><strong>Category:</strong> ${props.category}</p>
                        <p><strong>Location:</strong> ${props.city}</p>
                        <p><strong>Coordinates/Address:</strong> ${props.address}</p>
                        <p style="margin-top: 8px; padding: 8px; background: rgba(252, 227, 3, 0.1); border-left: 3px solid #fce303;">
                            <strong>Security Profile:</strong><br>${props.security_profile}
                        </p>
                    </div>
                `, { minWidth: 250 });

                layer.on('mouseover', function () {
                    this.setRadius(10);
                    this.setStyle({ weight: 3, color: '#fff' });
                });
                layer.on('mouseout', function () {
                    this.setRadius(8);
                    this.setStyle({ weight: 2, color: '#000' });
                });
            }
        }).addTo(map);
    } catch (error) {
        console.error('Error loading strategic infrastructure:', error);
    }
}

function setupToggles() {
    const strategicToggle = document.getElementById('toggle-strategic');
    const lineToggle = document.getElementById('toggle-lines');
    const pointToggle = document.getElementById('toggle-points');

    strategicToggle.addEventListener('change', (e) => {
        if (e.target.checked) {
            map.addLayer(strategicLayer);
        } else {
            map.removeLayer(strategicLayer);
        }
    });

    lineToggle.addEventListener('change', (e) => {
        if (e.target.checked) {
            map.addLayer(linesLayer);
        } else {
            map.removeLayer(linesLayer);
        }
    });

    pointToggle.addEventListener('change', (e) => {
        if (e.target.checked) {
            map.addLayer(pointsLayer);
        } else {
            map.removeLayer(pointsLayer);
        }
    });
}
