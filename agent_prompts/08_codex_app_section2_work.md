# Task 07: From G1 Motion Data to Minimal MuJoCo Motion Test

You are working on the local HumaSkill project.

Project path:

```powershell
G:\Code\Python\HumaSkill
```

This task is the next stage after the HumaSkill MVP.

The current HumaSkill MVP already supports:

```text
Language input
↓
Skill sequence generation
↓
Transition repair
↓
DummyBackend execution
↓
ExecutionResult and logs
```

Now we want to move one step beyond DummyBackend toward real MuJoCo simulation.

The goal of this task is:

```text
Inspect downloaded G1 motion data
↓
Understand what is stored inside the .pkl files
↓
Convert usable motion trajectories into HumaSkill-readable .npy clips
↓
Load the Unitree G1 MuJoCo model
↓
Check whether the .npy trajectory dimensions are compatible with the MuJoCo model
```

This task is only about data inspection, format conversion, and minimal MuJoCo testing.

Do not integrate TextOp in this task.  
Do not implement online motion generation.  
Do not train any model.  
Do not implement the full HumaSkill backend yet.  
Do not modify core HumaSkill framework logic.

---

## 1. Current Project State

HumaSkill MVP is complete and has passed:

```text
validate_skills.py
pytest
DummyBackend demo
Codex App final review
```

Existing local resources:

```text
Unitree G1 MuJoCo model:
model/unitree_g1/

Potential MuJoCo XML files:
model/unitree_g1/g1.xml
model/unitree_g1/g1_with_hands.xml
model/unitree_g1/scene.xml
model/unitree_g1/scene_table.xml

Downloaded G1 motion data:
data/g1-retargeted-motions/
```

The downloaded motion data appears to mainly contain `.pkl` files.

Your job is to inspect these `.pkl` files and export a small number of `.npy` motion clips for later use by MotionClipMujocoBackend.

---

## 2. What This Task Must Not Do

Do not do the following in this task:

```text
Do not integrate TextOp.
Do not implement online motion generation.
Do not train any model.
Do not implement the full HumaSkill backend.
Do not modify core HumaSkill framework logic.
Do not commit large data files.
```

Only make very small compatibility changes if they are clearly necessary.

---

## 3. Files to Read First

Before editing, read:

```text
PROJECT_PLAN.md
INTERFACES.md
README.md
ACCEPTANCE_CHECKLIST.md
```

Pay special attention to:

```text
ExecutionResult
Backend interface
MotionClipBackend placeholder
MujocoGymBackend placeholder
SkillInfo
```

---

## 4. Files You May Create or Edit

You may create:

```text
scripts/inspect_g1_pkl.py
scripts/convert_g1_pkl_to_npy.py
scripts/test_g1_motion_in_mujoco.py

configs/robot_g1_mujoco.yaml

tests/test_g1_motion_data.py
tests/test_g1_mujoco_smoke.py

motions/.gitkeep
motions/metadata.json
```

You may generate local motion files:

```text
motions/*.npy
```

You may minimally edit:

```text
requirements.txt
.gitignore
README.md
```

Do not modify core logic under:

```text
humaskill/main.py
humaskill/harness/
humaskill/composer/
humaskill/skills/
humaskill/backends/
```

If a tiny fix is absolutely necessary, explain why first and keep the patch minimal.

---

## 5. Step 1: Inspect G1 `.pkl` Data

Create:

```text
scripts/inspect_g1_pkl.py
```

The script must:

```text
Recursively search data/g1-retargeted-motions/ for .pkl files.
Print the total number of .pkl files.
Print the first 50 .pkl file paths.
Inspect the first 10 .pkl files.
```

For each inspected `.pkl` file, print:

```text
File path
Python object type
Dictionary keys if the object is a dict
For array-like values, print field name, type, shape, and dtype
For 2D arrays, print a short preview of the first row
For list, tuple, or nested dict objects, print a concise structure summary
```

The script must not crash just because one file has an unexpected structure.  
For unknown structures, print the type and a short repr preview.

Run:

```powershell
python scripts/inspect_g1_pkl.py
```

After running, summarize:

```text
How many .pkl files were found
Which fields look like motion trajectories
Which fields look like metadata
Which files are good first conversion candidates
```

Look for field names similar to:

```text
dof_pos
joint_pos
joint_positions
qpos
pose
motion
root_pos
root_rot
fps
```

---

## 6. Step 2: Create a G1 MuJoCo Config

Create:

```text
configs/robot_g1_mujoco.yaml
```

It must contain at least:

```yaml
robot_name: unitree_g1
model_dir: model/unitree_g1
model_path: model/unitree_g1/scene.xml
preferred_xml:
  - model/unitree_g1/scene.xml
  - model/unitree_g1/g1.xml
  - model/unitree_g1/g1_with_hands.xml
  - model/unitree_g1/scene_table.xml
motion_dir: motions
motion_fps: 30
control_mode: qpos_playback
notes: "Initial config for inspecting and testing G1 motion clips in MuJoCo."
```

If `scene.xml` cannot be loaded by MuJoCo, try the other XML files and record which one works in the final report.

---

## 7. Step 3: Convert a Small Number of `.pkl` Motions to `.npy`

Create:

```text
scripts/convert_g1_pkl_to_npy.py
```

The script must:

