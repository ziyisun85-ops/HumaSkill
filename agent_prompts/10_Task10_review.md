You are debugging the HumaSkill G1 qpos visual playback pipeline.

Current project:
G:/Code/Python/HumaSkill

Current status:
Task 08B numeric conversion and MuJoCo smoke test have passed, but visual playback is wrong. In MuJoCo viewer, the robot appears lying sideways or floating in the air. This means `mj_forward` can run, but the converted qpos may not match the MuJoCo model pose convention, quaternion convention, coordinate frame, root height, or joint ordering.

Your task:
Carefully inspect whether the PKL motion data fields match the MuJoCo G1 model qpos layout exactly, and fix any mismatch.

Important files:
- `model/g1_description/g1_23dof.xml`
- `motions/metadata.json`
- `motions/metadata_qpos.json`
- `scripts/convert_g1_pkl_to_qpos.py`
- `scripts/test_g1_qpos_motion_in_mujoco.py`
- `scripts/view_g1_qpos_motion_in_mujoco.py`
- generated qpos clips:
  - `motions/stand_ready_qpos.npy`
  - `motions/arm_wave_qpos.npy`
  - `motions/final_pose_qpos.npy`

Do not modify:
- `humaskill/`

Do not implement:
- backend integration
- TextOp integration
- training code

Main debugging goal:
Verify that the converted qpos layout is exactly what MuJoCo expects:

`[root_x, root_y, root_z, root_qw, root_qx, root_qy, root_qz, joint_1, ..., joint_23]`

The source PKL files contain:
- `root_trans_offset` with shape `[T, 3]`
- `root_rot` with shape `[T, 4]`
- `dof` with shape `[T, 23]`

The current conversion concatenates these into `[T, 30]`, but visual playback suggests one or more conventions may be wrong.

Please inspect the following carefully.

1. Inspect the MuJoCo XML model

Load `model/g1_description/g1_23dof.xml` with MuJoCo and print:

- `model.nq`
- `model.nv`
- `model.nu`
- all joint names
- all joint types
- each joint qpos address
- each joint dof address
- the order of the 23 actuated joints after the root freejoint
- whether the first joint is a freejoint
- whether MuJoCo expects root quaternion order as `wxyz`

Confirm the exact qpos layout used by this XML.

2. Inspect the source PKL motion files

Use the files listed in `motions/metadata.json`.

For each source PKL, inspect and print:

- available keys
- shape and dtype of `root_trans_offset`
- shape and dtype of `root_rot`
- shape and dtype of `dof`
- first frame `root_trans_offset[0]`
- first frame `root_rot[0]`
- first frame `dof[0]`
- first frame ` min/max of root translation
- min/max of dof values
- whether root quaternion norms are close to 1

Pay special attention to `root_rot`.

Determine whether `root_rot` is stored as:

- `[qw, qx, qy, qz]`
- `[qx, qy, qz, qw]`

MuJoCo freejoint qpos requires:

`[x, y, z, qw, qx, qy, qz]`

If the PKL uses `xyzw`, convert it to `wxyz` before writing qpos.

3. Check root pose correctness

For the first frame of each converted qpos clip, verify:

- `qpos[0, 0:3]` is a reasonable root position
- `qpos[0, 3:7]` is a normalized quaternion in MuJoCo order
- the robot is placed at a reasonable height above the ground
- the root orientation does not make the robot lie sideways, upside down, or float unnaturally

If the root height is suspicious, compare:

- PKL root z
- MuJoCo body geometry height
- default model keyframe or neutral pose if available
- whether `root_trans_offset` is relative to a different origin

Do not blindly add offsets unless you can justify the mismatch.

4. Check DOF joint order

The source PKL `dof` has 23 dimensions. The MuJoCo model also has 23 actuated joints.

Verify that each `dof[:, i]` corresponds to the correct MuJoCo joint after the root freejoint.

Print a mapping table like:

`PKL dof index -> MuJoCo joint name -> qpos address -> actuator name if available`

If the PKL metadata includes joint names, compare them directly.

If the PKL does not include joint names, infer carefully from:
- metadata
- XML joint order
- known Unitree G1 23-DOF convention
- source dataset documentation if available in the repo

Do not assume the order is correct just because the dimension matches.

5. Add or improve diagnostics

Add a small diagnostic mode or script if useful, for example:

`scripts/diagnose_g1_qpos_alignment.py`

It should print:

- XML qpos layout
- XML joint order
- XML actuator order
- PKL field shapes
- first-frame PKL root pose
- first-frame converted qpos
- first-frame MuJoCo `data.qpos`
- root/body position after `mj_forward`
- quaternion convention guess
- possible mismatch warnings

Keep this diagnostic script standalone.

6. Fix the conversion if a mismatch is found

If the problem is quaternion order:
- update `scripts/convert_g1_pkl_to_qpos.py`
- convert PKL root quaternion into MuJoCo `wxyz` order
- document the convention in code comments
- regenerate all qpos clips

If the problem is joint order:
- update the conversion script with an explicit reorder mapping
- document the mapping clearly
- add a test that checks the reorder logic

If the problem is root height or coordinate frame:
- identify the exact source of the coordinate mismatch
- apply the smallest justified correction
- document the correction clearly
- avoid arbitrary visual-only hacks

Regenerate:
- `motions/stand_ready_qpos.npy`
- `motions/arm_wave_qpos.npy`
- `motions/final_pose_qpos.npy`
- `motions/metadata_qpos.json`

7. Update tests

Update or add tests to verify:

- qpos dimension is still 30
- frame count is preserved
- root quaternion is in MuJoCo `wxyz` order
- quaternion norms are close to 1
- DOF order is explicitly checked or documented
- first 30 frames still run through `mj_forward`
- the XML `model.nq == 30`
- qpos length matches `model.nq`

8. Run validation

Run:

`python scripts/convert_g1_pkl_to_qpos.py`

`python scripts/test_g1_qpos_motion_in_mujoco.py`

`python -m pytest tests/test_g1_qpos_conversion.py tests/test_g1_qpos_playback.py -q`

`python -m pytest -q`

Also run the visual playback script manually if possible:

`python scripts/view_g1_qpos_motion_in_mujoco.py --clip stand_ready`

`python scripts/view_g1_qpos_motion_in_mujoco.py --clip arm_wave`

`python scripts/view_g1_qpos_motion_in_mujoco.py --clip final_pose`

9. Final report

Report clearly:

- exact mismatch found
- whether the issue was quaternion order, root height, coordinate frame, joint order, or viewer script logic
- files changed
- generated files updated
- commands run
- test results
- whether visual playback now appears correct
- any remaining uncertainty

Acceptance criteria:
- The robot appears upright and physically plausible in MuJoCo viewer.
- `stand_ready` looks like a stable standing pose.
- `arm_wave` shows reasonable arm motion.
- `final_pose` does not appear sideways, upside down, or floating.
- Numeric tests still pass.
- Full test suite still passes.