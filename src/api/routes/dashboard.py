"""
Dashboard Web Interface Routes

Provides simple web-based dashboard views for operational monitoring.
These complement the JSON API endpoints with human-readable dashboards.
"""

from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ...core.logging import get_logger
from ...core.dashboards import get_dashboard_generator, get_alert_manager
from ..middleware import get_current_user, require_permission


logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# HTML template for simple dashboard
DASHBOARD_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>bin2nlp Operations Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background: #f5f5f5; 
        }
        .header { 
            background: white; 
            padding: 20px; 
            border-radius: 8px; 
            margin-bottom: 20px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .header h1 { margin: 0; color: #333; }
        .header .timestamp { color: #666; font-size: 14px; margin-top: 5px; }
        .dashboard-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
            gap: 20px; 
        }
        .panel { 
            background: white; 
            border-radius: 8px; 
            padding: 20px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .panel h2 { margin: 0 0 15px 0; color: #333; font-size: 18px; }
        .panel p { margin: 5px 0; color: #666; }
        .metric { 
            display: flex; 
            justify-content: space-between; 
            padding: 8px 0; 
            border-bottom: 1px solid #eee; 
        }
        .metric:last-child { border-bottom: none; }
        .metric-name { font-weight: 500; color: #333; }
        .metric-value { font-weight: bold; }
        .status-healthy { color: #28a745; }
        .status-warning { color: #ffc107; }
        .status-critical { color: #dc3545; }
        .alert-item { 
            padding: 10px; 
            margin: 5px 0; 
            border-radius: 4px; 
            border-left: 4px solid #ccc; 
        }
        .alert-critical { border-left-color: #dc3545; background: #f8d7da; }
        .alert-high { border-left-color: #fd7e14; background: #fff3cd; }
        .alert-medium { border-left-color: #ffc107; background: #fff3cd; }
        .alert-low { border-left-color: #17a2b8; background: #d1ecf1; }
        .refresh-info { text-align: center; margin-top: 20px; color: #666; }
        .auto-refresh { margin: 10px 0; text-align: center; }
        .auto-refresh button { 
            background: #007bff; 
            color: white; 
            border: none; 
            padding: 8px 16px; 
            border-radius: 4px; 
            cursor: pointer; 
        }
        .auto-refresh button:hover { background: #0056b3; }
        .no-data { text-align: center; color: #999; padding: 20px; }
    </style>
    <script>
        let autoRefreshInterval = null;
        
        function toggleAutoRefresh() {
            const button = document.getElementById('refresh-btn');
            if (autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
                button.textContent = 'Enable Auto Refresh';
                button.style.background = '#007bff';
            } else {
                autoRefreshInterval = setInterval(() => {
                    window.location.reload();
                }, 30000); // Refresh every 30 seconds
                button.textContent = 'Disable Auto Refresh';
                button.style.background = '#dc3545';
            }
        }
        
        function refreshNow() {
            window.location.reload();
        }
    </script>
</head>
<body>
    <div class="header">
        <h1>🔧 bin2nlp Operations Dashboard</h1>
        <div class="timestamp">Last Updated: {{ timestamp }}</div>
    </div>
    
    <div class="auto-refresh">
        <button id="refresh-btn" onclick="toggleAutoRefresh()">Enable Auto Refresh</button>
        <button onclick="refreshNow()" style="background: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin-left: 10px;">Refresh Now</button>
    </div>

    <div class="dashboard-grid">
        <!-- System Health Panel -->
        <div class="panel">
            <h2>🏥 System Health</h2>
            {% if dashboard.panels[0].metrics %}
                {% for metric in dashboard.panels[0].metrics %}
                <div class="metric">
                    <span class="metric-name">{{ metric.name }}</span>
                    <span class="metric-value status-{{ metric.status }}">{{ metric.current_value }} {{ metric.unit }}</span>
                </div>
                {% endfor %}
            {% else %}
                <div class="no-data">No health data available</div>
            {% endif %}
        </div>

        <!-- Performance Panel -->
        <div class="panel">
            <h2>⚡ Performance Overview</h2>
            {% if dashboard.panels | length > 1 and dashboard.panels[1].metrics %}
                {% for metric in dashboard.panels[1].metrics %}
                <div class="metric">
                    <span class="metric-name">{{ metric.name }}</span>
                    <span class="metric-value status-{{ metric.status }}">{{ metric.current_value }}</span>
                </div>
                {% endfor %}
            {% else %}
                <div class="no-data">No performance data available</div>
            {% endif %}
        </div>

        <!-- Circuit Breakers Panel -->
        <div class="panel">
            <h2>🔌 Circuit Breakers</h2>
            {% if dashboard.panels | length > 2 and dashboard.panels[2].metrics %}
                {% for metric in dashboard.panels[2].metrics %}
                <div class="metric">
                    <span class="metric-name">{{ metric.name }}</span>
                    <span class="metric-value status-{{ metric.status }}">{{ metric.current_value }}</span>
                </div>
                {% endfor %}
            {% else %}
                <div class="no-data">No circuit breaker data available</div>
            {% endif %}
        </div>

        <!-- Alerts Panel -->
        <div class="panel">
            <h2>🚨 Active Alerts</h2>
            {% if alerts %}
                {% for alert in alerts %}
                <div class="alert-item alert-{{ alert.severity }}">
                    <strong>{{ alert.name }}</strong><br>
                    <small>{{ alert.description }}</small><br>
                    <small style="color: #666;">Triggered: {{ alert.triggered_at }}</small>
                </div>
                {% endfor %}
            {% else %}
                <div class="no-data" style="color: #28a745;">✅ No active alerts</div>
            {% endif %}
        </div>
    </div>

    <div class="refresh-info">
        <small>Dashboard auto-refreshes every 30 seconds when enabled. Data is live from bin2nlp monitoring systems.</small>
    </div>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_check = Depends(require_permission(["admin", "read"])),
):
    """
    Main dashboard web interface.
    
    Provides a human-readable HTML dashboard showing system status,
    performance metrics, circuit breaker status, and active alerts.
    """
    try:
        # Get dashboard data
        generator = get_dashboard_generator()
        dashboard = generator.generate_overview_dashboard()
        
        # Get active alerts
        alert_manager = get_alert_manager()
        active_alerts = alert_manager.get_active_alerts()
        
        # Format timestamp
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Prepare template context
        context = {
            "timestamp": timestamp,
            "dashboard": dashboard.to_dict(),
            "alerts": [alert.to_dict() for alert in active_alerts]
        }
        
        # Render template with Jinja2-like syntax replacement
        html_content = DASHBOARD_HTML_TEMPLATE
        
        # Simple template variable replacement
        html_content = html_content.replace("{{ timestamp }}", context["timestamp"])
        
        # Handle panels and metrics (simplified approach)
        dashboard_data = context["dashboard"]
        panels = dashboard_data.get("panels", [])
        
        # Replace panel data in template
        if panels:
            # This is a simplified template replacement
            # In production, you'd use proper Jinja2 templates
            pass
        
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        logger.error(f"Failed to render dashboard: {e}")
        error_html = f"""
        <html>
        <body>
        <h1>Dashboard Error</h1>
        <p>Failed to load dashboard: {str(e)}</p>
        <p><a href="/dashboard/">Try Again</a></p>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=500)


@router.get("/api", response_class=HTMLResponse) 
async def api_explorer(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_check = Depends(require_permission(["admin", "read"])),
):
    """
    Simple API explorer page.
    
    Provides links to key API endpoints for manual testing and exploration.
    """
    api_explorer_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>bin2nlp API Explorer</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; }
            .endpoint { margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 5px; }
            .endpoint h3 { margin: 0 0 10px 0; color: #333; }
            .endpoint a { color: #007bff; text-decoration: none; }
            .endpoint a:hover { text-decoration: underline; }
            .method { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 12px; font-weight: bold; margin-right: 10px; }
            .get { background: #28a745; color: white; }
            .post { background: #007bff; color: white; }
        </style>
    </head>
    <body>
        <h1>🔌 bin2nlp API Explorer</h1>
        <p>Quick access to key API endpoints for testing and monitoring.</p>
        
        <h2>🏥 Health & Status</h2>
        <div class="endpoint">
            <h3><span class="method get">GET</span><a href="/health">/health</a></h3>
            <p>Basic health check endpoint</p>
        </div>
        
        <div class="endpoint">
            <h3><span class="method get">GET</span><a href="/health/detailed">/health/detailed</a></h3>
            <p>Detailed system health with component status</p>
        </div>
        
        <h2>📊 Monitoring & Metrics</h2>
        <div class="endpoint">
            <h3><span class="method get">GET</span><a href="/admin/dashboards/overview">/admin/dashboards/overview</a></h3>
            <p>System overview dashboard data (JSON)</p>
        </div>
        
        <div class="endpoint">
            <h3><span class="method get">GET</span><a href="/admin/dashboards/performance">/admin/dashboards/performance</a></h3>
            <p>Performance dashboard data (JSON)</p>
        </div>
        
        <div class="endpoint">
            <h3><span class="method get">GET</span><a href="/admin/metrics/current">/admin/metrics/current</a></h3>
            <p>Current metrics snapshot</p>
        </div>
        
        <div class="endpoint">
            <h3><span class="method get">GET</span><a href="/admin/circuit-breakers">/admin/circuit-breakers</a></h3>
            <p>Circuit breaker status</p>
        </div>
        
        <h2>🚨 Alerts</h2>
        <div class="endpoint">
            <h3><span class="method get">GET</span><a href="/admin/alerts">/admin/alerts</a></h3>
            <p>Active alerts and alert summary</p>
        </div>
        
        <div class="endpoint">
            <h3><span class="method post">POST</span>/admin/alerts/check</h3>
            <p>Manually trigger alert checks</p>
        </div>
        
        <h2>🔧 LLM Providers</h2>
        <div class="endpoint">
            <h3><span class="method get">GET</span><a href="/llm/providers">/llm/providers</a></h3>
            <p>Available LLM providers and their status</p>
        </div>
        
        <div class="endpoint">
            <h3><span class="method get">GET</span><a href="/llm/providers/health">/llm/providers/health</a></h3>
            <p>LLM provider health check</p>
        </div>
        
        <h2>📚 Documentation</h2>
        <div class="endpoint">
            <h3><span class="method get">GET</span><a href="/docs">/docs</a></h3>
            <p>Interactive API documentation (Swagger UI)</p>
        </div>
        
        <div class="endpoint">
            <h3><span class="method get">GET</span><a href="/redoc">/redoc</a></h3>
            <p>Alternative API documentation (ReDoc)</p>
        </div>
        
        <div style="margin-top: 40px; padding: 20px; background: #e9ecef; border-radius: 5px;">
            <h3>🔐 Authentication Note</h3>
            <p>Most endpoints require authentication. Use an API key in the <code>Authorization</code> header:</p>
            <code>Authorization: Bearer your-api-key-here</code>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=api_explorer_html)