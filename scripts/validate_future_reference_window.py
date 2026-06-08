from pathlib import Path
import sys

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from low_level_execution.gmt_tracking_runner import GMTTrackingRunner, _ReferenceSampler
from middle_architecture.robot_state import ReferenceFrames


def _constant_reference(root_height: float, dof_value: float) -> ReferenceFrames:
    num_frames = 4
    root_pos = np.zeros((num_frames, 3), dtype=np.float32)
    root_pos[:, 2] = root_height
    root_rot = np.tile(
        np.array([[0.0, 0.0, 0.0, 1.0]], dtype=np.float32),
        (num_frames, 1),
    )
    dof_pos = np.full((num_frames, 23), dof_value, dtype=np.float32)
    return ReferenceFrames(
        fps=10.0,
        root_pos=root_pos,
        root_rot=root_rot,
        dof_pos=dof_pos,
    )


def main() -> None:
    current = _ReferenceSampler(_constant_reference(root_height=1.0, dof_value=0.1))
    next_ref = _ReferenceSampler(_constant_reference(root_height=2.0, dof_value=0.9))

    runner = GMTTrackingRunner(gmt_root="unused", robot="g1")
    runner.control_dt = 0.1
    runner.tar_obs_steps = np.array([4], dtype=np.int32)

    obs = runner._get_mimic_obs(current, control_step=0, future_sampler=next_ref)
    root_height = float(obs[0])
    first_dof = float(obs[7])

    if abs(root_height - 2.0) > 1e-6:
        raise AssertionError(
            f"future window wrapped to current segment height {root_height}, expected next segment"
        )
    if abs(first_dof - 0.9) > 1e-6:
        raise AssertionError(
            f"future window wrapped to current segment dof {first_dof}, expected next segment"
        )

    print("future reference window crosses segment boundary without wrapping")


if __name__ == "__main__":
    main()
