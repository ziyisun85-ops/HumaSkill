# GMT obs/reference 契约结论

Generated: 2026-06-03T01:01:04

GMT root source: `G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking`

## M0 简短复述

Prompt.md 的目标是在 GMT sim2sim 之上构建三层 harness，把 `walk_forward(10s) -> kick_leg -> crouch_down -> stand_up` 转成同一个 MuJoCo episode 内连续执行的 GMT reference segments。硬约束是：M0 先读源码确认 obs/reference 契约；常驻单 episode；不逐段 subprocess 调 `sim2sim.py`；段间不 reset；只使用 GMT 8 个真实 pkl；root 重锚、track 步进、reference 时间索引、归一化和摔倒策略都由 M0 事实驱动。

Plan.md milestone 顺序：P0 人工验证 GMT 原始环境；M0 GMT obs/reference 契约调查；M1 GMTTrackingRunner；M2 Task Plan 层；M3 Middle Architecture 层；M4 端到端集成；M5 产物收敛与最终验证。M0 是硬门槛，M0 validation 通过前不得写 M1 及之后实现代码。

## 环境与资产检查

- GMT root: `G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking`
- sim2sim.py: `G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py`, exists=True
- motion directory: `G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\assets\motions`
- checkpoint: `G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\assets\pretrained_checkpoints\pretrained.pt`, exists=True
- robot xml: `G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\assets\robots\g1\g1.xml`, exists=True
- sim2sim CLI motion option in this GMT checkout is `--motion_file`, not `--motion` (source: G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:309).

| motion | exists | fps | frames | seconds | root_pos | root_rot | dof_pos | local_body_pos |
|---|---:|---:|---:|---:|---|---|---|---|
| airkick_stand.pkl | yes | 29.887359 | 200 | 6.658 | (200, 3) | (200, 4) | (200, 23) | (200, 38, 3) |
| basic_walk.pkl | yes | 29.980814 | 1173 | 39.092 | (1173, 3) | (1173, 4) | (1173, 23) | (1173, 38, 3) |
| crouchwalk_stand.pkl | yes | 29.933775 | 227 | 7.550 | (227, 3) | (227, 4) | (227, 23) | (227, 38, 3) |
| dance.pkl | yes | 30.000000 | 690 | 22.967 | (690, 3) | (690, 4) | (690, 23) | (690, 38, 3) |
| dance_waltz.pkl | yes | 33.250620 | 269 | 8.060 | (269, 3) | (269, 4) | (269, 23) | (269, 38, 3) |
| kick_walk.pkl | yes | 29.974160 | 291 | 9.675 | (291, 3) | (291, 4) | (291, 23) | (291, 38, 3) |
| squat.pkl | yes | 59.999989 | 304 | 5.050 | (304, 3) | (304, 4) | (304, 23) | (304, 38, 3) |
| walk_stand.pkl | yes | 29.932280 | 222 | 7.383 | (222, 3) | (222, 4) | (222, 23) | (222, 38, 3) |

## GMT obs/reference 契约结论

### 1. 如何只加载一次 policy + mujoco，并在不 reset 的前提下连续步进

`HumanoidEnv.__init__` 创建 MuJoCo model/data，设置 timestep，调用一次 keyframe reset 和一次 `mj_step`，创建 viewer，加载 `MotionLib`，初始化 proprio history，并加载 TorchScript policy。对应源码：model/data/reset 在 G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:148，policy load 在 G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:184。

`run()` 的循环只推进当前 `self.model` / `self.data`，没有在循环内 reset。控制步在 `i % self.sim_decimation == 0` 时计算 action，随后每个物理步都用当前 `pd_target` 算 PD torque 并 `mujoco.mj_step`。对应源码：控制门槛 G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:254，policy call G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:271，PD target G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:280，torque 和 physics step G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:292 / G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:297。

Harness 结论：`GMTTrackingRunner.initialize()` 应复用 `__init__` 中的加载与 reset 逻辑；`track(reference_frames)` 只替换当前 reference source 并推进同一份 `model/data`。多次 `track()` 之间不得调用 `mj_resetDataKeyframe`，但每段 reference 的 reference time index 应从该段的 0 秒开始，policy 的 `last_action` 和 `proprio_history_buf` 应跨段保留。

### 2. policy observation 的参考目标是绝对 root，还是 root 相对量、速度量

`_get_mimic_obs()` 从 motion reference 取 20 个未来目标时间点：`root_pos, root_rot, root_vel, root_ang_vel, dof_pos`。最终 mimic obs 拼接字段是 `root_pos[..., 2:3]`、reference roll/pitch、root linear velocity（经 reference root quat 旋到局部系）、reference yaw angular velocity、reference dof_pos。对应源码：时间构造 G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:193 / G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:194，motion frame 读取 G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:197，mimic concat G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:213。

