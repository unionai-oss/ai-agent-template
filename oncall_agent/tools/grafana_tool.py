import os
from urllib.parse import urlparse, parse_qs
import httpx


def parse_grafana_url(url: str) -> dict:
    """
    Parse a Grafana dashboard URL to extract relevant information.

    Args:
        url: Full Grafana URL (e.g., https://unionai.grafana.net/d/e65d0d7c-cb63-4d2c-826f-6bc8305a303d?from=1763655790000&orgId=1&to=1763659420252&viewPanel=115)

    Returns:
        dict with keys: base_url, dashboard_uid, panel_id (optional), from_timestamp (optional), to_timestamp (optional), org_id (optional)
    """
    parsed = urlparse(url)

    # Extract base URL (scheme + netloc)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # Extract dashboard UID from path (format: /d/{uid}/...)
    path_parts = parsed.path.strip('/').split('/')
    dashboard_uid = None
    if len(path_parts) >= 2 and path_parts[0] == 'd':
        dashboard_uid = path_parts[1]

    if not dashboard_uid:
        raise ValueError(f"Could not extract dashboard UID from URL: {url}")

    # Parse query parameters
    query_params = parse_qs(parsed.query)

    result = {
        "base_url": base_url,
        "dashboard_uid": dashboard_uid,
        "panel_id": int(query_params.get('viewPanel', [None])[0]) if query_params.get('viewPanel') else None,
        "from_timestamp": int(query_params.get('from', [None])[0]) if query_params.get('from') else None,
        "to_timestamp": int(query_params.get('to', [None])[0]) if query_params.get('to') else None,
        "org_id": int(query_params.get('orgId', [1])[0]) if query_params.get('orgId') else 1,
    }

    return result


def query_panel_data(client, base_url, headers, dashboard_uid, panel, from_timestamp, to_timestamp, org_id):
    """
    Query actual data for a specific panel using Grafana's query API.

    Args:
        client: httpx.Client instance
        base_url: Grafana base URL
        headers: Request headers with authentication
        dashboard_uid: Dashboard UID
        panel: Panel configuration object
        from_timestamp: Start time in milliseconds
        to_timestamp: End time in milliseconds
        org_id: Organization ID

    Returns:
        dict: Panel configuration with queried data
    """
    panel_id = panel.get("id")
    panel_info = {
        "panel_id": panel_id,
        "title": panel.get("title"),
        "type": panel.get("type"),
        "datasource": panel.get("datasource"),
        "description": panel.get("description"),
        "targets": panel.get("targets", []),
        "time_range": {
            "from": from_timestamp,
            "to": to_timestamp
        }
    }

    # Try to query the panel data using Grafana's panel query API
    if from_timestamp and to_timestamp and panel.get("targets"):
        try:
            # Use Grafana's ds/query API to query panel data
            query_url = f"{base_url}/api/ds/query"

            # Build queries from panel targets
            queries = []
            for target in panel.get("targets", []):
                query = {
                    "refId": target.get("refId", "A"),
                    "datasource": panel.get("datasource"),
                    "expr": target.get("expr"),  # For Prometheus
                    "query": target.get("query"),  # For other datasources
                    "queryType": target.get("queryType"),
                    "intervalMs": target.get("intervalMs", 1000),
                    "maxDataPoints": target.get("maxDataPoints", 1000),
                }
                # Add any other target properties
                query.update({k: v for k, v in target.items() if k not in query})
                queries.append(query)

            query_payload = {
                "queries": queries,
                "from": str(from_timestamp),
                "to": str(to_timestamp),
            }

            print(f"  Querying data for panel {panel_id}: {panel.get('title')}")
            query_response = client.post(
                query_url,
                headers=headers,
                json=query_payload,
                params={"orgId": org_id}
            )

            if query_response.status_code == 200:
                panel_info["data"] = query_response.json()
                panel_info["data_status"] = "success"
            else:
                panel_info["data_status"] = "failed"
                panel_info["data_error"] = f"HTTP {query_response.status_code}: {query_response.text}"

        except Exception as e:
            panel_info["data_status"] = "error"
            panel_info["data_error"] = str(e)
    else:
        panel_info["data_status"] = "no_time_range"

    return panel_info


