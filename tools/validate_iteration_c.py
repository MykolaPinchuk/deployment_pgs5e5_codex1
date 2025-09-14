import os
import importlib.util
from pathlib import Path


def main():
    root = Path.cwd()
    handout = root / 'handout_from DS_agent'
    os.environ.setdefault('HANDOUT_DIR', str(handout))
    os.environ.setdefault('MODEL_PATH', str(handout / 'model.joblib'))
    # Import service app
    spec = importlib.util.spec_from_file_location('service_app', str(root / 'service' / 'app.py'))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    # Startup and call info
    module._startup()
    info = module.info()
    print('INFO keys:', sorted(info.keys()))
    print('Model path:', info.get('model', {}).get('path'))
    print('MLFLOW_TRACKING_URI:', info.get('env', {}).get('MLFLOW_TRACKING_URI'))


if __name__ == '__main__':
    main()

