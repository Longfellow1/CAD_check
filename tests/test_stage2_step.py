from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server.cases import CASES
from server.stage2_runtime import Stage2Workspace

def ensure():
 if not (ROOT/'data/step/vehicle_v1.step').exists(): subprocess.run([sys.executable,'tools/generate_step_fixture.py'],cwd=ROOT,check=True)

def test_real_step_import_binding_occt_regression_and_trace():
 ensure();ws=Stage2Workspace(ROOT).load_manifest(ROOT/'models/demo_manifest.yaml');assert ws.readiness('V1')['bindings']['valid'];r=ws.run_regression('V1','V2');assert len(r['regression'])==len(CASES);assert (Path(r['run_dir'])/'trace.jsonl').exists();assert any(x.case_id=='CLR_BAT_BRACKET' and x.candidate.value is not None for x in r['regression'])

def test_ocp_tessellate_bridge():
 ensure();ws=Stage2Workspace(ROOT).load_manifest(ROOT/'models/demo_manifest.yaml');p=ws.viewer_payload('V1',['battery','underbody_bracket']);assert 'shapes' in p
