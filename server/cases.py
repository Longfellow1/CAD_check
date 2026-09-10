from __future__ import annotations

from .domain import Rule, RuleAuthority, VerificationCase


def _c(id, title, source_ref, executor, target, counterpart=None, axis=None, angle_axis=None,
       operator=">=", threshold=None, lower=None, upper=None, unit="mm", epsilon=0.5, note=""):
    return VerificationCase(
        id=id, title=title, source="Sanitized DR500-style engineering rule", source_ref=source_ref,
        executor=executor, target=target, counterpart=counterpart, axis=axis, angle_axis=angle_axis,
        rule=Rule(operator=operator, threshold=threshold, lower=lower, upper=upper, unit=unit, authority=RuleAuthority.FORMAL),
        regression_epsilon=epsilon, note=note,
    )


CASES = [
    _c("CLR_BAT_BRACKET", "动力电池包至底部支架间隙", "demo-001", "minimum_clearance", "battery", "underbody_bracket", threshold=10),
    _c("CLR_BAT_LEFT_RAIL", "动力电池包至左纵梁间隙", "demo-002", "minimum_clearance", "battery", "left_rail", threshold=10),
    _c("CLR_BAT_RIGHT_RAIL", "动力电池包至右纵梁间隙", "demo-003", "minimum_clearance", "battery", "right_rail", threshold=10),
    _c("CLR_MOTOR_BRACKET", "电机总成至电机支架间隙", "demo-004", "minimum_clearance", "motor", "motor_bracket", threshold=5),
    _c("CLR_MOTOR_FRONT", "动力系统至前横梁间隙", "demo-005", "minimum_clearance", "motor", "front_crossmember", threshold=25),
    _c("CLR_MOTOR_EXHAUST", "动力系统至高温排气区域间隙", "demo-006", "minimum_clearance", "motor", "exhaust", threshold=50),
    _c("CLR_MCU_BRACKET", "MCU至固定支架间隙", "demo-007", "minimum_clearance", "controller", "controller_bracket", threshold=10),
    _c("CLR_MCU_MOTOR", "MCU至相对运动动力系统间隙", "demo-008", "minimum_clearance", "controller", "motor", threshold=25),
    _c("CLR_REAR_LEFT_RAIL", "后电驱模块至左侧结构间隙", "demo-009", "minimum_clearance", "rear_module", "left_rail", threshold=20),
    _c("CLR_REAR_RIGHT_RAIL", "后电驱模块至右侧结构间隙", "demo-010", "minimum_clearance", "rear_module", "right_rail", threshold=20),
    _c("DIR_BAT_GROUND", "动力电池包Z向最小离地间隙", "demo-011", "directional_distance", "battery", "ground_ref", axis="Z", threshold=130),
    _c("DIR_MOTOR_GROUND", "动力系统Z向离地间隙", "demo-012", "directional_distance", "motor", "ground_ref", axis="Z", threshold=160),
    _c("DIR_MOTOR_FRONT_X", "动力系统至前横梁X向间隙", "demo-013", "directional_distance", "motor", "front_crossmember", axis="X", threshold=30),
    _c("DIR_MCU_RAIL_Y", "MCU至右纵梁Y向间隙", "demo-014", "directional_distance", "controller", "right_rail", axis="Y", threshold=18),
    _c("DIR_BAT_RAIL_Y", "电池包至左纵梁Y向间隙", "demo-015", "directional_distance", "battery", "left_rail", axis="Y", threshold=10),
    _c("ANG_MOTOR_YAW", "动力总成Z轴布置角偏差", "demo-016", "angle", "motor", angle_axis="Z", operator="<=", threshold=2.0, unit="deg", epsilon=0.1),
    _c("ANG_MCU_PITCH", "MCU Y轴布置角偏差", "demo-017", "angle", "controller", angle_axis="Y", operator="<=", threshold=2.0, unit="deg", epsilon=0.1),
    _c("ANG_REAR_PITCH", "后电驱模块Y轴布置角偏差", "demo-018", "angle", "rear_module", angle_axis="Y", operator="<=", threshold=0.5, unit="deg", epsilon=0.1),
]
