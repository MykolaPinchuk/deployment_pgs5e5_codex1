import os
import importlib.util
import time
import pandas as pd


def load_app_module():
    root = os.getcwd()
    svc_path = os.path.join(root, 'service', 'app.py')
    spec = importlib.util.spec_from_file_location('service_app', svc_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_predict_and_feedback_direct():
    root = os.getcwd()
    handout = os.path.join(root, 'handout_from DS_agent')
    os.environ.setdefault('HANDOUT_DIR', handout)
    os.environ.setdefault('MODEL_PATH', os.path.join(handout, 'model.joblib'))

    mod = load_app_module()
    # Startup loads model
    mod._startup()

    # pick one record from train (OK for test; integration sim uses holdout)
    df = pd.read_csv(os.path.join(handout, 'data_sample', 'train.csv'))
    row = df.iloc[0]
    rec = {
        'id': int(row['id']),
        'Age': float(row['Age']),
        'Height': float(row['Height']),
        'Weight': float(row['Weight']),
        'Duration': float(row['Duration']),
        'Heart_Rate': float(row['Heart_Rate']),
        'Body_Temp': float(row['Body_Temp']),
        'Gender': str(row['Gender']) if 'Gender' in row else 'male',
    }

    out = mod.predict(mod.PredictRecord(**rec))
    assert out['id'] == rec['id']
    assert isinstance(out['Calories'], float)

    # Send feedback and check that metrics response exists
    mod.feedback(mod.FeedbackRecord(id=rec['id'], Calories=float(row['Calories']), ts=time.time()))
    resp = mod.metrics()
    assert hasattr(resp, 'body') and b'app_feedback_coverage_5m' in resp.body

