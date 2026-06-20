import json
import statistics
from pathlib import Path
from http.server import BaseHTTPRequestHandler

DATA_PATH = Path(__file__).parent.parent / "data" / "telemetry.json"
with open(DATA_PATH) as f:
    ALL_RECORDS = json.load(f)


def compute_metrics(records: list[dict], threshold_ms: float) -> dict:
    latencies = [r["latency_ms"] for r in records]
    uptimes   = [r["uptime_pct"] for r in records]

    sorted_lat = sorted(latencies)
    n = len(sorted_lat)
    p95_index = max(0, int(0.95 * n) - 1)

    return {
        "avg_latency": round(statistics.mean(latencies), 2),
        "p95_latency": round(sorted_lat[p95_index], 2),
        "avg_uptime":  round(statistics.mean(uptimes), 3),
        "breaches":    sum(1 for l in latencies if l > threshold_ms),
    }


class handler(BaseHTTPRequestHandler):

    def _send(self, status: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    # CORS preflight
    def do_OPTIONS(self):
        self._send(204, {})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            self._send(400, {"error": "Invalid JSON"})
            return

        regions      = [r.lower() for r in body.get("regions", [])]
        threshold_ms = float(body.get("threshold_ms", 200))

        if not regions:
            self._send(400, {"error": "'regions' list is required"})
            return

        result = {}
        for region in regions:
            records = [r for r in ALL_RECORDS if r["region"] == region]
            if not records:
                result[region] = {"error": "No data found"}
            else:
                result[region] = compute_metrics(records, threshold_ms)

        self._send(200, result)
