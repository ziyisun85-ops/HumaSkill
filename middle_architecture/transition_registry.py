from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import yaml


@dataclass
class TransitionSpec:
    from_skill: str
    to_skill: str
    mode: str
    num_frames: Optional[int] = None
    bridge_skill: Optional[str] = None
    pre_bridge_interp_frames: Optional[int] = None
    post_bridge_interp_frames: Optional[int] = None
    reason: str = ""
    interpolation_mode: str = "linear"
    hermite_tension: float = 1.0


class TransitionRegistry:
    def __init__(self, specs: Dict[Tuple[str, str], TransitionSpec]):
        self.specs = dict(specs)

    @staticmethod
    def from_yaml(yaml_path: str) -> "TransitionRegistry":
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        raw_specs = data.get("transitions") if isinstance(data, dict) else None
        if not isinstance(raw_specs, list):
            raise ValueError(f"Transition YAML must contain a transitions list: {yaml_path}")

        specs = {}
        for raw in raw_specs:
            spec = TransitionSpec(
                from_skill=str(raw["from_skill"]),
                to_skill=str(raw["to_skill"]),
                mode=str(raw["mode"]),
                num_frames=raw.get("num_frames"),
                bridge_skill=raw.get("bridge_skill"),
                pre_bridge_interp_frames=raw.get("pre_bridge_interp_frames"),
                post_bridge_interp_frames=raw.get("post_bridge_interp_frames"),
                reason=str(raw.get("reason", "")),
                interpolation_mode=str(raw.get("interpolation_mode", "linear")),
                hermite_tension=float(raw.get("hermite_tension", 1.0)),
            )
            for attr in ["num_frames", "pre_bridge_interp_frames", "post_bridge_interp_frames"]:
                value = getattr(spec, attr)
                if value is not None:
                    setattr(spec, attr, int(value))
            specs[(spec.from_skill, spec.to_skill)] = spec
        return TransitionRegistry(specs)

    def get(self, from_skill: str, to_skill: str) -> TransitionSpec:
        key = (from_skill, to_skill)
        if key not in self.specs:
            raise KeyError(
                f"Missing transition spec from {from_skill} to {to_skill}. "
                "Please add it to configs/transitions.yaml."
            )
        return self.specs[key]
