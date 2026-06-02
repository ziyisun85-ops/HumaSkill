# Task 08A: Check Whether the TextOp G1 Model Matches the 23-DoF Motion Data

You are working on the local HumaSkill project.

Project path:

```powershell
G:\Code\Python\HumaSkill
```

The current task is to inspect the newly found TextOp G1 model folder:

```text
model/g1_description
```

and determine whether it contains a MuJoCo model that directly matches the current G1 motion data.

---

## 1. Current Background

Task 07 has already been completed.

Known results:

```text
G1 motion data folder:
data/g1-retargeted-motions/

174 .pkl files were found.

Useful motion fields:
dof: [T, 23]
root_trans_offset: [T, 3]
root_rot: [T, 4]
pose_aa: [T, 27, 3]
fps
contact_mask

Generated files:
motions/stand_ready.npy
motions/arm_wave.npy
motions/final_pose.npy

These .npy files currently store 23-D dof trajectories.
```

The previously tested MuJoCo model was:

```text
model/unitree_g1/scene.xml
```

Its model information was:

```text
nq = 36
nv = 35
nu = 0
```

So the current 23-D dof trajectories are not directly compatible with that model’s full qpos dimension.

Now inspect:

```text
model/g1_description/
```

to check whether it contains a better model for this 23-DoF data.

---

## 2. Goal

Inspect the model files under `model/g1_description` and find a MuJoCo model compatible with the current motion data.

Ideal matching logic:

```text
root_trans_offset [3]
+
root_rot [4]
+
dof [23]
=
qpos [30]
```

Priority target:

```text
nq = 30
```

Also check:

```text
nu = 23
```

Interpretation:

```text
nq = 30:
The full MuJoCo qpos is likely directly buildable from root_trans_offset, root_rot, and dof.

nu = 23:
The actuator count may align with the 23-D dof data and could be useful for later control execution.
```

This task is only for model compatibility inspection.

Do not convert motion data yet.  
Do not implement a backend yet.  
Do not integrate TextOp yet.  
Do not modify core HumaSkill logic.

---

## 3. Files to Read First

If this is a fresh Codex session, read:

```text
README.md
PROJECT_PLAN.md
INTERFACES.md
configs/robot_g1_mujoco.yaml
motions/metadata.json
scripts/test_g1_motion_in_mujoco.py
```

If this continues the current session, only inspect:

```text
configs/robot_g1_mujoco.yaml
motions/metadata.json
scripts/test_g1_motion_in_mujoco.py
```

---

## 4. Allowed Files to Create or Modify

You may create:

```text
scripts/inspect_g1_description_models.py
reports/g1_model_match_report.md
```

You may minimally edit:

```text
.gitignore
README.md
```

Only do so if it is clearly useful for recording the report location or ignoring generated report folders.

Keep the following unchanged:

```text
humaskill/
scripts/convert_g1_pkl_to_npy.py
scripts/test_g1_motion_in_mujoco.py
motions/
data/
model/
```

---

## 5. Step 1: Create the Model Inspection Script

Create:

```text
scripts/inspect_g1_description_models.py
```

The script must recursively search:

```text
model/g1_description
```

for:

```text
*.xml
*.urdf
```

For each XML file, try loading it with MuJoCo:

```python
mujoco.MjModel.from_xml_path(...)
```

For each loadable XML, print:

```text
file path
nq
nv
nu
njnt
nbody
joint count
actuator count
joint names
actuator names
qpos_match: nq == 30
action_match: nu == 23
```

For XML files that fail to load, print:

```text
file path
load error
```

For URDF files, only list:

```text
file path
file type: URDF
note: recorded only, not loaded as MuJoCo XML
```

If MuJoCo is not installed, print:

```text
MuJoCo is not installed. Install with: python -m pip install mujoco
```

and exit cleanly.

---

## 6. Step 2: Run the Inspection Script

Run:

```powershell
python scripts/inspect_g1_description_models.py
```

Record the output.

---

## 7. Step 3: Decide the Best Matching Model

Use this decision logic:

```text
Best direct qpos match:
nq = 30

Possible control match:
nu = 23

Partial match:
nq is close to 30, or joint information suggests floating base + 23 body DoF

No match:
No loadable XML satisfies nq = 30 or nu = 23
```

If multiple XML files satisfy the conditions, rank them as:

```text
1. nq = 30 and nu = 23
2. nq = 30
3. nu = 23
4. nq closest to 30
```

---

## 8. Step 4: Generate a Report

Create:

```text
reports/g1_model_match_report.md
```

The report must include:

```text
Inspection time
Inspected folder
XML file count
URDF file count
For each loadable XML: nq, nv, nu, njnt, nbody
Failed XML files and error reasons
Best matching model
Matching reason
Recommended next step
```

---

## 9. Final Report Format

Report using this format:

```text
Task 08A status:
- PASS / NEEDS_FIX / BLOCKED

Model folder:
- model/g1_description

Files found:
- XML count:
- URDF count:

Loadable XML files:
- path:
  nq:
  nv:
  nu:
  njnt:
  nbody:
  qpos_match:
  action_match:

Failed XML files:
- path:
  error:

Best matching model:
- path:
- reason:

Compatibility conclusion:
- compatible_with_qpos_30 / compatible_with_action_23 / partial_match / no_match

Files created or modified:
- ...

Commands run:
- ...

Recommended next step:
- If qpos match exists: convert [root_trans_offset, root_rot, dof] to qpos .npy
- If only action match exists: inspect actuator control mode
- If no match exists: build a 23-DoF compatible XML or create explicit 23-DoF to current model qpos mapping
```

---

## 10. Important Scope Boundary

This task only checks model compatibility.

Do not do:

```text
motion data conversion
TextOp integration
MotionClipMujocoBackend implementation
core HumaSkill logic modification
```

After completion, only report which model matches best and what should happen next for the 23-D dof data.