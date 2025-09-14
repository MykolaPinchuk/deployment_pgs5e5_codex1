#!/usr/bin/env python3
import argparse
import os
import sys
import pandas as pd


def main():
    root = os.getcwd()
    handout = os.path.join(root, 'handout_from DS_agent')
    src_train = os.path.join(handout, 'data_sample', 'train.csv')

    p = argparse.ArgumentParser()
    p.add_argument('--source', default=src_train, help='Path to full training CSV')
    p.add_argument('--out-dir', default=os.path.join(root, 'data', 'holdout'), help='Output directory')
    p.add_argument('--size', type=int, default=500, help='Number of rows for holdout set (from tail)')
    args = p.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    df = pd.read_csv(args.source)
    n = len(df)
    k = max(1, min(args.size, n - 1))
    holdout = df.tail(k).copy()
    train_wo = df.head(n - k).copy()

    # Save files with expected names for train.py
    train_path = os.path.join(args.out_dir, 'train.csv')
    holdout_path = os.path.join(args.out_dir, 'holdout.csv')
    train_wo.to_csv(train_path, index=False)
    holdout.to_csv(holdout_path, index=False)

    print(f'Wrote train (no holdout) to {train_path} ({len(train_wo)} rows)')
    print(f'Wrote holdout to {holdout_path} ({len(holdout)} rows)')


if __name__ == '__main__':
    main()

