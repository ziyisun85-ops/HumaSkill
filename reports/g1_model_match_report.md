# G1 Model Match Report

Inspection time: 2026-05-12 15:20:28 +08:00

Inspected folder: `model/g1_description`

## File Counts

- XML file count: 10
- URDF file count: 25

## Loadable XML Files

| XML path | nq | nv | nu | njnt | nbody | qpos_match nq==30 | action_match nu==23 |
|---|---:|---:|---:|---:|---:|---|---|
| `model/g1_description/g1_23dof.xml` | 30 | 29 | 23 | 24 | 25 | true | true |
| `model/g1_description/g1_23dof_rev_1_0.xml` | 30 | 29 | 23 | 24 | 25 | true | true |
| `model/g1_description/g1_29dof.xml` | 36 | 35 | 29 | 30 | 31 | false | false |
| `model/g1_description/g1_29dof_lock_waist.xml` | 34 | 33 | 27 | 28 | 31 | false | false |
| `model/g1_description/g1_29dof_lock_waist_rev_1_0.xml` | 34 | 33 | 27 | 28 | 31 | false | false |
| `model/g1_description/g1_29dof_lock_waist_with_hand_rev_1_0.xml` | 48 | 47 | 41 | 42 | 43 | false | false |
| `model/g1_description/g1_29dof_rev_1_0.xml` | 36 | 35 | 29 | 30 | 31 | false | false |
| `model/g1_description/g1_29dof_with_hand.xml` | 50 | 49 | 43 | 44 | 45 | false | false |
| `model/g1_description/g1_29dof_with_hand_rev_1_0.xml` | 50 | 49 | 43 | 44 | 45 | false | false |
| `model/g1_description/g1_dual_arm.xml` | 14 | 14 | 14 | 14 | 15 | false | false |

## Failed XML Files

None. All 10 XML files loaded successfully with MuJoCo.

## URDF Files

The 25 URDF files were recorded only and not loaded as MuJoCo XML. They include top-level G1 variants and nested Inspire Hand URDFs.

## Best Matching Model

Best matching model: `model/g1_description/g1_23dof.xml`

Matching reason:

- It satisfies the strongest ranking condition: `nq = 30` and `nu = 23`.
- The current motion data fields can form a 30-D qpos candidate as `root_trans_offset[3] + root_rot[4] + dof[23]`.
- Its 23 actuators align with the current 23-D `dof` data for later actuator-control inspection.
- `model/g1_description/g1_23dof_rev_1_0.xml` has the same dimensions and is also a direct match. `g1_23dof.xml` is selected first because it is the base non-revision filename.

## Compatibility Conclusion

`compatible_with_qpos_30`

The TextOp G1 23-DoF XML variants directly match the expected full qpos dimension for the existing retargeted motion components.

## Recommended Next Step

Convert `[root_trans_offset, root_rot, dof]` to full 30-D qpos `.npy` clips using `model/g1_description/g1_23dof.xml`, then run a MuJoCo qpos playback smoke test against that XML.
