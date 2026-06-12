# CHOREO Registry vs SkillMotion Comparison

- Registry output: `G:\Code\Python\HumaSkill\outputs\choreo_ab\registry\demo_walk_kick_crouch_stand`
- SkillMotion output: `G:\Code\Python\HumaSkill\outputs\choreo_ab\skillmotion\demo_walk_kick_crouch_stand`
- Overall pass: `True`

| Segment | Pass | Success | Margin Δ | MAJE Δ | Seam Δ | Peak jerk Δ | AUJ Δ | Start | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| stabilization_000_stand_ready | yes | yes | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | yes |  |
| skill_001_walk_forward | yes | yes | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | yes |  |
| transition_001_walk_forward_to_kick_leg_body | yes | yes | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | yes | keep_bridge_not_stand_ready |
| transition_001_walk_forward_to_kick_leg_post | yes | yes | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | yes | keep_bridge_not_stand_ready |
| skill_002_kick_leg | yes | yes | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | yes |  |
| transition_002_kick_leg_to_crouch_down | yes | yes | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | yes | keep_config_interpolation |
| skill_003_crouch_down | yes | yes | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | yes |  |
| transition_003_crouch_down_to_stand_up | yes | yes | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | yes | keep_config_interpolation |
| skill_004_stand_up | yes | yes | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | yes |  |
