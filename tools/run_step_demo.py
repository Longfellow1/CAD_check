#!/usr/bin/env python3
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.stage2_runtime import Stage2Workspace
if __name__=='__main__':
 ws=Stage2Workspace(ROOT).load_manifest(ROOT/'models/demo_manifest.yaml');r=ws.run_regression('V1','V2');print('run_id=',r['run_id']);print('run_dir=',r['run_dir'])
 for x in r['regression']: print(f'{x.case_id:24} {x.regression.value:16} {x.baseline.value!s:>8} -> {x.candidate.value!s:>8}')
