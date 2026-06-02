# Task 09B: Add Single-Viewer HumaSkill Sequence Playback

You are working on the local HumaSkill project.

Project path:

```powershell
G:\Code\Python\HumaSkill
```

## Current problem

`motion_clip_mujoco` viewer mode currently opens a separate MuJoCo viewer window for each skill, because `MotionClipMujocoBackend.execute()` is called once per skill.

Current behavior:

```text
stand_ready opens one viewer
arm_wave opens another viewer
final_pose opens another viewer
```

Desired behavior:

```text
Open one MuJoCo viewer window once
Play the whole HumaSkill skill sequence continuously
Close the viewer after the sequence finishes
```

## Goal

Create a standalone demo script for single-window sequence playback.

Do not redesign the backend yet.  
Do not modify SkillExecutor unless necessary.  
Do not implement actuator control.  
Do not integrate TextOp.

This task should focus on a clean visual demo.

## Files to create or modify

Create:

```text
scripts/view_humaskill_sequence_in_mujoco.py
```

You may minimally modify:

```text
README.md
```

Do not modify core HumaSkill logic unless absolutely necessary.

## Required behavior

The script should accept:

```powershell
python scripts/view_humaskill_sequence_in_mujoco.py --text "跳一段舞" --duration 8 --fps 30
```

Optional args:

```text
--loop
--max-frames
--output-sequence
```

The script should:

```text
1. Use the existing HumaSkill composer and transition logic to generate a skill sequence from text.
2. Map each skill to an existing qpos clip.
3. Load model/g1_description/g1_23dof.xml.
4. Open one MuJoCo viewer window.
5. Play all available qpos clips in sequence inside the same viewer.
6. Skip skills that do not have qpos clips, but print a clear warning.
7. Print the final played skill list.
```

## Clip mapping

Use this mapping first:

```text
stand_ready -> motions/stand_ready_qpos.npy
arm_wave -> motions/arm_wave_qpos.npy
final_pose -> motions/final_pose_qpos.npy
```

If a skill has no clip, skip it and print:

```text
[WARN] Missing qpos clip for skill: <skill_name>
```

## Playback logic

Use qpos playback:

```python
data.qpos[:] = motion[t]
mujoco.mj_forward(model, data)
viewer.sync()
```

Use one viewer:

```python
with mujoco.viewer.launch_passive(model, data) as viewer:
    play stand_ready
    play arm_wave
    play final_pose
```

If `--loop` is enabled, repeat the full sequence until the viewer is closed.

Handle `KeyboardInterrupt` gracefully.

## Output sequence

If `--output-sequence` is provided, save the generated and actually played sequence to JSON.

Example:

```powershell
python scripts/view_humaskill_sequence_in_mujoco.py --text "跳一段舞" --duration 8 --fps 30 --output-sequence logs/sequence_viewer_demo.json
```

The JSON should include:

```json
{
  "text": "...",
  "duration": 8,
  "generated_sequence": [...],
  "played_sequence": [...],
  "skipped_skills": [...]
}
```

## Important note

If the current composer output for `"跳一段舞"` does not include `arm_wave`, add a minimal composer fix so that dance-related text such as:

```text
舞
跳舞
dance
```

generates at least:

```text
stand_ready
arm_wave
final_pose
```

If you modify the composer, add or update tests.

## Tests

Add or update tests only if they can run without opening a viewer.

Possible tests:

```text
The script imports successfully.
The skill-to-clip mapping finds existing clips.
The generated dance sequence includes arm_wave.
Missing clips are skipped rather than crashing.
```

Do not open the viewer in pytest.

## Commands to run

Run:

```powershell
python -m py_compile scripts/view_humaskill_sequence_in_mujoco.py
python -m pytest -q
```

Manual viewer command:

```powershell
python scripts/view_humaskill_sequence_in_mujoco.py --text "跳一段舞" --duration 8 --fps 30 --output-sequence logs/sequence_viewer_demo.json
```

## Final report

Report:

```text
Task 09B status:
Files created or modified:
Commands run:
Generated sequence:
Played sequence:
Skipped skills:
Viewer command:
Remaining issues:
Recommended next step:
```