def get_grafana_panel_data(url: str, include_all_panels: bool = True) -> dict:
    """
    Queries Grafana for dashboard panel data from a Grafana URL.

    If the URL contains a viewPanel parameter, that panel will be designated as the primary panel.
    All panels on the dashboard will be queried for their data.

    Args:
        url (str): Full Grafana dashboard URL with optional viewPanel parameter
                   (e.g., 'https://unionai.grafana.net/d/e65d0d7c-cb63-4d2c-826f-6bc8305a303d?from=1763655790000&orgId=1&to=1763659420252&viewPanel=115')
        include_all_panels (bool): If True, fetch data for all panels. If False, only fetch the primary panel.

    Returns:
        dict: Contains dashboard info, primary_panel (if specified), and all_panels data
    """
    # Parse URL to extract components
    url_info = parse_grafana_url(url)

    dashboard_uid = url_info["dashboard_uid"]
    primary_panel_id = url_info["panel_id"]
    from_timestamp = url_info["from_timestamp"]
    to_timestamp = url_info["to_timestamp"]
    org_id = url_info["org_id"]
    base_url = url_info["base_url"]

    print(f"Querying Grafana dashboard {dashboard_uid}")
    if primary_panel_id:
        print(f"Primary panel: {primary_panel_id}")

    # Get authentication token from environment
    auth_token = os.getenv("GRAFANA_AUTH_TOKEN")
    if not auth_token:
        raise ValueError("GRAFANA_AUTH_TOKEN environment variable is not set")

    # First, get the dashboard definition to understand the panels
    dashboard_url = f"{base_url}/api/dashboards/uid/{dashboard_uid}"

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    with httpx.Client(timeout=30.0) as client:
        # Get dashboard metadata
        print(f"Fetching dashboard metadata from {dashboard_url}")
        dashboard_response = client.get(
            dashboard_url,
            headers=headers,
            params={"orgId": org_id}
        )
        dashboard_response.raise_for_status()
        dashboard_data = dashboard_response.json()

        # Get all panels from the dashboard
        dashboard_json = dashboard_data.get("dashboard", {})
        panels = dashboard_json.get("panels", [])

        result = {
            "dashboard_uid": dashboard_uid,
            "dashboard_title": dashboard_json.get("title"),
            "time_range": {
                "from": from_timestamp,
                "to": to_timestamp
            },
            "primary_panel_id": primary_panel_id,
            "primary_panel": None,
            "all_panels": []
        }

        # Query all panels
        for panel in panels:
            panel_data = query_panel_data(
                client, base_url, headers, dashboard_uid,
                panel, from_timestamp, to_timestamp, org_id
            )

            result["all_panels"].append(panel_data)

            # Mark the primary panel if it matches
            if primary_panel_id and panel.get("id") == primary_panel_id:
                result["primary_panel"] = panel_data

        # If only primary panel requested and it exists
        if not include_all_panels and result["primary_panel"]:
            result["all_panels"] = [result["primary_panel"]]

        print(f"Fetched data for {len(result['all_panels'])} panel(s)")
        return result


def get_grafana_dashboard_info(url: str) -> dict:
    """
    Retrieves information about a Grafana dashboard from a Grafana URL.

    Args:
        url (str): Full Grafana dashboard URL
                   (e.g., 'https://unionai.grafana.net/d/e65d0d7c-cb63-4d2c-826f-6bc8305a303d?orgId=1')

    Returns:
        dict: Dashboard metadata including title, panels, tags, and settings
    """
    # Parse URL to extract components
    url_info = parse_grafana_url(url)

    dashboard_uid = url_info["dashboard_uid"]
    org_id = url_info["org_id"]
    base_url = url_info["base_url"]

    print(f"Fetching Grafana dashboard info for {dashboard_uid}")

    # Get authentication token from environment
    auth_token = os.getenv("GRAFANA_AUTH_TOKEN")
    if not auth_token:
        raise ValueError("GRAFANA_AUTH_TOKEN environment variable is not set")

    dashboard_url = f"{base_url}/api/dashboards/uid/{dashboard_uid}"

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    with httpx.Client() as client:
        print(f"Fetching dashboard from {dashboard_url}")
        response = client.get(
            dashboard_url,
            headers=headers,
            params={"orgId": org_id}
        )
        response.raise_for_status()
        data = response.json()

        dashboard = data.get("dashboard", {})

        # Extract relevant dashboard information
        dashboard_info = {
            "uid": dashboard.get("uid"),
            "title": dashboard.get("title"),
            "tags": dashboard.get("tags", []),
            "timezone": dashboard.get("timezone"),
            "panels": [
                {
                    "id": panel.get("id"),
                    "title": panel.get("title"),
                    "type": panel.get("type")
                }
                for panel in dashboard.get("panels", [])
            ],
            "version": dashboard.get("version"),
            "schema_version": dashboard.get("schemaVersion")
        }

        return dashboard_info


if __name__ == '__main__':
    r = get_grafana_panel_data(
        url="https://unionai.grafana.net/d/e65d0d7c-cb63-4d2c-826f-6bc8305a303d?from=1763655790000&orgId=1&to=1763659420252&viewPanel=115"
    )
    print(r)
