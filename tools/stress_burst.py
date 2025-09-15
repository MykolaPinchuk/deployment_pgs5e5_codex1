#!/usr/bin/env python3
import argparse
import asyncio
import os
import random
import statistics
import time
from typing import List, Optional

import httpx


def make_payload(i: int) -> dict:
    return {
        "id": i,
        "Gender": "male",
        "Age": 30,
        "Height": 180,
        "Weight": 80,
        "Duration": 30,
        "Heart_Rate": 120,
        "Body_Temp": 37.0,
    }


async def run_once(client: httpx.AsyncClient, url: str, payload: dict):
    t0 = time.perf_counter()
    try:
        r = await client.post(url, json=payload)
        ok = r.status_code == 200
    except Exception:
        ok = False
    dt = time.perf_counter() - t0
    return ok, dt


async def stress(
    base_url: str,
    duration: float,
    rps: float,
    concurrency: int,
    seed: int = 42,
):
    random.seed(seed)
    url = base_url.rstrip("/") + "/predict"
    inter = 1.0 / max(0.1, rps)
    end = time.perf_counter() + duration
    latencies: List[float] = []
    ok_count = 0
    err_count = 0
    issued = 0

    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=5.0) as client:
        async def worker(i: int):
            nonlocal ok_count, err_count
            async with sem:
                ok, dt = await run_once(client, url, make_payload(i))
                latencies.append(dt)
                if ok:
                    ok_count += 1
                else:
                    err_count += 1

        i = 0
        while time.perf_counter() < end:
            asyncio.create_task(worker(i))
            i += 1
            issued += 1
            await asyncio.sleep(inter)
        # wait for in-flight
        await asyncio.sleep(min(5.0, duration))

    total = ok_count + err_count
    p50 = statistics.quantiles(latencies, n=100)[49] if latencies else 0.0
    p95 = statistics.quantiles(latencies, n=100)[94] if latencies else 0.0
    p99 = statistics.quantiles(latencies, n=100)[98] if latencies else 0.0
    print(f"issued={issued} total={total} ok={ok_count} err={err_count}")
    print(f"latency_p50={p50:.4f}s latency_p95={p95:.4f}s latency_p99={p99:.4f}s")


async def stress_asgi(duration: float, rps: float, concurrency: int):
    import importlib.util
    root = os.getcwd()
    svc_path = os.path.join(root, "service", "app.py")
    spec = importlib.util.spec_from_file_location("service_app", svc_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    inter = 1.0 / max(0.1, rps)
    end = time.perf_counter() + duration
    latencies: List[float] = []
    ok_count = 0
    err_count = 0
    issued = 0
    sem = asyncio.Semaphore(concurrency)

    transport = httpx.ASGITransport(app=module.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://app", timeout=5.0) as client:
        async def worker(i: int):
            nonlocal ok_count, err_count
            async with sem:
                t0 = time.perf_counter()
                try:
                    r = await client.post("/predict", json=make_payload(i))
                    ok = r.status_code == 200
                except Exception:
                    ok = False
                dt = time.perf_counter() - t0
                latencies.append(dt)
                if ok:
                    ok_count += 1
                else:
                    err_count += 1
        i = 0
        while time.perf_counter() < end:
            asyncio.create_task(worker(i))
            i += 1
            issued += 1
            await asyncio.sleep(inter)
        await asyncio.sleep(min(5.0, duration))

    total = ok_count + err_count
    p50 = statistics.quantiles(latencies, n=100)[49] if latencies else 0.0
    p95 = statistics.quantiles(latencies, n=100)[94] if latencies else 0.0
    p99 = statistics.quantiles(latencies, n=100)[98] if latencies else 0.0
    print(f"issued={issued} total={total} ok={ok_count} err={err_count}")
    print(f"latency_p50={p50:.4f}s latency_p95={p95:.4f}s latency_p99={p99:.4f}s")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000", help="Base URL of API (ignored in --asgi mode)")
    p.add_argument("--duration", type=float, default=60.0)
    p.add_argument("--rps", type=float, default=100.0)
    p.add_argument("--concurrency", type=int, default=64)
    p.add_argument("--asgi", action="store_true", help="Use in-process ASGI app (no network)")
    return p.parse_args()


def main():
    args = parse_args()
    if args.asgi:
        asyncio.run(stress_asgi(args.duration, args.rps, args.concurrency))
    else:
        asyncio.run(stress(args.url, args.duration, args.rps, args.concurrency))


if __name__ == "__main__":
    main()

