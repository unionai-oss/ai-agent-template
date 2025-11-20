import os
from urllib.parse import urlparse, parse_qs
import asyncio
import json
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


def _timestamp_to_iso(timestamp_ms):
    """Convert millisecond timestamp to ISO format string."""
    if not timestamp_ms:
        return None
    from datetime import datetime
    return datetime.fromtimestamp(timestamp_ms / 1000).isoformat()


def _generate_series_summary(series, labels):
    """Generate a human-readable summary for a series."""
    parts = []

    # Add label context
    if labels:
        label_str = ", ".join(f"{k}={v}" for k, v in labels.items())
        parts.append(f"Series for {label_str}")
    else:
        parts.append("Aggregate series")

    # Add value context
    max_val = series.get("max", 0)
    avg_val = series.get("avg", 0)

    if max_val > 0:
        parts.append(f"showing elevated values (max: {max_val:.6f}, avg: {avg_val:.6f})")
    else:
        parts.append("showing no elevated values")

    # Add trend context
    if series.get("trend"):
        direction = series["trend"].get("direction")
        change = abs(series["trend"].get("change_percent", 0))
        parts.append(f"with {direction} trend ({change:.1f}% change)")

    # Add anomaly context
    if series.get("anomalies"):
        spike_count = series["anomalies"].get("spike_count")
        parts.append(f"and {spike_count} anomalous spikes detected")

    return "; ".join(parts)


def _get_issue_description(issue_type):
    """Get human-readable description for issue type."""
    descriptions = {
        "elevated_errors": "Elevated error rates detected - indicates service is experiencing errors",
        "high_latency": "High latency detected - indicates service response times are degraded"
    }
    return descriptions.get(issue_type, f"Issue type: {issue_type}")


def _generate_issue_interpretation(issue):
    """Generate interpretation for a panel with issues."""
    issue_type = issue.get("issue_type")
    metrics = issue.get("metrics", {})

    if issue_type == "elevated_errors":
        return f"Error rate at {metrics.get('avg', 0):.6f} (max: {metrics.get('max', 0):.6f}) - service is experiencing errors"
    elif issue_type == "high_latency":
        return f"Latency at {metrics.get('avg', 0):.3f}s average (max: {metrics.get('max', 0):.3f}s) - service response times are degraded"
    else:
        return f"Metrics show max: {metrics.get('max', 0):.6f}, avg: {metrics.get('avg', 0):.6f}"


def _generate_health_summary(summary):
    """Generate overall health summary."""
    health = summary.get("overall_health")
    issues = summary.get("panels_with_issues", [])

    if health == "healthy":
        return "All monitored metrics are within normal ranges"
    elif health == "degraded":
        issue_count = len(issues)
        issue_types = set(issue.get("issue_type") for issue in issues)

        summary_parts = [f"System is degraded with {issue_count} panel(s) showing issues"]

        if "elevated_errors" in issue_types:
            summary_parts.append("elevated error rates detected")
        if "high_latency" in issue_types:
            summary_parts.append("high latency detected")

        return "; ".join(summary_parts)
    else:
        return "Health status unknown - insufficient data"


def resolve_datasource_variables(datasource, dashboard_json, debug=False):
    """
    Resolve datasource template variables like ${datasource}.

    Args:
        datasource: Datasource config from panel (may contain template vars)
        dashboard_json: Full dashboard JSON with templating config
        debug: Print debug information

    Returns:
        Resolved datasource config or None if can't resolve
    """
    if not datasource:
        return None

    # If datasource UID contains a variable like ${datasource}
    ds_uid = datasource.get("uid", "")
    if ds_uid.startswith("${") and ds_uid.endswith("}"):
        var_name = ds_uid[2:-1]  # Extract variable name

        # Look for the variable in dashboard templating
        templating = dashboard_json.get("templating", {})
        template_list = templating.get("list", [])

        for template_var in template_list:
            if template_var.get("name") == var_name:
                # Get current value or first option
                current = template_var.get("current", {})
                value = current.get("value")

                if not value and template_var.get("options"):
                    # Use first option if no current value
                    value = template_var["options"][0].get("value")

                if value:
                    resolved = {
                        "type": datasource.get("type"),
                        "uid": value
                    }
                    if debug:
                        print(f"    Resolved datasource ${{{var_name}}} -> {value}")
                    return resolved

        if debug:
            print(f"    Could not resolve datasource variable: ${{{var_name}}}")
        # If we can't resolve, return None (will skip querying)
        return None

    # No variable to resolve
    return datasource


