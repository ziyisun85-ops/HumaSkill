from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from middle_architecture.canonical import CanonicalReference, CanonicalRobotState


@dataclass
class TrackerSpec:
    name: str
    tracker_type: str
    robot: str
    dof: int
    control_frequency_hz: float
    reference_type: str
    observation_type: str
    action_type: str
    action_dimension: int
    action_scale: float
    joint_order: str
    stiffness: List[float]
    damping: List[float]
    normalization: Dict[str, float]
    entry_conditions: Dict[str, Any]
    exit_conditions: Dict[str, Any]
    fallback_tracker: Optional[str] = None
    fallback_skill: Optional[str] = None


def _require(mapping: Dict[str, Any], key: str, yaml_path: Path) -> Any:
    if key not in mapping:
        raise ValueError(f"{yaml_path}: missing required key '{key}'")
    return mapping[key]


def load_tracker_spec(yaml_path: str) -> TrackerSpec:
    path = Path(yaml_path)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: tracker spec must be a mapping")

    pd_gains = _require(data, "pd_gains", path)
    if not isinstance(pd_gains, dict):
        raise ValueError(f"{path}: pd_gains must be a mapping")
    normalization = _require(data, "normalization", path)
    if not isinstance(normalization, dict):
        raise ValueError(f"{path}: normalization must be a mapping")
    fallback = data.get("fallback", {}) or {}
    if not isinstance(fallback, dict):
        raise ValueError(f"{path}: fallback must be a mapping")

    spec = TrackerSpec(
        name=str(_require(data, "name", path)),
        tracker_type=str(_require(data, "tracker_type", path)),
        robot=str(_require(data, "robot", path)),
        dof=int(_require(data, "dof", path)),
        control_frequency_hz=float(_require(data, "control_frequency_hz", path)),
        reference_type=str(_require(data, "reference_type", path)),
        observation_type=str(_require(data, "observation_type", path)),
        action_type=str(_require(data, "action_type", path)),
        action_dimension=int(_require(data, "action_dimension", path)),
        action_scale=float(_require(data, "action_scale", path)),
        joint_order=str(_require(data, "joint_order", path)),
        stiffness=[float(v) for v in _require(pd_gains, "stiffness", path)],
        damping=[float(v) for v in _require(pd_gains, "damping", path)],
        normalization={str(k): float(v) for k, v in normalization.items()},
        entry_conditions=dict(_require(data, "entry_conditions", path)),
        exit_conditions=dict(_require(data, "exit_conditions", path)),
        fallback_tracker=fallback.get("tracker"),
        fallback_skill=fallback.get("skill"),
    )
    validate_tracker_spec(spec, path)
    return spec


def validate_tracker_spec(spec: TrackerSpec, yaml_path: Path) -> None:
    if spec.dof <= 0:
        raise ValueError(f"{yaml_path}: dof must be positive")
    if spec.action_dimension != spec.dof:
        raise ValueError(f"{yaml_path}: action_dimension must equal dof for joint-position targets")
    if len(spec.stiffness) != spec.dof:
        raise ValueError(f"{yaml_path}: pd_gains.stiffness length must equal dof")
    if len(spec.damping) != spec.dof:
        raise ValueError(f"{yaml_path}: pd_gains.damping length must equal dof")
    if spec.reference_type != "kinematic_reference_frames":
        raise ValueError(f"{yaml_path}: unsupported reference_type {spec.reference_type}")
    if spec.action_type != "joint_position_target":
        raise ValueError(f"{yaml_path}: unsupported action_type {spec.action_type}")
    for key in ["ang_vel_scale", "dof_pos_scale", "dof_vel_scale"]:
        if key not in spec.normalization:
            raise ValueError(f"{yaml_path}: normalization missing {key}")


class TrackerAdapter(ABC):
    @abstractmethod
    def initialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_state(self) -> CanonicalRobotState:
        raise NotImplementedError

    @abstractmethod
    def track(self, reference: CanonicalReference, **kwargs: Any):
        raise NotImplementedError


class GMTTrackerAdapter(TrackerAdapter):
    def __init__(self, runner, spec: TrackerSpec) -> None:
        self.runner = runner
        self.spec = spec

    def initialize(self) -> None:
        self.runner.initialize()

    def get_state(self) -> CanonicalRobotState:
        return CanonicalRobotState.from_robot_state(self.runner.get_robot_state())

    def track(self, reference: CanonicalReference, **kwargs: Any):
        future = kwargs.pop("future_reference", None)
        future_reference_frames = kwargs.pop("future_reference_frames", None)
        if future is not None:
            if future_reference_frames is not None:
                raise ValueError("Pass only one of future_reference or future_reference_frames")
            future_reference_frames = future.to_reference_frames()
        return self.runner.track(
            reference.to_reference_frames(),
            future_reference_frames=future_reference_frames,
            **kwargs,
        )