结论：GMT policy 不直接观察完整 absolute_root 的 x/y/yaw reference；它只使用 reference root height z、roll/pitch、局部 root linear velocity、局部 yaw angular velocity 和 dof_pos。为了匹配 Plan.md 的二分支配置，本项目把 `reference_contract.root_reference_mode` 选为 `root_relative` 分支，并记录细化事实：它是“无 global x/y/yaw tracking target，但有 absolute root height”。因此 skill clip 不需要按当前真实 world x/y/yaw 做 root 重锚；root height 仍应保留 pkl/transition 的实际 z 轨迹。

### 3. skill clip 与 transition 是否需要重锚到当前真实 root

不需要对 skill clip 的 world x/y/yaw 做强制 reanchor。理由是 obs 不消费 reference x/y/yaw，只消费 root height、roll/pitch、局部速度和关节角。对 world x/y/yaw 重锚不会影响主要 tracking target，反而可能引入和 GMT 源 motion 速度差分不一致的 reference velocity。

实现分支选择：`reanchor_reference_frames()` 必须存在并支持 `absolute_root` / `offset_root_pos` 分支，但默认调用路径按 M0 选择 `pass_through` / `root_relative`。Transition 的第一帧仍由真实 `RobotState` 生成，目标入口使用下一段 skill 的未重锚 reference first frame；其中对 policy 有效的是 target z、roll/pitch 和 dof。

### 4. 控制频率、物理频率、decimation

- `sim_dt = 0.001` seconds，物理频率 1000 Hz（source: G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:141）。
- `sim_decimation = 20`（source: G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:142）。
- `control_dt = sim_dt * sim_decimation = 0.02` seconds，控制频率 50 Hz（source: G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:143）。
- 一个 action 维持 20 个 MuJoCo physics steps。

### 5. 参考帧如何按时间索引到控制步

控制步 `curr_timestep = i // sim_decimation`，base motion time 是 `curr_timestep * control_dt`。mimic obs 使用未来 target offsets `tar_obs_steps = [1, 5, 10, ..., 95]`，即相对当前控制时刻向前看 0.02s 到 1.90s。对应源码：G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:159、G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:193、G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:194。

`MotionLib.calc_motion_frame()` 先用 motion length 对 motion time 取循环：`motion_times -= floor(motion_times / length) * length`，再用 `phase = times / motion_length` 映射到 `[0, num_frames - 1]`，取 `frame_idx0`、`frame_idx1` 和 blend。root_pos / dof_pos 线性插值，root_rot 用 slerp。对应源码：loop G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\utils\motion_lib.py:155，phase/index G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\utils\motion_lib.py:141 / G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\utils\motion_lib.py:144，插值 G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\utils\motion_lib.py:174 / G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\utils\motion_lib.py:175。

结论：runner 不应简单按整数 frame index 取 30fps reference；应按 control time 以 seconds 查询 reference，并在相邻 reference frames 之间插值。若自建 `ReferenceFramesMotionLib`，应复刻 `MotionLib` 的 length = `(N - 1) / fps`、loop、phase、blend、linear/slerp 规则。

### 6. obs 是否带历史窗口

带历史窗口，但只保存 proprio obs，不保存 mimic obs。`history_len = 20`，`proprio_history_buf` 初始化为 20 个零向量；每个控制步构造当前 `obs_prop` 后，先把历史 flatten 拼入 `obs_buf`，policy 推理后再 append 当前 `obs_prop`。对应源码：history init G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:168，history flatten G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:263，obs concat G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:266。

G1 维度：`n_proprio = 3 + 2 + 3 * num_actions = 74`；mimic 每个未来步为 `1 + 1 + 1 + 3 + 1 + 23 = 30`? 代码实际字段是 root_z(1), roll(1), pitch(1), root_vel(3), root_ang_vel_z(1), dof_pos(23)，合计 30；20 个未来步合计 600。总 obs 维度为 `600 + 74 + 20*74 = 2154`。

### 7. obs normalization 如何加载和应用

源码没有加载 running mean/std 或 normalizer 文件。只有显式 scaling：`dof_pos_scale = 1.0`、`dof_vel_scale = 0.05`、`ang_vel_scale = 0.25`，以及 action scale `0.5`。对应源码：scales G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:171、obs_prop G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:254、action scale/pd target G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:280。

结论：M1 observation normalization 不加载外部 stats；只复刻这些 scaling 和 ankle velocity masking（`obs_dof_vel[[4, 5, 10, 11]] = 0`）。

### 8. reference velocity 是否需要由参考序列差分得到

需要。pkl 文件只提供 fps、root_pos、root_rot、dof_pos、local_body_pos 等位置/姿态数据；`MotionLib` 在加载时从相邻 reference frames 差分计算 `root_vel`、`root_ang_vel` 和 `dof_vel`，并用窗口 19 做 smoothing。对应源码：motion load G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\utils\motion_lib.py:54 / G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\utils\motion_lib.py:58，root_vel G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\utils\motion_lib.py:66，root_ang_vel G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\utils\motion_lib.py:72，dof_vel G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\utils\motion_lib.py:77。

runner 中若不直接使用 GMT `MotionLib`，则 `ReferenceFrames` 必须派生同等 velocity fields，至少 root velocity 与 angular velocity 要可用于 mimic obs。

