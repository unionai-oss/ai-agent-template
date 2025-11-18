import httpx
import json
import os
import re
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse, parse_qs
import flyte
from utils.decorators import tool


@tool(agent="oncall")
@flyte.trace
async def query_grafana_data(
    grafana_url: str,
    time_range: Optional[str] = "1h"
) -> Dict[str, Any]:
    """
    Query data from a Grafana dashboard or panel link.
    
    This function can extract data from Grafana dashboards by:
    1. Parsing the dashboard URL to extract dashboard and panel information
    2. Using Grafana's API to fetch the actual metrics data
    3. Returning structured data that can be analyzed
    
    Authentication is handled via the GRAFANA_AUTH_TOKEN environment variable.
    
    Args:
        grafana_url (str): The Grafana dashboard or panel URL
        time_range (str): Time range for the query (default: "1h")
                         Examples: "5m", "1h", "24h", "7d"
    
    Returns:
        Dict[str, Any]: Dictionary containing:
            - dashboard_info: Dashboard metadata
            - panels_data: Data from each panel
            - time_range: The time range queried
            - status: Success/error status
    """
    print(f"TOOL CALL: Querying Grafana data from {grafana_url}")
    
    try:
        # Parse the Grafana URL
        parsed_info = _parse_grafana_url(grafana_url)
        
        if not parsed_info["is_valid"]:
            return {
                "status": "error",
                "error": "Invalid Grafana URL provided",
                "dashboard_info": {},
                "panels_data": [],
                "time_range": time_range
            }
        
        base_url = parsed_info["base_url"]
        dashboard_uid = parsed_info["dashboard_uid"]
        panel_id = parsed_info.get("panel_id")
        
        # Set up authentication headers using environment variable
        grafana_token = os.getenv("GRAFANA_AUTH_TOKEN")
        if not grafana_token:
            return {
                "status": "error",
                "error": "GRAFANA_AUTH_TOKEN environment variable not set",
                "dashboard_info": {},
                "panels_data": [],
                "time_range": time_range
            }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {grafana_token}"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get dashboard information
            dashboard_info = await _get_dashboard_info(
                client, base_url, dashboard_uid, headers
            )
            
            if dashboard_info["status"] == "error":
                return dashboard_info
            
            # Get panels data
            panels_data = await _get_panels_data(
                client, base_url, dashboard_info["dashboard"], 
                headers, time_range, panel_id
            )
            
            return {
                "status": "success",
                "dashboard_info": dashboard_info["dashboard"],
                "panels_data": panels_data,
                "time_range": time_range,
                "total_panels": len(panels_data)
            }
    
    except httpx.TimeoutException:
        return {
            "status": "error", 
            "error": "Timeout connecting to Grafana instance",
            "dashboard_info": {},
            "panels_data": [],
            "time_range": time_range
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Error querying Grafana: {str(e)}",
            "dashboard_info": {},
            "panels_data": [],
            "time_range": time_range
        }


def _parse_grafana_url(url: str) -> Dict[str, Any]:
    """
    Parse a Grafana URL to extract dashboard and panel information.
    
    Args:
        url (str): The Grafana URL
        
    Returns:
        Dict[str, Any]: Parsed information including base_url, dashboard_uid, panel_id
    """
    try:
        parsed = urlparse(url)
        
        # Extract base URL
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        # Parse path to get dashboard UID
        path_parts = parsed.path.split('/')
        dashboard_uid = None
        panel_id = None
        
        # Look for dashboard UID in the path
        if 'd' in path_parts:
            d_index = path_parts.index('d')
            if d_index + 1 < len(path_parts):
                dashboard_uid = path_parts[d_index + 1]
        
        # Check for panel ID in query parameters or fragment
        query_params = parse_qs(parsed.query)
        if 'viewPanel' in query_params:
            panel_id = query_params['viewPanel'][0]
        
        # Also check fragment for panel ID
        if parsed.fragment:
            fragment_params = parse_qs(parsed.fragment)
            if 'viewPanel' in fragment_params:
                panel_id = fragment_params['viewPanel'][0]
            # Handle hash-style panel references
            elif parsed.fragment.isdigit():
                panel_id = parsed.fragment
        
        return {
            "is_valid": dashboard_uid is not None,
            "base_url": base_url,
            "dashboard_uid": dashboard_uid,
            "panel_id": panel_id
        }
    
    except Exception:
        return {"is_valid": False}


async def _get_dashboard_info(
    client: httpx.AsyncClient, 
    base_url: str, 
    dashboard_uid: str, 
    headers: Dict[str, str]
) -> Dict[str, Any]:
    """Get dashboard information from Grafana API."""
    
    try:
        # Get dashboard metadata
        dashboard_url = f"{base_url}/api/dashboards/uid/{dashboard_uid}"
        response = await client.get(dashboard_url, headers=headers)
        response.raise_for_status()
        
        dashboard_data = response.json()
        
        return {
            "status": "success",
            "dashboard": {
                "uid": dashboard_data["dashboard"]["uid"],
                "title": dashboard_data["dashboard"]["title"],
                "description": dashboard_data["dashboard"].get("description", ""),
                "tags": dashboard_data["dashboard"].get("tags", []),
                "panel_count": len(dashboard_data["dashboard"]["panels"]),
                "panels": dashboard_data["dashboard"]["panels"]
            }
        }
    
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            error_msg = "Authentication failed - check API key or credentials"
        elif e.response.status_code == 404:
            error_msg = "Dashboard not found - check the URL"
        else:
            error_msg = f"HTTP {e.response.status_code} error"
        
        return {
            "status": "error",
            "error": error_msg,
            "dashboard": {}
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": f"Error fetching dashboard info: {str(e)}",
            "dashboard": {}
        }


