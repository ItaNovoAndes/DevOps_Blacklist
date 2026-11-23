"""Prueba de estrés para blacklist-ms (Entrega 4 - Monitoreo continuo con New Relic).

Solo usa la librería estándar de Python. Genera tráfico concurrente contra el ALB
mezclando peticiones exitosas y peticiones que producen errores (400, 401, 409),
para que New Relic muestre tiempos de respuesta, Apdex, errores y dispare alertas.

Uso:
    export BASE_URL=http://blacklist-ms-alb-1459916110.us-east-2.elb.amazonaws.com
    export JWT_TOKEN=<token estático>        # no lo guardes en el repo
    python3 scripts/stress_test.py --duration 300 --workers 20
"""
import argparse
import json
import os
import random
import statistics
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter

# Peso de cada escenario en la mezcla de tráfico.
SCENARIOS = [
    ("ping", 15),
    ("post_ok", 25),           # 201
    ("get_ok", 30),            # 200
    ("post_duplicate", 10),    # 409
    ("post_invalid", 8),       # 400
    ("get_no_token", 6),       # 401
    ("post_bad_token", 6),     # 401
]


def request(method, url, token=None, body=None, timeout=15):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
            status = resp.status
    except urllib.error.HTTPError as err:
        status = err.code
    except Exception:
        status = "conn_error"
    return status, (time.perf_counter() - start) * 1000


def new_email():
    return f"stress-{uuid.uuid4().hex[:12]}@example.com"


def worker(base, token, deadline, known, lock, results):
    names = [s[0] for s in SCENARIOS]
    weights = [s[1] for s in SCENARIOS]
    while time.time() < deadline:
        scenario = random.choices(names, weights)[0]
        with lock:
            existing = random.choice(known) if known else None
        if scenario == "ping":
            status, ms = request("GET", f"{base}/ping")
        elif scenario == "post_ok":
            email = new_email()
            status, ms = request("POST", f"{base}/blacklists", token, {
                "email": email, "app_uuid": str(uuid.uuid4()), "blocked_reason": "prueba de estrés"})
            if status == 201:
                with lock:
                    known.append(email)
        elif scenario == "get_ok":
            status, ms = request("GET", f"{base}/blacklists/{existing or new_email()}", token)
        elif scenario == "post_duplicate" and existing:
            status, ms = request("POST", f"{base}/blacklists", token, {
                "email": existing, "app_uuid": str(uuid.uuid4()), "blocked_reason": "duplicado"})
        elif scenario == "post_invalid":
            status, ms = request("POST", f"{base}/blacklists", token, {"email": "no-es-un-email"})
        elif scenario == "get_no_token":
            status, ms = request("GET", f"{base}/blacklists/{new_email()}")
        elif scenario == "post_bad_token":
            status, ms = request("POST", f"{base}/blacklists", "token-invalido", {
                "email": new_email(), "app_uuid": str(uuid.uuid4()), "blocked_reason": "x"})
        else:
            continue
        with lock:
            results.append((scenario, status, ms))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL"))
    parser.add_argument("--token", default=os.environ.get("JWT_TOKEN"))
    parser.add_argument("--duration", type=int, default=300, help="segundos (default 300)")
    parser.add_argument("--workers", type=int, default=20, help="hilos concurrentes (default 20)")
    args = parser.parse_args()
    if not args.base_url or not args.token:
        parser.error("define BASE_URL y JWT_TOKEN (variables de entorno o --base-url/--token)")

    base = args.base_url.rstrip("/")
    deadline = time.time() + args.duration
    known, results, lock = [], [], threading.Lock()
    print(f"Prueba de estrés contra {base}: {args.workers} hilos durante {args.duration}s...")

    threads = [threading.Thread(target=worker, args=(base, args.token, deadline, known, lock, results), daemon=True)
               for _ in range(args.workers)]
    for t in threads:
        t.start()
    while any(t.is_alive() for t in threads):
        time.sleep(10)
        with lock:
            print(f"  {len(results)} peticiones enviadas...")

    latencies = [r[2] for r in results]
    print(f"\nTotal peticiones: {len(results)}  ({len(results) / args.duration:.1f} req/s)")
    if latencies:
        q = statistics.quantiles(latencies, n=100)
        print(f"Latencia ms -> promedio {statistics.mean(latencies):.0f} | p50 {q[49]:.0f} | p95 {q[94]:.0f} | p99 {q[98]:.0f}")
    print("Códigos de respuesta:", dict(Counter(str(r[1]) for r in results)))
    print("Por escenario:")
    for (scenario, status), n in sorted(Counter((r[0], str(r[1])) for r in results).items()):
        print(f"  {scenario:16s} {status:>10s}  {n}")


if __name__ == "__main__":
    main()