### 9. `local_body_pos` 在 observation 中是否必需

不必需。GMT pkl 包含 `local_body_pos`，shape 为 `(N, 38, 3)`，但 `MotionLib` 不加载它，`calc_motion_frame()` 不返回它，`sim2sim.py` 的 mimic obs 也不拼接它。对应源码：MotionLib 只读取 `root_pos/root_rot/dof_pos` 于 G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\utils\motion_lib.py:58，返回字段于 G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\utils\motion_lib.py:179。

结论：Middle Architecture 的 motion adapter 仍应读取并保留 `local_body_pos`，因为架构验收要求有该字段；但 runner observation 不依赖它，插值时可线性插值或按目标填充，缺失时不阻塞 M1 tracking。

## Motion 字段、shape、root 坐标与四元数顺序

- motion pkl 是 dict，含 `fps`, `root_pos`, `root_rot`, `dof_pos`, `local_body_pos`, `link_body_list`。
- `root_pos`: `(N, 3)`，world frame root position；obs 只消费 z。
- `root_rot`: `(N, 4)`，GMT motion 内部顺序是 `xyzw`。证据：`torch_utils.quat_mul` 解包为 `x,y,z,w`（G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\utils\torch_utils.py:12），`view_motion.py` 写入 MuJoCo qpos 时使用 `root_rot[[3,0,1,2]]` 转成 MuJoCo `wxyz`（G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\view_motion.py:49）。
- MuJoCo `qpos[3:7]` 是 `wxyz`；RobotState 面向 harness 建议统一保存 MuJoCo/root sensor 的 `root_quat` 为 `wxyz`，ReferenceFrames 的 `root_rot` 保存 GMT pkl 的 `xyzw`，进入 MuJoCo 或欧拉计算时显式转换。
- `dof_pos`: `(N, 23)`，顺序与 `sim2sim.py` 的 `dof_names` 和 MuJoCo actuator 顺序一致：left leg 6, right leg 6, waist yaw/roll/pitch 3, left arm 4, right arm 4。
- `local_body_pos`: `(N, 38, 3)`，M0 结论为保存但 obs 不消费。

## sim2sim step 推进逻辑

在每个 physics step 读取当前 dof_pos/dof_vel/root orientation/angular velocity。每 20 个 physics steps 计算一次 obs 和 policy action；action clipping 到 `[-10, 10]` 后乘 `0.5`，加 `default_dof_pos` 得到 PD target。每个 physics step 都用 `torque = (pd_target - dof_pos) * stiffness - dof_vel * damping` 并按 torque limits clip 后写入 `data.ctrl`，再 `mj_step`。对应源码：extract G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:226，control loop G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:247，policy G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:271，torque G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:292，step G:\Code\Python\Paper-Reproduction\GMT\humanoid-general-motion-tracking\sim2sim.py:297。

多段 harness 的 `track()` 应以 reference segment 的帧数/时长决定循环长度；每段内部从 segment-local time 0 开始索引 reference，物理 `data`、history、last_action 跨段保留。

## reset 与摔倒逻辑

原始 `sim2sim.py` 只有初始化时 `mj_resetDataKeyframe(self.model, self.data, 0)`，没有 runtime reset 或 fall detection。M1 需要按 Prompt.md 新增最小 `_has_fallen()`，但阈值不是 GMT 源码事实；它应来自 `configs/harness.yaml` 的 harness 配置，并在 Documentation.md 标注为 harness empirical config。

## M0 决策

- `reference_contract.root_reference_mode`: `root_relative`（细化：无 global x/y/yaw target，保留 root height z target）。
- `reference_contract.reanchor_skill_clip`: `false`。
- `reference_contract.reference_velocity_policy`: `derive_like_motion_lib`。
- `reference_contract.local_body_pos_policy`: `preserve_for_middle_architecture_not_used_by_runner_obs`。
- `runner_timing.physics_dt`: `0.001`。
- `runner_timing.control_dt`: `0.02`。
- `runner_timing.decimation`: `20`。
- `runner_timing.obs_history`: `20` proprio frames.
- `runner_timing.obs_normalization`: explicit scales only; no loaded mean/std normalization.
- `runner_timing.reference_time_indexing`: segment-local control time in seconds -> `MotionLib`-style loop/phase/blend.

## 文档冲突记录

- `Architecture_Desgin.md` 说 motion `root_rot` 四元数顺序为 `wxyz`；GMT 源码显示 pkl/`MotionLib` 内部为 `xyzw`，写入 MuJoCo qpos 时才转换为 `wxyz`。按 Prompt.md 和 Implement.md 的 M0 源码事实优先，后续代码采用 `ReferenceFrames.root_rot = xyzw`, `RobotState.root_quat = wxyz`。
- `Plan.md` P0 command 使用 `--motion walk_stand.pkl`；当前 GMT `sim2sim.py --help` 暴露的是 `--motion_file`。后续脚本入口可以接受 `--motion` 作为 harness 自己的参数，但原版 GMT 命令应使用 `--motion_file`。
