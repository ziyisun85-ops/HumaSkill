import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from low_level_execution.gmt_tracking_runner import GMTTrackingRunner


def main() -> None:
    local_model = Path("assets/robots/g1/g1.xml")
    assert local_model.exists(), f"local G1 model missing: {local_model}"

    with Path("configs/harness.yaml").open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    assert config["gmt"]["model_path"] == str(local_model).replace("\\", "/")

    runner = GMTTrackingRunner(
        gmt_root=config["gmt"]["root"],
        robot=config["gmt"].get("robot", "g1"),
        model_path=config["gmt"]["model_path"],
    )
    assert runner.model_path == local_model

    resolved = runner._resolve_model_path()
    assert resolved == local_model.resolve()
    assert resolved.exists()

    import mujoco

    model = mujoco.MjModel.from_xml_path(str(resolved))
    assert model.nq == 30
    assert model.nv == 29
    assert model.nu == 23


if __name__ == "__main__":
    main()

