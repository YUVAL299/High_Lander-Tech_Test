"""A tiny stand-in for OSRM, used by the end-to-end tests.

It answers /route with an L-shaped path (east/west first, then north/south)
and /nearest with the input point, so tests are deterministic and need no
internet access or map data. Not for real use: it knows nothing about roads.
"""

import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def haversine_m(a, b):
    r = 6_371_008.8
    p1, p2 = math.radians(a[1]), math.radians(b[1])
    dp, dl = p2 - p1, math.radians(b[0] - a[0])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        coords = [tuple(map(float, c.split(","))) for c in path.rsplit("/", 1)[-1].split(";")]
        if "/route/" in path:
            a, b = coords
            corner = (b[0], a[1])
            dist = haversine_m(a, corner) + haversine_m(corner, b)
            body = {
                "code": "Ok",
                "routes": [
                    {
                        "distance": dist,
                        "duration": dist / 1.4,
                        "geometry": {"type": "LineString", "coordinates": [a, corner, b]},
                    }
                ],
            }
        elif "/nearest/" in path:
            body = {"code": "Ok", "waypoints": [{"location": coords[0]}]}
        else:
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 5000), Handler).serve_forever()
