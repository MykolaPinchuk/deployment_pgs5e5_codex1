import os
import sys
import time
import importlib.util

def main():
    root = os.getcwd()
    svc_path = os.path.join(root, 'service', 'app.py')
    spec = importlib.util.spec_from_file_location('service_app', svc_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    print('Imported app module')
    print('HANDOUT_DIR=', mod.HANDOUT_DIR)
    print('MODEL_PATH=', mod.MODEL_PATH)
    print('sys.path has handout?', mod.HANDOUT_DIR in sys.path)
    print('Calling _startup()...')
    t0 = time.time()
    mod._startup()
    print('Startup done in', f'{time.time()-t0:.3f}s')
    print('model is None?', mod.model is None)

if __name__ == '__main__':
    main()

