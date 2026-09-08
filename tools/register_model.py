#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.cad.step_reader import load_step_model,model_readiness
p=argparse.ArgumentParser();p.add_argument('step');p.add_argument('--model-id',default='public_vehicle');p.add_argument('--version',default='V1');a=p.parse_args();m=load_step_model(a.step,model_id=a.model_id,version=a.version);print(json.dumps(model_readiness(m),ensure_ascii=False,indent=2));print('\nLEAF INVENTORY');[print(o.path,o.is_valid,o.bbox) for o in m.leaf_occurrences]