```text
Read .pkl files under data/g1-retargeted-motions/.
Use the inspection result from Step 1 to select the most likely motion trajectory field.
Export a small number of .npy files under motions/.
Create motions/metadata.json.
```

Keep the first conversion small. The first target clips should be:

```text
stand_ready.npy
arm_wave.npy
final_pose.npy
```

If the dataset file names do not clearly match these skills, choose the closest available motions and document the mapping in `metadata.json`.

Example `metadata.json` format:

```json
{
  "motions": [
    {
      "skill": "arm_wave",
      "source_file": "data/g1-retargeted-motions/example.pkl",
      "output_file": "motions/arm_wave.npy",
      "field": "dof_pos",
      "shape": [120, 29],
      "dtype": "float32",
      "fps": 30,
      "notes": "Selected as a first usable motion clip."
    }
  ]
}
```

After running, the script must print:

```text
Number of converted motions
Source .pkl file for each motion
Selected field name
Output .npy file
Shape and dtype of each .npy file
```

Run:

```powershell
python scripts/convert_g1_pkl_to_npy.py
```

---

## 8. Step 4: Minimal MuJoCo Load and Motion Dimension Test

Create:

```text
scripts/test_g1_motion_in_mujoco.py
```

This is a minimal test script, not a full backend.

The script must:

```text
Read configs/robot_g1_mujoco.yaml.
Load the MuJoCo XML model.
Print model information.
Load one .npy motion clip from motions/.
Print motion shape and dtype.
Check whether the motion dimension is likely compatible with the MuJoCo model.
```

Print this MuJoCo model information:

```text
nq
nv
nu
number of joints
number of actuators
XML path used
```

Dimension compatibility rules:

```text
If the last motion dimension equals nq, report compatible_with_qpos.
If the last motion dimension equals nu, report compatible_with_action.
Otherwise, report incompatible_dimension.
```

If MuJoCo is not installed, the script must clearly print:

```text
MuJoCo is not installed. Install with: python -m pip install mujoco
```

If MuJoCo is installed, run:

```powershell
python scripts/test_g1_motion_in_mujoco.py
```

Requirements:

```text
Do not open a viewer.
Do not render.
Do not require GPU.
Only load the model, load the motion, and check dimensions.
If the dimension matches qpos or actuator dimension, optionally step 10 to 30 simulation steps to verify that MuJoCo does not crash.
```

---

## 9. Tests to Add

Create:

```text
tests/test_g1_motion_data.py
tests/test_g1_mujoco_smoke.py
```

### 9.1 tests/test_g1_motion_data.py

Must test:

```text
data/g1-retargeted-motions/ exists.
At least one .pkl file exists.
scripts/convert_g1_pkl_to_npy.py can generate motions/metadata.json.
metadata.json contains at least one motion entry.
The .npy files recorded in metadata exist.
Generated .npy files are 2D arrays.
```

### 9.2 tests/test_g1_mujoco_smoke.py

Must test:

```text
configs/robot_g1_mujoco.yaml exists.
The configured model_path exists.
motions/metadata.json exists.
scripts/test_g1_motion_in_mujoco.py can run far enough to print model and motion information.
```

If MuJoCo is not installed, use `pytest.skip` instead of failing.

---

## 10. Dependency Rules

If MuJoCo is needed, prefer this package:

```text
mujoco
```

If the current environment does not have MuJoCo and the script/test requires it, you may add it to:

```text
requirements.txt
```

Do not add large machine learning dependencies.  
Do not add TextOp dependencies.  
Do not add torch unless the `.pkl` files truly require torch to load.  
If torch is required to read the `.pkl` files, report that first instead of making a large environment change.

---

## 11. Git Ignore Rules

Ensure `.gitignore` contains:

```gitignore
data/
motions/
*.pkl
*.npz
*.npy
*.fbx
*.bvh
```

Do not remove these rules.

Generated `.npy` files, downloaded data, and large files must not be committed.

---

## 12. Final Validation Commands

Run:

```powershell
python scripts/inspect_g1_pkl.py
python scripts/convert_g1_pkl_to_npy.py
python scripts/test_g1_motion_in_mujoco.py
python -m pytest tests/test_g1_motion_data.py tests/test_g1_mujoco_smoke.py -q
python scripts/validate_skills.py
python -m pytest -q
```

If MuJoCo is not installed, clearly report that the MuJoCo test was skipped and still complete the data inspection and `.npy` conversion tests.

---

## 13. Final Report Format

Report using this structure:

```text
Task 07 status:
- PASS / NEEDS_FIX / BLOCKED

Data inspection:
- Number of .pkl files:
- Useful fields found:
- Selected source files:

Conversion:
- Generated .npy files:
- Shapes:
- Metadata path:

MuJoCo check:
- XML used:
- nq:
- nv:
- nu:
- Motion compatibility:
- Simulation smoke result:

Files created or modified:
- ...

Commands run:
- ...

Test result:
- ...

Remaining issues:
- ...

Recommended next step:
- ...
```

The recommended next step must be one of:

```text
Implement MotionClipMujocoBackend
Fix motion dimension mismatch
Choose a better motion source file
Install MuJoCo and rerun smoke test
Inspect TextOp output format later
```

Remember: this task is only about `.pkl` inspection, `.npy` conversion, and minimal MuJoCo testing. Do not integrate TextOp and do not implement the full backend yet.