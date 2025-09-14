import os
import sys
import time
import traceback
import logging
import pandas as pd
from fastapi.testclient import TestClient  # unused in direct mode but kept for reference


def main():
    root = os.getcwd()
    os.makedirs('logs', exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s %(message)s',
        handlers=[
            logging.FileHandler('logs/validate_iteration_a.log', mode='w'),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.info('Starting Iteration A validation')
    handout = os.path.join(root, 'handout_from DS_agent')
    os.environ.setdefault('HANDOUT_DIR', handout)
    os.environ.setdefault('MODEL_PATH', os.path.join(handout, 'model.joblib'))

    # Import the FastAPI app from file path (avoid package import issues)
    import importlib.util
    svc_path = os.path.join(root, 'service', 'app.py')
    spec = importlib.util.spec_from_file_location('service_app', svc_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    logging.info('Importing service.app from %s', svc_path)
    spec.loader.exec_module(module)
    app = module.app
    logging.info('Imported FastAPI app')

    train_csv = os.path.join(handout, 'data_sample', 'train.csv')
    df = pd.read_csv(train_csv)
    row = df.iloc[0]
    rec = {
        'id': int(row['id']),
        'Age': float(row['Age']),
        'Height': float(row['Height']),
        'Weight': float(row['Weight']),
        'Duration': float(row['Duration']),
        'Heart_Rate': float(row['Heart_Rate']),
        'Body_Temp': float(row['Body_Temp']),
    }
    if 'Gender' in row:
        rec['Gender'] = str(row['Gender'])
    elif 'Sex' in row:
        rec['Sex'] = str(row['Sex'])
    else:
        rec['Gender'] = 'male'

    # Safety timeout gate
    t_start = time.time()
    def check_timeout():
        if time.time() - t_start > 20:
            raise SystemExit("Validation timeout exceeded (20s)")

    logging.info('Creating TestClient')
    # Direct in-process validation to avoid TestClient lifespan hangs in restricted sandboxes
    try:
        logging.info('Calling _startup() directly')
        module._startup()
        check_timeout()
        logging.info('healthz()')
        hz = module.healthz()
        logging.info('healthz: %s', hz)
        check_timeout()
        logging.info('predict()')
        pr = module.PredictRecord(**rec)
        out = module.predict(pr)
        logging.info('predict: %s', out)
        check_timeout()
        logging.info('feedback()')
        module.feedback(module.FeedbackRecord(id=rec['id'], Calories=float(row['Calories']), ts=time.time()))
        check_timeout()
        logging.info('metrics()')
        resp = module.metrics()
        # Response has body in .body (bytes)
        text = resp.body.decode('utf-8', errors='replace')
        lines = [ln for ln in text.splitlines() if ln.startswith('app_rolling') or ln.startswith('app_feedback_coverage_5m')]
        logging.info('metrics sample:\n%s', '\n'.join(lines[:10]))
    except Exception:
        logging.error('Validation raised exception:\n%s', traceback.format_exc())
        raise
    finally:
        logging.info('Validation complete')


if __name__ == '__main__':
    main()