async def _get_panels_data(
    client: httpx.AsyncClient,
    base_url: str,
    dashboard: Dict[str, Any],
    headers: Dict[str, str],
    time_range: str,
    target_panel_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get data from dashboard panels."""
    
    panels_data = []
    panels = dashboard.get("panels", [])
    
    # Convert time range to millisecond timestamps
    time_params = _convert_time_range(time_range)
    
    for panel in panels:
        # Skip if we're targeting a specific panel and this isn't it
        if target_panel_id and str(panel.get("id")) != str(target_panel_id):
            continue
            
        # Skip panels without queries (like text panels)
        if not panel.get("targets"):
            continue
        
        try:
            panel_data = {
                "panel_id": panel.get("id"),
                "title": panel.get("title", "Untitled Panel"),
                "type": panel.get("type", "unknown"),
                "queries": [],
                "error": None
            }
            
            # Process each query in the panel
            for target in panel.get("targets", []):
                if target.get("hide"):  # Skip hidden queries
                    continue
                
                query_data = await _execute_panel_query(
                    client, base_url, target, time_params, headers
                )
                panel_data["queries"].append(query_data)
            
            panels_data.append(panel_data)
            
        except Exception as e:
            panels_data.append({
                "panel_id": panel.get("id"),
                "title": panel.get("title", "Untitled Panel"),
                "type": panel.get("type", "unknown"),
                "queries": [],
                "error": f"Error processing panel: {str(e)}"
            })
    
    return panels_data


async def _execute_panel_query(
    client: httpx.AsyncClient,
    base_url: str,
    target: Dict[str, Any],
    time_params: Dict[str, int],
    headers: Dict[str, str]
) -> Dict[str, Any]:
    """Execute a single panel query."""
    
    try:
        # Prepare query payload for Grafana's query API
        query_payload = {
            "queries": [{
                "refId": target.get("refId", "A"),
                "expr": target.get("expr", ""),  # For Prometheus queries
                "datasource": target.get("datasource", {}),
                "intervalMs": 15000,
                "maxDataPoints": 800
            }],
            "range": {
                "from": str(time_params["from"]),
                "to": str(time_params["to"])
            },
            "from": str(time_params["from"]),
            "to": str(time_params["to"])
        }
        
        # Execute query
        query_url = f"{base_url}/api/ds/query"
        response = await client.post(
            query_url, 
            json=query_payload, 
            headers=headers
        )
        response.raise_for_status()
        
        result = response.json()
        
        return {
            "refId": target.get("refId", "A"),
            "expr": target.get("expr", ""),
            "data": result,
            "error": None
        }
    
    except Exception as e:
        return {
            "refId": target.get("refId", "A"),
            "expr": target.get("expr", ""),
            "data": None,
            "error": f"Query execution failed: {str(e)}"
        }


def _convert_time_range(time_range: str) -> Dict[str, int]:
    """Convert time range string to millisecond timestamps."""
    
    import time
    
    current_time_ms = int(time.time() * 1000)
    
    # Parse time range
    if time_range.endswith('m'):
        minutes = int(time_range[:-1])
        from_time_ms = current_time_ms - (minutes * 60 * 1000)
    elif time_range.endswith('h'):
        hours = int(time_range[:-1])
        from_time_ms = current_time_ms - (hours * 60 * 60 * 1000)
    elif time_range.endswith('d'):
        days = int(time_range[:-1])
        from_time_ms = current_time_ms - (days * 24 * 60 * 60 * 1000)
    else:
        # Default to 1 hour
        from_time_ms = current_time_ms - (60 * 60 * 1000)
    
    return {
        "from": from_time_ms,
        "to": current_time_ms
    }


@tool(agent="oncall")
@flyte.trace
async def summarize_grafana_metrics(panels_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Summarize and analyze metrics data from Grafana panels.
    
    Args:
        panels_data (List[Dict[str, Any]]): Panel data from query_grafana_data
        
    Returns:
        Dict[str, Any]: Summary including key metrics, alerts, and insights
    """
    print("TOOL CALL: Summarizing Grafana metrics data")
    
    summary = {
        "total_panels": len(panels_data),
        "panels_with_data": 0,
        "panels_with_errors": 0,
        "key_metrics": [],
        "potential_issues": [],
        "summary": ""
    }
    
    for panel in panels_data:
        if panel.get("error"):
            summary["panels_with_errors"] += 1
            summary["potential_issues"].append({
                "panel": panel["title"],
                "issue": panel["error"]
            })
            continue
        
        has_data = False
        for query in panel.get("queries", []):
            if query.get("data") and not query.get("error"):
                has_data = True
                # Extract key metrics from the data
                # This is a simplified extraction - in practice, you'd parse
                # the specific data format returned by your data source
                summary["key_metrics"].append({
                    "panel": panel["title"],
                    "query": query.get("expr", ""),
                    "has_data": True
                })
        
        if has_data:
            summary["panels_with_data"] += 1
    
    # Generate summary text
    summary["summary"] = (
        f"Analyzed {summary['total_panels']} panels. "
        f"{summary['panels_with_data']} panels returned data, "
        f"{summary['panels_with_errors']} panels had errors."
    )
    
    if summary["potential_issues"]:
        summary["summary"] += f" Found {len(summary['potential_issues'])} potential issues."
    
    return summary
