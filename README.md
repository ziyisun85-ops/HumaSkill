# HumaSkill

HumaSkill is a three-layer harness built on top of GMT (General Motion Tracking) for executing long humanoid robot skill sequences in one continuous MuJoCo episode.

The first demo converts a fixed task sequence:

```text
walk_forward(10s) -> kick_leg -> crouch_down -> stand_up
```

into GMT reference segments, inserts runtime transition references between skills, tracks the full chain without resetting simulator state, and records segment-level execution results.

## Project Structure

```text
HumaSkill/
├── task_plan/              # YAML task sequence parsing and skill registry validation
├── middle_architecture/    # Motion loading, matching, transition building, orchestration
├── low_level_execution/    # Importable GMT tracking runner
├── configs/                # Harness, skills, transitions, and demo sequence configs
├── assets/motions/         # GMT motion pkl assets used by the demo
├── outputs/                # Contract docs, demo logs, and the comparison video
└── index.html              # GitHub Pages project page
```

## Demo

The static project page is available through `index.html` and is designed for GitHub Pages. It showcases the current harness result, including the generated comparison video at:

```text
outputs/demo_walk_kick_crouch_stand_comparison.mp4
```

## Run

Configure GMT in `configs/harness.yaml`, then run:

```bash
python scripts/run_harness_sequence.py
```

Run a single GMT motion through the harness:

```bash
python scripts/run_single_gmt_motion.py --motion walk_stand.pkl --duration 5.0
```

## Status

The first version is complete. The recorded demo summary reports:

```json
{
  "task_id": "demo_walk_kick_crouch_stand",
  "success": true,
  "num_segments": 7,
  "failed_segments": []
}
```

