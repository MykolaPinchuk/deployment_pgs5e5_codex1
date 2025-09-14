#!/usr/bin/env python3
import argparse
import asyncio
import os
import time
from typing import Optional

import httpx
import pandas as pd


def parse_args():
    here = os.path.dirname(__file__)
    root = os.path.abspath(os.path.join(here, os.pardir))
    handout_dir = os.path.join(root, "handout_from DS_agent")
    # Default to derived holdout set outside the handout dir
    default_data = os.path.join(root, "data", "holdout", "holdout.csv")
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--data", default=default_data)
    p.add_argument("--limit", type=int, default=200, help="Max records to send (0=all)")
    p.add_argument("--feedback-delay", type=float, default=300.0, help="Seconds until feedback is sent")
    p.add_argument("--cycles", type=int, default=2, help="Number of burst cycles")
    p.add_argument("--burst-rps", type=float, default=20.0, help="Requests per second during burst")
    p.add_argument("--burst-duration", type=float, default=5.0, help="Seconds per burst active period")
    p.add_argument("--idle-duration", type=float, default=25.0, help="Seconds per idle period between bursts")
    return p.parse_args()


def row_to_payload(row: pd.Series) -> dict:
    # Align with SCHEMA.md; allow Gender or Sex
    payload = {
        "id": int(row.get("id")),
        "Age": float(row.get("Age")),
        "Height": float(row.get("Height")),
        "Weight": float(row.get("Weight")),
        "Duration": float(row.get("Duration")),
        "Heart_Rate": float(row.get("Heart_Rate")),
        "Body_Temp": float(row.get("Body_Temp")),
    }
    if "Gender" in row and not pd.isna(row["Gender"]):
        payload["Gender"] = str(row["Gender"])
    elif "Sex" in row and not pd.isna(row["Sex"]):
        payload["Sex"] = str(row["Sex"])
    else:
        payload["Gender"] = "male"
    return payload


async def send_predict(client: httpx.AsyncClient, base_url: str, payload: dict) -> Optional[float]:
    try:
        r = await client.post(f"{base_url}/predict", json=payload, timeout=10.0)
        r.raise_for_status()
        return float(r.json()["Calories"])
    except Exception as e:
        print(f"predict error for id={payload.get('id')}: {e}")
        return None


async def send_feedback(client: httpx.AsyncClient, base_url: str, rec_id: int, calories: float, ts_true: Optional[float] = None):
    body = {"id": int(rec_id), "Calories": float(calories)}
    if ts_true is not None:
        body["ts"] = float(ts_true)
    try:
        r = await client.post(f"{base_url}/feedback", json=body, timeout=10.0)
        r.raise_for_status()
    except Exception as e:
        print(f"feedback error for id={rec_id}: {e}")


async def burst_cycle(client: httpx.AsyncClient, base_url: str, df: pd.DataFrame, start_idx: int, n_records: int, rps: float, duration: float, feedback_delay: float):
    inter_arrival = 1.0 / max(0.1, rps)
    sent = 0
    t0 = time.time()
    while sent < n_records and (time.time() - t0) < duration:
        idx = start_idx + sent
        if idx >= len(df):
            break
        row = df.iloc[idx]
        payload = row_to_payload(row)
        y_true = float(row.get("Calories")) if "Calories" in row else None
        # Fire prediction
        asyncio.create_task(send_predict(client, base_url, payload))
        # Schedule feedback after delay (use true timestamp of now+delay)
        if y_true is not None:
            async def _schedule_feedback(rid: int, yt: float):
                await asyncio.sleep(feedback_delay)
                await send_feedback(client, base_url, rid, yt, ts_true=time.time())
            asyncio.create_task(_schedule_feedback(int(payload["id"]), y_true))

        sent += 1
        await asyncio.sleep(inter_arrival)
    return sent


async def main_async():
    args = parse_args()
    if not os.path.exists(args.data):
        raise SystemExit(f"Simulator data not found at {args.data}. Generate holdout via: make holdout")
    df = pd.read_csv(args.data)
    if args.limit > 0:
        df = df.iloc[: args.limit].copy()
    total = len(df)
    base_url = args.url.rstrip("/")

    async with httpx.AsyncClient() as client:
        idx = 0
        per_burst = int(args.burst_rps * args.burst_duration)
        for c in range(args.cycles):
            if idx >= total:
                break
            n = min(per_burst, total - idx)
            print(f"cycle {c+1}/{args.cycles}: burst sending {n} records @ {args.burst_rps} rps for {args.burst_duration}s")
            sent = await burst_cycle(client, base_url, df, idx, n, args.burst_rps, args.burst_duration, args.feedback_delay)
            idx += sent
            if idx >= total:
                break
            idle = args.idle_duration
            print(f"cycle {c+1}: idle for {idle}s")
            await asyncio.sleep(idle)
        # Wait a short grace period for outstanding feedback tasks (not full delay)
        print("simulation complete; waiting 2s for in-flight tasks")
        await asyncio.sleep(2.0)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
