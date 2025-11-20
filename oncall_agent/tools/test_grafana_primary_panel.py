"""
Test script to query only the primary panel and print all raw data.
"""
import asyncio
import json
from grafana_tool import get_grafana_panel_data


async def main():
    # Use the URL from an alert notification - the timestamps represent when the alert fired
    test_url = "https://unionai.grafana.net/d/e65d0d7c-cb63-4d2c-826f-6bc8305a303d?from=1763655790000&orgId=1&to=1763659420252&viewPanel=115"

    print("Querying ONLY the primary panel (viewPanel=115)...")
    print("=" * 80)

    # Query only the primary panel (include_all_panels=False)
    result = await get_grafana_panel_data(url=test_url, include_all_panels=False)

    # Print the entire result as formatted JSON
    # print("\n=== FULL RAW DATA ===")
    # print(json.dumps(result, indent=2, default=str))

    # Also print primary panel data specifically
    if result.get('primary_panel'):
        # print("\n" + "=" * 80)
        # print("=== PRIMARY PANEL DATA ONLY ===")
        # print(json.dumps(result['primary_panel'], indent=2, default=str))

        # Print targets specifically to understand the query
        print("\n" + "=" * 80)
        print("=== PANEL TARGETS (QUERIES) ===")
        targets = result['primary_panel'].get('targets', [])
        for idx, target in enumerate(targets):
            print(f"\nTarget {idx}:")
            print(json.dumps(target, indent=2, default=str))

        # Print dashboard template variables
        print("\n" + "=" * 80)
        print("=== DASHBOARD TEMPLATE VARIABLES ===")
        if 'dashboard_json' in result:
            templating = result['dashboard_json'].get('templating', {})
            template_list = templating.get('list', [])
            for var in template_list:
                var_name = var.get('name')
                var_type = var.get('type')
                current = var.get('current', {})
                print(f"\nVariable: ${{{var_name}}}")
                print(f"  Type: {var_type}")
                print(f"  Current value: {current}")
        else:
            print("Dashboard JSON not available in result")

        # Print data field separately for easier inspection
        if result['primary_panel'].get('data'):
            print("\n" + "=" * 80)
            # print("=== PRIMARY PANEL 'data' FIELD ===")
            # print(json.dumps(result['primary_panel']['data'], indent=2, default=str))

            # Analyze the frame structure in detail
            print("\n" + "=" * 80)
            print("=== DETAILED FRAME ANALYSIS ===")
            raw_data = result['primary_panel'].get('data', {})
            results = raw_data.get('results', {})

            for ref_id, ref_result in results.items():
                print(f"\nRefID: {ref_id}")
                frames = ref_result.get('frames', [])
                print(f"  Number of frames: {len(frames)}")

                for frame_idx, frame in enumerate(frames):
                    print(f"\n  Frame {frame_idx}:")
                    schema = frame.get('schema', {})
                    fields = schema.get('fields', [])
                    data = frame.get('data', {})
                    values = data.get('values', [])

                    print(f"    Fields ({len(fields)}):")
                    for field_idx, field in enumerate(fields):
                        field_name = field.get('name', '')
                        field_type = field.get('type', '')
                        labels = field.get('labels', {})
                        print(f"      [{field_idx}] name='{field_name}', type='{field_type}', labels={labels}")

                    print(f"\n    Values (arrays):")
                    for val_idx, val_array in enumerate(values):
                        if val_array:
                            # Show first few and last few values
                            preview = val_array[:3] + ['...'] + val_array[-3:] if len(val_array) > 6 else val_array
                            print(f"      [{val_idx}] {len(val_array)} values: {preview}")

                            # If this is numeric data, show min/max
                            numeric_vals = [v for v in val_array if v is not None and isinstance(v, (int, float))]
                            if numeric_vals:
                                print(f"           min={min(numeric_vals):.6f}, max={max(numeric_vals):.6f}, avg={sum(numeric_vals)/len(numeric_vals):.6f}")


if __name__ == '__main__':
    asyncio.run(main())
