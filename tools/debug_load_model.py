import os
import sys
import time
import joblib

def main():
    root = os.getcwd()
    handout = os.path.join(root, 'handout_from DS_agent')
    path = os.path.join(handout, 'model.joblib')
    if handout not in sys.path:
        sys.path.insert(0, handout)
    t0 = time.time()
    print('DEBUG: loading model from', path, flush=True)
    m = joblib.load(path)
    dt = time.time() - t0
    print('DEBUG: loaded type=', type(m), 'in', f'{dt:.3f}s', flush=True)

if __name__ == '__main__':
    main()
