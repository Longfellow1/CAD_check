from __future__ import annotations

from copy import deepcopy
from .domain import Box, VehicleModel


def _base_objects() -> dict[str, Box]:
    objects = [
        Box(id="battery", label="动力电池包", center=(0,0,220), size=(1500,1100,120), category="power_battery"),
        Box(id="underbody_bracket", label="底部支架", center=(0,0,145), size=(500,800,20), category="body_bracket"),
        Box(id="left_rail", label="左纵梁", center=(0,650,300), size=(1700,90,160), category="body"),
        Box(id="right_rail", label="右纵梁", center=(0,-650,300), size=(1700,90,160), category="body"),
        Box(id="motor", label="前驱电机总成", center=(650,0,520), size=(520,480,420), rotation_deg=(0,0,0.8), category="powertrain"),
        Box(id="motor_bracket", label="电机支架", center=(650,295,520), size=(260,70,240), category="bracket"),
        Box(id="controller", label="电机控制器 MCU", center=(300,-360,610), size=(360,260,150), rotation_deg=(0,1.0,0), category="controller"),
        Box(id="controller_bracket", label="MCU支架", center=(300,-515,610), size=(300,40,180), category="bracket"),
        Box(id="exhaust", label="高温排气区域", center=(720,480,450), size=(600,180,180), category="heat_source"),
        Box(id="front_crossmember", label="前横梁", center=(1020,0,330), size=(130,1150,120), category="body"),
        Box(id="ground_ref", label="地面基准", center=(0,0,0), size=(2800,1700,10), category="reference"),
        Box(id="rear_module", label="后电驱模块", center=(-800,0,420), size=(460,420,300), rotation_deg=(0,0.6,0), category="powertrain"),
    ]
    return {o.id:o for o in objects}


def model_v1() -> VehicleModel:
    return VehicleModel(model_id="demo_vehicle", version="V1", description="Controlled baseline fixture", objects=_base_objects())


def model_v2() -> VehicleModel:
    objs=deepcopy(_base_objects())
    objs["battery"].center=(0,0,205)
    objs["controller"].center=(300,-375,610)
    objs["motor"].center=(680,0,520)
    objs["motor"].rotation_deg=(0,0,2.2)
    objs["rear_module"].rotation_deg=(0,0.1,0)
    return VehicleModel(model_id="demo_vehicle", version="V2", description="Controlled candidate fixture", objects=objs)


def all_models():
    return {"V1":model_v1(),"V2":model_v2()}