async def query_panel_data(client, base_url, headers, panel, dashboard_json, from_timestamp, to_timestamp, org_id):
    """
    Query actual data for a specific panel using Grafana's query API.

    Args:
        client: httpx.AsyncClient instance
        base_url: Grafana base URL
        headers: Request headers with authentication
        panel: Panel configuration object
        dashboard_json: Full dashboard JSON (for resolving template variables)
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
            # Resolve datasource variables
            panel_datasource = panel.get("datasource")
            resolved_datasource = resolve_datasource_variables(panel_datasource, dashboard_json)

            if not resolved_datasource:
                panel_info["data_status"] = "skipped"
                panel_info["data_error"] = f"Could not resolve datasource: {panel_datasource}"
                return panel_info

            # Use Grafana's ds/query API to query panel data
            query_url = f"{base_url}/api/ds/query"

            # Extract template variables for substitution
            template_var_map = {}
            templating = dashboard_json.get("templating", {})
            for template_var in templating.get("list", []):
                var_name = template_var.get("name")
                current = template_var.get("current", {})
                if var_name and current:
                    value = current.get("value")
                    # Handle special Grafana values
                    if value == "$__all" or value == ["$__all"]:
                        # For "All", use .* regex to match everything
                        template_var_map[var_name] = ".*"
                    elif isinstance(value, list):
                        # Multiple values - join with |
                        template_var_map[var_name] = "|".join(str(v) for v in value)
                    else:
                        template_var_map[var_name] = str(value)

            # Build queries from panel targets
            queries = []
            for target in panel.get("targets", []):
                # Resolve datasource for each target too
                target_datasource = target.get("datasource", resolved_datasource)
                target_resolved = resolve_datasource_variables(target_datasource, dashboard_json)

                if not target_resolved:
                    continue

                # Get the query expression and substitute template variables
                expr = target.get("expr", "")
                if expr:
                    # Replace template variables in the expression
                    for var_name, var_value in template_var_map.items():
                        expr = expr.replace(f"${var_name}", var_value)
                        expr = expr.replace(f"${{{var_name}}}", var_value)

                query = {
                    "refId": target.get("refId", "A"),
                    "datasource": target_resolved,
                    "expr": expr,  # For Prometheus - now with substituted variables
                    "query": target.get("query"),  # For other datasources
                    "queryType": target.get("queryType"),
                    "intervalMs": target.get("intervalMs", 1000),
                    "maxDataPoints": target.get("maxDataPoints", 1000),
                }
                # Add any other target properties
                query.update({k: v for k, v in target.items() if k not in query and k != "datasource" and k != "expr"})
                queries.append(query)

            if not queries:
                panel_info["data_status"] = "skipped"
                panel_info["data_error"] = "No resolvable queries found"
                return panel_info

            # Extract template variables from dashboard to pass to query
            scoped_vars = {}
            templating = dashboard_json.get("templating", {})
            for template_var in templating.get("list", []):
                var_name = template_var.get("name")
                current = template_var.get("current", {})
                if var_name and current:
                    # Format the variable value for Grafana query API
                    value = current.get("value")
                    text = current.get("text")
                    scoped_vars[var_name] = {
                        "text": text,
                        "value": value
                    }

            query_payload = {
                "queries": queries,
                "from": str(from_timestamp),
                "to": str(to_timestamp),
                "scopedVars": scoped_vars
            }

            print(f"  Querying data for panel {panel_id}: {panel.get('title')}")
            print(f"    Template substitutions: {template_var_map}")
            if queries and queries[0].get("expr"):
                print(f"    Substituted query: {queries[0]['expr'][:200]}...")  # Show first 200 chars
            query_response = await client.post(
                query_url,
                headers=headers,
                json=query_payload,
                params={"orgId": org_id}
            )

            if query_response.status_code == 200:
                response_data = query_response.json()
                panel_info["data"] = response_data
                panel_info["data_status"] = "success"

                # Debug: Check how many frames we actually got
                for ref_id, result in response_data.get("results", {}).items():
                    num_frames = len(result.get("frames", []))
                    print(f"    RefID {ref_id}: {num_frames} frame(s) returned")
            else:
                panel_info["data_status"] = "failed"
                panel_info["data_error"] = f"HTTP {query_response.status_code}: {query_response.text}"

        except Exception as e:
            panel_info["data_status"] = "error"
            panel_info["data_error"] = str(e)
    else:
        panel_info["data_status"] = "no_time_range"

    return panel_info


async def get_grafana_panel_data(url: str, include_all_panels: bool = True) -> dict:
    """
    Queries Grafana for dashboard panel data from a Grafana URL.

    If the URL contains a viewPanel parameter, that panel will be designated as the primary panel.
    All panels on the dashboard will be queried for their data in parallel.

    Args:
        url (str): Full Grafana dashboard URL with optional viewPanel parameter
                   (e.g., 'https://unionai.grafana.net/d/e65d0d7c-cb63-4d2c-826f-6bc8305a303d?from=1763655790000&orgId=1&to=1763659420252&viewPanel=115')
        include_all_panels (bool): If True, fetch data for all panels. If False, only fetch the primary panel.

    Returns:
        dict: Contains:
            - dashboard_uid: Dashboard unique identifier
            - dashboard_title: Dashboard name
            - time_range: Query time range (from/to timestamps)
            - primary_panel_id: ID of primary panel (if specified in URL)
            - primary_panel: Raw data for primary panel
            - all_panels: Raw data for all queried panels
            - summary: Agent-friendly summary with insights, trends, and health status
            - analysis: Technical analysis of query results
            - agent_response: Clean formatted response with:
                - dashboard_title: Dashboard name
                - time_range: Query time range
                - overall_health: "healthy", "degraded", or "unknown"
                - primary_panel: Panel insights with series data, trends, and anomalies
                - panels_with_issues: List of panels with detected issues
                - technical_summary: Query success/failure counts
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

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get dashboard metadata
        print(f"Fetching dashboard metadata from {dashboard_url}")
        dashboard_response = await client.get(
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
            "dashboard_json": dashboard_json,  # Include full dashboard JSON for debugging
            "time_range": {
                "from": from_timestamp,
                "to": to_timestamp
            },
            "primary_panel_id": primary_panel_id,
            "primary_panel": None,
            "all_panels": []
        }

        # Determine which panels to query
        panels_to_query = panels
        if not include_all_panels and primary_panel_id:
            panels_to_query = [p for p in panels if p.get("id") == primary_panel_id]

        # Query all panels in parallel using asyncio.gather
        print(f"Querying {len(panels_to_query)} panel(s) in parallel...")
        panel_tasks = [
            query_panel_data(
                client, base_url, headers,
                panel, dashboard_json, from_timestamp, to_timestamp, org_id
            )
            for panel in panels_to_query
        ]

        # Wait for all panel queries to complete
        all_panel_data = await asyncio.gather(*panel_tasks, return_exceptions=True)

        # Process results
        for panel_data in all_panel_data:
            if isinstance(panel_data, Exception):
                # Handle exception from gather
                print(f"Error querying panel: {panel_data}")
                continue

            result["all_panels"].append(panel_data)

            # Mark the primary panel if it matches
            if primary_panel_id and panel_data.get("panel_id") == primary_panel_id:
                result["primary_panel"] = panel_data

        print(f"Fetched data for {len(result['all_panels'])} panel(s)")

        # Add agent-friendly summary
        summary = summarize_dashboard_for_agent(result)
        result["summary"] = summary

        # Add technical analysis
        analysis = analyze_panel_results(result)
        result["analysis"] = analysis

        # Create a clean, agent-friendly response format with enhanced context
        primary_panel = summary.get("primary_panel")

        # Enhance primary panel with more context
        enhanced_primary = None
        if primary_panel:
            enhanced_primary = {
                "panel_id": primary_panel.get("panel_id"),
                "title": primary_panel.get("title"),
                "description": f"Panel measuring: {primary_panel.get('title')}",
                "status": primary_panel.get("status"),
                "has_data": primary_panel.get("has_data"),
                "series": []
            }

            # Add enhanced series information
            for series in primary_panel.get("series", []):
                labels = series.get("labels", {})

                # Build human-readable description from labels
                label_descriptions = []
                for key, value in labels.items():
                    label_descriptions.append(f"{key}: {value}")

                enhanced_series = {
                    "series_name": series.get("name"),
                    "labels": labels,  # Keep original labels
                    "label_description": ", ".join(label_descriptions) if label_descriptions else "aggregate metric",
                    "metrics": {
                        "min": series.get("min"),
                        "max": series.get("max"),
                        "avg": series.get("avg"),
                        "current": series.get("current"),
                        "first": series.get("first"),
                    },
                    "interpretation": {
                        "has_elevated_values": series.get("max", 0) > 0,
                        "highest_value_seen": series.get("max"),
                        "average_value": series.get("avg"),
                        "current_value": series.get("current"),
                    }
                }

                # Add trend information if available
                if series.get("trend"):
                    trend = series["trend"]
                    enhanced_series["trend"] = {
                        "direction": trend.get("direction"),
                        "change_percent": trend.get("change_percent"),
                        "first_half_avg": trend.get("first_half_avg"),
                        "second_half_avg": trend.get("second_half_avg"),
                        "interpretation": f"Metric is {trend.get('direction')} with a {abs(trend.get('change_percent', 0)):.1f}% change"
                    }

                # Add anomaly information if available
                if series.get("anomalies"):
                    anomalies = series["anomalies"]
                    enhanced_series["anomalies"] = {
                        "spike_count": anomalies.get("spike_count"),
                        "max_spike_value": anomalies.get("max_spike"),
                        "spike_threshold": anomalies.get("spike_threshold"),
                        "interpretation": f"Detected {anomalies.get('spike_count')} spikes above {anomalies.get('spike_threshold'):.6f}, with max spike reaching {anomalies.get('max_spike'):.6f}"
                    }

                enhanced_series["summary"] = _generate_series_summary(series, labels)
                enhanced_primary["series"].append(enhanced_series)

        # Enhance panels with issues
        enhanced_issues = []
        for issue in summary.get("panels_with_issues", []):
            enhanced_issue = {
                "panel_id": issue.get("panel_id"),
                "panel_title": issue.get("title"),
                "issue_type": issue.get("issue_type"),
                "issue_description": _get_issue_description(issue.get("issue_type")),
                "metrics": issue.get("metrics"),
                "trend": issue.get("trend"),
                "anomalies": issue.get("anomalies"),
                "interpretation": _generate_issue_interpretation(issue)
            }
            enhanced_issues.append(enhanced_issue)

        result["agent_response"] = {
            "dashboard_title": result.get("dashboard_title"),
            "time_range": {
                "from": from_timestamp,
                "to": to_timestamp,
                "from_iso": _timestamp_to_iso(from_timestamp),
                "to_iso": _timestamp_to_iso(to_timestamp),
                "duration_minutes": (to_timestamp - from_timestamp) / 1000 / 60 if from_timestamp and to_timestamp else None
            },
            "overall_health": summary.get("overall_health"),
            "health_summary": _generate_health_summary(summary),
            "primary_panel": enhanced_primary,
            "panels_with_issues": enhanced_issues,
            "technical_summary": {
                "total_panels": analysis.get("total_panels"),
                "successful_queries": analysis.get("successful"),
                "failed_queries": analysis.get("failed"),
                "skipped_queries": analysis.get("skipped"),
                "data_quality": "good" if analysis.get("successful", 0) > analysis.get("failed", 0) else "degraded"
            }
        }

        return result


