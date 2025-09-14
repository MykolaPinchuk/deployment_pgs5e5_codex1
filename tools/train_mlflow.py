#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import mlflow
import yaml


def main():
    root = Path(os.getcwd())
    handout = root / 'handout_from DS_agent'
    cfg_path = handout / 'config.yaml'
    model_path = handout / 'model.joblib'
    metrics_path = handout / 'metrics.json'

    p = argparse.ArgumentParser()
    p.add_argument('--run-name', default='local-train')
    p.add_argument('--tracking-uri', default=os.environ.get('MLFLOW_TRACKING_URI', 'http://127.0.0.1:5000'))
    p.add_argument('--register', action='store_true', help='Register model in MLflow registry')
    p.add_argument('--model-name', default='CaloriesPredictor')
    args = p.parse_args()

    mlflow.set_tracking_uri(args.tracking_uri)

    # Load params from config
    params = {}
    if cfg_path.exists():
        with open(cfg_path, 'r') as f:
            cfg = yaml.safe_load(f)
        # flatten
        for k, v in cfg.items():
            if isinstance(v, dict):
                for k2, v2 in v.items():
                    params[f'{k}.{k2}'] = v2
            else:
                params[k] = v

    with mlflow.start_run(run_name=args.run_name) as run:
        run_id = run.info.run_id
        # Print artifact URI to verify server-side artifact service
        try:
            art_uri = mlflow.get_artifact_uri()
            print(f"Artifact URI: {art_uri}")
            if art_uri.startswith('file:'):
                print("WARNING: Artifact URI is local file. Ensure MLflow server is started with --serve-artifacts and that you're using the HTTP tracking URI.")
        except Exception as e:
            print(f"Could not determine artifact URI: {e}")
        # log params
        if params:
            mlflow.log_params(params)

        # Run training script as a subprocess
        cmd = [sys.executable, str(handout / 'train.py')]
        print('Running:', ' '.join(cmd), flush=True)
        t0 = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        dt = time.time() - t0
        print(proc.stdout)
        if proc.returncode != 0:
            print(proc.stderr, file=sys.stderr)
            raise SystemExit(f'Training failed with code {proc.returncode}')
        mlflow.log_metric('train_wall_time_sec', dt)

        # Log metrics
        if metrics_path.exists():
            with open(metrics_path, 'r') as f:
                m = json.load(f)
            for k, v in m.items():
                if isinstance(v, (int, float)):
                    mlflow.log_metric(k, float(v))

        # Log artifacts
        if model_path.exists():
            mlflow.log_artifact(str(model_path), artifact_path='model')
        if cfg_path.exists():
            mlflow.log_artifact(str(cfg_path), artifact_path='config')
        if metrics_path.exists():
            mlflow.log_artifact(str(metrics_path), artifact_path='metrics')

        # Optionally register the model
        if args.register and model_path.exists():
            uri = f'runs:/{run_id}/model/model.joblib'
            try:
                mlflow.register_model(uri, args.model_name)
            except Exception as e:
                print(f'Registration failed: {e}', file=sys.stderr)

    print('MLflow run completed:', run_id)


if __name__ == '__main__':
    main()
