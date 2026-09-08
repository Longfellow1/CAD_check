#!/usr/bin/env python3
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.stage2_runtime import Stage2Workspace
if __name__=='__main__':
 ws=Stage2Workspace(ROOT).load_manifest(ROOT/'models/demo_manifest.yaml')
 for k in ('V1','V2'): print(k,json.dumps(ws.readiness(k),ensure_ascii=False,indent=2))
 print('PAIR',json.dumps(ws.pair_readiness('V1','V2'),ensure_ascii=False,indent=2))
