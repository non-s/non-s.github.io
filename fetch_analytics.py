#!/usr/bin/env python3
"""Fetch Google Analytics 4 data and save to _data/analytics.json"""
import os, json
from datetime import date, timedelta
import requests

def main():
    property_id = os.getenv("GA4_PROPERTY_ID")
    # Support service account via GOOGLE_INDEXING_CREDENTIALS (already used by google_index.py)
    creds_json = os.getenv("GOOGLE_INDEXING_CREDENTIALS")

    if not property_id:
        print("GA4_PROPERTY_ID not set — skipping")
        return

    try:
        # Use service account if available
        if creds_json:
            creds_data = json.loads(creds_json)
            # Get access token via service account JWT
            import time, base64
            header = base64.urlsafe_b64encode(json.dumps({"alg":"RS256","typ":"JWT"}).encode()).rstrip(b'=').decode()
            now = int(time.time())
            payload = {
                "iss": creds_data.get("client_email"),
                "scope": "https://www.googleapis.com/auth/analytics.readonly",
                "aud": "https://oauth2.googleapis.com/token",
                "exp": now + 3600,
                "iat": now
            }
            payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b'=').decode()
            signing_input = f"{header}.{payload_b64}"

            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            private_key = serialization.load_pem_private_key(
                creds_data["private_key"].encode(), password=None
            )
            signature = private_key.sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
            sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b'=').decode()
            jwt_token = f"{signing_input}.{sig_b64}"

            token_r = requests.post("https://oauth2.googleapis.com/token",
                data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": jwt_token})
            access_token = token_r.json().get("access_token")
            if not access_token:
                print("Failed to get GA4 access token")
                return

            headers = {"Authorization": f"Bearer {access_token}"}
        else:
            print("No Google credentials — skipping GA4")
            return

        # Query GA4 Data API — daily breakdown (last 30 days)
        report_url = f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"
        body = {
            "dateRanges": [{"startDate": "30daysAgo", "endDate": "today"}],
            "metrics": [
                {"name": "activeUsers"},
                {"name": "sessions"},
                {"name": "screenPageViews"},
                {"name": "averageSessionDuration"},
                {"name": "bounceRate"},
            ],
            "dimensions": [{"name": "date"}],
            "orderBys": [{"dimension": {"dimensionName": "date"}, "desc": True}],
            "limit": 30
        }
        r = requests.post(report_url, headers=headers, json=body, timeout=30)
        if r.status_code != 200:
            print(f"GA4 API error: {r.status_code} {r.text}")
            return

        data = r.json()
        rows = data.get("rows", [])

        analytics = {
            "last_updated": date.today().isoformat(),
            "daily": []
        }
        for row in rows:
            dims = [d["value"] for d in row.get("dimensionValues", [])]
            metrics = [m["value"] for m in row.get("metricValues", [])]
            analytics["daily"].append({
                "date": dims[0] if dims else "",
                "active_users": int(metrics[0]) if metrics else 0,
                "sessions": int(metrics[1]) if len(metrics) > 1 else 0,
                "pageviews": int(metrics[2]) if len(metrics) > 2 else 0,
                "avg_duration": float(metrics[3]) if len(metrics) > 3 else 0,
                "bounce_rate": float(metrics[4]) if len(metrics) > 4 else 0,
            })

        # Get top pages (last 7 days)
        pages_body = {
            "dateRanges": [{"startDate": "7daysAgo", "endDate": "today"}],
            "metrics": [{"name": "screenPageViews"}],
            "dimensions": [{"name": "pageTitle"}, {"name": "pagePath"}],
            "orderBys": [{"metric": {"metricName": "screenPageViews"}, "desc": True}],
            "limit": 10
        }
        r2 = requests.post(report_url, headers=headers, json=pages_body, timeout=30)
        if r2.status_code == 200:
            top_pages = []
            for row in r2.json().get("rows", []):
                dims = [d["value"] for d in row.get("dimensionValues", [])]
                metrics = [m["value"] for m in row.get("metricValues", [])]
                top_pages.append({
                    "title": dims[0] if dims else "",
                    "path": dims[1] if len(dims) > 1 else "",
                    "views": int(metrics[0]) if metrics else 0
                })
            analytics["top_pages"] = top_pages

        # Totals across 30d
        analytics["totals"] = {
            "active_users_30d": sum(d["active_users"] for d in analytics["daily"]),
            "sessions_30d": sum(d["sessions"] for d in analytics["daily"]),
            "pageviews_30d": sum(d["pageviews"] for d in analytics["daily"]),
        }

        os.makedirs("_data", exist_ok=True)
        with open("_data/analytics.json", "w") as f:
            json.dump(analytics, f, indent=2)
        print(f"GA4 data saved: {len(rows)} days, {analytics['totals']['pageviews_30d']} pageviews")

    except Exception as e:
        print(f"GA4 fetch error: {e}")
        import traceback; traceback.print_exc()

if __name__ == "__main__":
    main()