async def get_grafana_dashboard_info(url: str) -> dict:
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

    async with httpx.AsyncClient() as client:
        print(f"Fetching dashboard from {dashboard_url}")
        response = await client.get(
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


def extract_panel_insights(panel_data: dict, debug: bool = False) -> dict:
    """
    Extract actionable insights from panel data for an AI agent.

    Transforms raw Grafana data into human-readable metrics and trends
    that help determine if an alert was firing and provide context.

    Args:
        panel_data: Panel data from query_panel_data()
        debug: Print debug information about data extraction

    Returns:
        dict: Insights including summary stats, trends, and interpretation
    """
    insights = {
        "panel_id": panel_data.get("panel_id"),
        "title": panel_data.get("title"),
        "type": panel_data.get("type"),
        "status": panel_data.get("data_status"),
        "has_data": False,
        "series": []
    }

    # If query failed or was skipped, return early
    if panel_data.get("data_status") != "success":
        insights["error"] = panel_data.get("data_error")
        return insights

    # Parse the raw Grafana response
    raw_data = panel_data.get("data", {})
    results = raw_data.get("results", {})

    if debug:
        print(f"\n[DEBUG] Extracting insights for panel {panel_data.get('panel_id')}: {panel_data.get('title')}")
        print(f"[DEBUG] Number of query results: {len(results)}")

    for ref_id, result in results.items():
        frames = result.get("frames", [])
        if debug:
            print(f"[DEBUG] RefID {ref_id}: {len(frames)} frame(s)")

        for frame_idx, frame in enumerate(frames):
            schema = frame.get("schema", {})
            fields = schema.get("fields", [])
            data = frame.get("data", {})
            values = data.get("values", [])

            if debug:
                print(f"[DEBUG]   Frame {frame_idx}: {len(fields)} field(s), {len(values)} value array(s)")
                for idx, field in enumerate(fields):
                    print(f"[DEBUG]     Field {idx}: name='{field.get('name')}', type='{field.get('type')}', labels={field.get('labels', {})}")

            # Find time and value fields - check ALL numeric fields, not just first
            time_field_idx = None
            value_fields = []  # Track all value fields with their labels

            for idx, field in enumerate(fields):
                field_name = field.get("name", "")
                field_type = field.get("type", "")
                field_labels = field.get("labels", {})  # Extract labels from field (e.g., {'region': 'us-east-2'})

                if field_name == "Time" or field_type == "time":
                    time_field_idx = idx
                elif field_type in ["number", "float64", "int64"]:
                    # Use labels to create a more descriptive series name
                    if field_labels:
                        # Create name from labels like "us-east-2" from {'region': 'us-east-2'}
                        label_str = ", ".join(f"{k}={v}" for k, v in field_labels.items())
                        series_name = label_str or field_name or f"series_{idx}"
                    else:
                        series_name = field_name or f"series_{idx}"

                    value_fields.append((idx, series_name, field_labels))

            if debug:
                print(f"[DEBUG]   Time field index: {time_field_idx}")
                print(f"[DEBUG]   Value fields: {[(idx, name, labels) for idx, name, labels in value_fields]}")

            # Extract time series data for each value field
            if time_field_idx is not None and value_fields and len(values) > 0:
                timestamps = values[time_field_idx] if time_field_idx < len(values) else []

                for value_field_idx, value_field_name, field_labels in value_fields:
                    if value_field_idx >= len(values):
                        continue

                    vals = values[value_field_idx]

                    if vals:
                        insights["has_data"] = True

                        # Calculate statistics
                        numeric_vals = [v for v in vals if v is not None and isinstance(v, (int, float))]

                        if debug:
                            print(f"[DEBUG]   Field '{value_field_name}': {len(numeric_vals)} numeric values")
                            if numeric_vals:
                                print(f"[DEBUG]     Range: {min(numeric_vals):.6f} to {max(numeric_vals):.6f}")

                        if numeric_vals:
                            series_insight = {
                                "name": value_field_name,
                                "labels": field_labels,  # Use labels from field definition
                                "count": len(numeric_vals),
                                "min": min(numeric_vals),
                                "max": max(numeric_vals),
                                "avg": sum(numeric_vals) / len(numeric_vals),
                                "current": numeric_vals[-1] if numeric_vals else None,
                                "first": numeric_vals[0] if numeric_vals else None,
                            }

                            # Detect trends
                            if len(numeric_vals) >= 2:
                                first_half_avg = sum(numeric_vals[:len(numeric_vals)//2]) / (len(numeric_vals)//2)
                                second_half_avg = sum(numeric_vals[len(numeric_vals)//2:]) / (len(numeric_vals) - len(numeric_vals)//2)

                                change_pct = ((second_half_avg - first_half_avg) / first_half_avg * 100) if first_half_avg != 0 else 0

                                series_insight["trend"] = {
                                    "first_half_avg": first_half_avg,
                                    "second_half_avg": second_half_avg,
                                    "change_percent": change_pct,
                                    "direction": "increasing" if change_pct > 10 else "decreasing" if change_pct < -10 else "stable"
                                }

                            # Detect spikes (values > 2x average)
                            avg_val = series_insight["avg"]
                            spikes = [v for v in numeric_vals if v > avg_val * 2]
                            if spikes:
                                series_insight["anomalies"] = {
                                    "spike_count": len(spikes),
                                    "max_spike": max(spikes),
                                    "spike_threshold": avg_val * 2
                                }

                            insights["series"].append(series_insight)

    if debug and not insights["has_data"]:
        print(f"[DEBUG] WARNING: No data extracted for panel {panel_data.get('panel_id')}")

    return insights


def summarize_dashboard_for_agent(result: dict) -> dict:
    """
    Create a concise summary of dashboard data optimized for AI agent consumption.

    This transforms raw panel data into actionable insights that help an agent
    determine if an alert was firing and understand the context.

    Args:
        result: Result from get_grafana_panel_data()

    Returns:
        dict: Agent-friendly summary with key metrics and insights
    """
    summary = {
        "dashboard_title": result.get("dashboard_title"),
        "time_range": result.get("time_range"),
        "primary_panel": None,
        "panels_with_issues": [],
        "all_panel_insights": [],
        "overall_health": "unknown"
    }

    # Extract insights from all panels
    for panel in result.get("all_panels", []):
        insights = extract_panel_insights(panel)
        summary["all_panel_insights"].append(insights)

        # Flag panels with concerning data
        if insights.get("has_data"):
            for series in insights.get("series", []):
                # Check for error-related panels with high values
                title_lower = insights["title"].lower() if insights["title"] else ""

                if any(keyword in title_lower for keyword in ["error", "5xx", "4xx", "fail"]):
                    if series.get("max", 0) > 0 or series.get("avg", 0) > 0:
                        summary["panels_with_issues"].append({
                            "panel_id": insights["panel_id"],
                            "title": insights["title"],
                            "issue_type": "elevated_errors",
                            "metrics": {
                                "avg": series["avg"],
                                "max": series["max"],
                                "current": series["current"]
                            },
                            "trend": series.get("trend", {}).get("direction"),
                            "anomalies": series.get("anomalies")
                        })

                # Check for latency panels with high values
                elif any(keyword in title_lower for keyword in ["latency", "duration", "response time", "p99", "p95"]):
                    # If latency avg > 1 second (1000ms), flag it
                    if series.get("avg", 0) > 1:
                        summary["panels_with_issues"].append({
                            "panel_id": insights["panel_id"],
                            "title": insights["title"],
                            "issue_type": "high_latency",
                            "metrics": {
                                "avg": series["avg"],
                                "max": series["max"],
                                "current": series["current"]
                            },
                            "trend": series.get("trend", {}).get("direction")
                        })

    # Extract primary panel insights
    if result.get("primary_panel"):
        summary["primary_panel"] = extract_panel_insights(result["primary_panel"])

    # Determine overall health
    if summary["panels_with_issues"]:
        summary["overall_health"] = "degraded"
    elif summary["all_panel_insights"]:
        summary["overall_health"] = "healthy"

    return summary


def analyze_panel_results(result: dict) -> dict:
    """
    Analyze panel query results and provide a summary of what went wrong.

    Args:
        result: Result dictionary from get_grafana_panel_data()

    Returns:
        dict: Analysis summary with counts and issues
    """
    analysis = {
        "total_panels": len(result.get("all_panels", [])),
        "successful": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
        "no_time_range": 0,
        "issues": []
    }

    for panel in result.get("all_panels", []):
        status = panel.get("data_status", "unknown")

        if status == "success":
            analysis["successful"] += 1
            # Check if data is actually present
            data = panel.get("data", {})
            if not data or not data.get("results"):
                analysis["issues"].append({
                    "panel_id": panel.get("panel_id"),
                    "title": panel.get("title"),
                    "issue": "Success but no data returned",
                    "datasource": panel.get("datasource")
                })
        elif status == "failed":
            analysis["failed"] += 1
            analysis["issues"].append({
                "panel_id": panel.get("panel_id"),
                "title": panel.get("title"),
                "issue": f"Failed: {panel.get('data_error', 'Unknown error')}",
                "datasource": panel.get("datasource")
            })
        elif status == "skipped":
            analysis["skipped"] += 1
            analysis["issues"].append({
                "panel_id": panel.get("panel_id"),
                "title": panel.get("title"),
                "issue": f"Skipped: {panel.get('data_error', 'Unknown reason')}",
                "datasource": panel.get("datasource")
            })
        elif status == "error":
            analysis["errors"] += 1
            analysis["issues"].append({
                "panel_id": panel.get("panel_id"),
                "title": panel.get("title"),
                "issue": f"Error: {panel.get('data_error', 'Unknown error')}",
                "datasource": panel.get("datasource")
            })
        elif status == "no_time_range":
            analysis["no_time_range"] += 1

    # Check primary panel specifically
    if result.get("primary_panel"):
        primary = result["primary_panel"]
        primary_status = primary.get("data_status")
        analysis["primary_panel_status"] = primary_status

        if primary_status != "success":
            analysis["primary_panel_issue"] = {
                "panel_id": primary.get("panel_id"),
                "title": primary.get("title"),
                "status": primary_status,
                "error": primary.get("data_error"),
                "datasource": primary.get("datasource")
            }

    return analysis


if __name__ == '__main__':
    async def main():
        # Use the URL from an alert notification - the timestamps represent when the alert fired
        # This is just an example URL - in production, this would come from the alert payload
        test_url = "https://unionai.grafana.net/d/e65d0d7c-cb63-4d2c-826f-6bc8305a303d?from=1763655790000&orgId=1&to=1763659420252&viewPanel=115"

        result = await get_grafana_panel_data(url=test_url)

        # Access the clean agent response
        agent_response = result.get("agent_response", {})

        # print("\n=== Agent Response ===")
        # print(f"Dashboard: {agent_response.get('dashboard_title')}")
        # print(f"Overall Health: {agent_response.get('overall_health')}")

        # # Primary panel insights
        # primary = agent_response.get('primary_panel')
        # if primary:
        #     print(f"\n=== Primary Panel: {primary.get('title')} ===")
        #     print(f"Description: {primary.get('description')}")
        #     print(f"Status: {primary.get('status')}")
        #     if primary.get('has_data'):
        #         print(f"Series count: {len(primary.get('series', []))}")
        #         for series in primary.get('series', []):
        #             # Only show series with data (max > 0)
        #             metrics = series.get('metrics', {})
        #             if metrics.get('max', 0) > 0:
        #                 print(f"\n  Series: {series.get('series_name')}")
        #                 print(f"    Label Description: {series.get('label_description')}")
        #                 print(f"    Labels: {series.get('labels')}")
        #                 print(f"    Avg: {metrics.get('avg'):.6f}, Max: {metrics.get('max'):.6f}")
        #                 print(f"    Summary: {series.get('summary')}")
        #                 if series.get('trend'):
        #                     print(f"    Trend: {series['trend']['interpretation']}")
        #                 if series.get('anomalies'):
        #                     print(f"    Anomalies: {series['anomalies']['interpretation']}")
        #     elif primary.get('error'):
        #         print(f"  Error: {primary.get('error')}")

        # # Panels with issues
        # panels_with_issues = agent_response.get('panels_with_issues', [])
        # if panels_with_issues:
        #     print(f"\n=== Panels with Issues ({len(panels_with_issues)}) ===")
        #     for issue in panels_with_issues[:5]:
        #         print(f"\n  {issue['panel_title']} ({issue['issue_type']})")
        #         print(f"    Panel ID: {issue['panel_id']}")
        #         print(f"    Description: {issue['issue_description']}")
        #         print(f"    Max: {issue['metrics']['max']:.6f}, Avg: {issue['metrics']['avg']:.6f}")
        #         print(f"    Interpretation: {issue['interpretation']}")
        #         if issue.get('trend'):
        #             print(f"    Trend: {issue['trend']}")

        # # Technical summary
        # tech = agent_response.get('technical_summary', {})
        # print(f"\n=== Technical Summary ===")
        # print(f"Total panels: {tech.get('total_panels')}")
        # print(f"Successful queries: {tech.get('successful_queries')}")
        # print(f"Failed queries: {tech.get('failed_queries')}")
        # print(f"Skipped queries: {tech.get('skipped_queries')}")

        # Return the agent_response for use by other tools/agents
        print(json.dumps(agent_response, indent=2))
        print(json.dumps(agent_response["primary_panel"]["series"], indent=2))
        return agent_response

    asyncio.run(main())
