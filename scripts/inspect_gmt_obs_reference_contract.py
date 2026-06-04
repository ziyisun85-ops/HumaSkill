import argparse
import os
import pickle
from datetime import datetime
from pathlib import Path


EXPECTED_MOTIONS = [
    "airkick_stand.pkl",
    "basic_walk.pkl",
    "crouchwalk_stand.pkl",
    "dance.pkl",
    "dance_waltz.pkl",
    "kick_walk.pkl",
    "squat.pkl",
    "walk_stand.pkl",
]


def _read_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().splitlines()


def _find(lines, needle):
    for i, line in enumerate(lines, start=1):
        if needle in line:
            return i
    return None


def _source_ref(path, line):
    if line is None:
        return f"{path}"
    return f"{path}:{line}"


def _motion_summary(motions_dir):
    rows = []
    for name in EXPECTED_MOTIONS:
        path = motions_dir / name
        if not path.exists():
            rows.append(
                {
                    "name": name,
                    "exists": False,
                    "fps": None,
                    "frames": None,
                    "seconds": None,
                    "root_pos": None,
                    "root_rot": None,
                    "dof_pos": None,
                    "local_body_pos": None,
                    "keys": [],
                }
            )
            continue
        with open(path, "rb") as f:
            data = pickle.load(f)
        frames = int(data["root_pos"].shape[0])
        fps = float(data["fps"])
        seconds = (frames - 1) / fps if fps else 0.0
        rows.append(
            {
                "name": name,
                "exists": True,
                "fps": fps,
                "frames": frames,
                "seconds": seconds,
                "root_pos": tuple(data["root_pos"].shape),
                "root_rot": tuple(data["root_rot"].shape),
                "dof_pos": tuple(data["dof_pos"].shape),
                "local_body_pos": tuple(data["local_body_pos"].shape)
                if "local_body_pos" in data
                else None,
                "keys": sorted(data.keys()),
            }
        )
    return rows


def _line_map(gmt_root, sim2sim_rel):
    sim2sim_path = gmt_root / sim2sim_rel
    motion_lib_path = gmt_root / "utils" / "motion_lib.py"
    torch_utils_path = gmt_root / "utils" / "torch_utils.py"
    view_motion_path = gmt_root / "view_motion.py"

    sim2sim_lines = _read_lines(sim2sim_path)
    motion_lib_lines = _read_lines(motion_lib_path)
    torch_utils_lines = _read_lines(torch_utils_path)
    view_motion_lines = _read_lines(view_motion_path)

    return {
        "sim2sim": sim2sim_path,
        "motion_lib": motion_lib_path,
        "torch_utils": torch_utils_path,
        "view_motion": view_motion_path,
        "lines": {
            "sim_dt": _find(sim2sim_lines, "self.sim_dt ="),
            "sim_decimation": _find(sim2sim_lines, "self.sim_decimation ="),
            "control_dt": _find(sim2sim_lines, "self.control_dt ="),
            "mj_reset": _find(sim2sim_lines, "mj_resetDataKeyframe"),
            "mj_step_init": _find(sim2sim_lines, "mujoco.mj_step(self.model, self.data)"),
            "tar_obs_steps": _find(sim2sim_lines, "self.tar_obs_steps ="),
            "history_len": _find(sim2sim_lines, "self.history_len ="),
            "scales": _find(sim2sim_lines, "self.dof_pos_scale ="),
            "motion_lib_init": _find(sim2sim_lines, "self._motion_lib = MotionLib"),
            "policy_load": _find(sim2sim_lines, "self.policy_jit = torch.jit.load"),
            "mimic_time": _find(sim2sim_lines, "motion_times = torch.tensor"),
            "mimic_future": _find(sim2sim_lines, "obs_motion_times = self.tar_obs_steps"),
            "calc_motion_frame": _find(sim2sim_lines, "calc_motion_frame(motion_ids"),
            "mimic_cat": _find(sim2sim_lines, "mimic_obs_buf = torch.cat"),
            "extract_qpos": _find(sim2sim_lines, "dof_pos = self.data.qpos"),
            "control_loop": _find(sim2sim_lines, "if i % self.sim_decimation == 0"),
            "obs_prop": _find(sim2sim_lines, "obs_prop = np.concatenate"),
            "obs_hist": _find(sim2sim_lines, "obs_hist = np.array"),
            "obs_buf": _find(sim2sim_lines, "obs_buf = np.concatenate"),
            "policy_call": _find(sim2sim_lines, "raw_action = self.policy_jit"),
            "pd_target": _find(sim2sim_lines, "pd_target = step_actions"),
            "torque": _find(sim2sim_lines, "torque = (pd_target"),
            "physics_step": max(
                i
                for i, line in enumerate(sim2sim_lines, start=1)
                if "mujoco.mj_step(self.model, self.data)" in line
            ),
            "motion_load_fps": _find(motion_lib_lines, 'fps = motion_data["fps"]'),
            "motion_load_root": _find(motion_lib_lines, 'root_pos = torch.tensor'),
            "motion_vel": _find(motion_lib_lines, "root_vel[:-1"),
            "motion_ang_vel": _find(motion_lib_lines, "root_ang_vel[:-1"),
            "motion_dof_vel": _find(motion_lib_lines, "dof_vel[:-1"),
            "frame_phase": _find(motion_lib_lines, "phase = times /"),
            "frame_idx0": _find(motion_lib_lines, "frame_idx0 ="),
            "loop_num": _find(motion_lib_lines, "motion_loop_num ="),
            "motion_interp": _find(motion_lib_lines, "root_pos = (1.0"),
            "motion_slerp": _find(motion_lib_lines, "root_rot = slerp"),
            "motion_return": _find(motion_lib_lines, "return root_pos"),
            "quat_xyzw": _find(torch_utils_lines, "x1, y1, z1, w1 ="),
            "view_reorder": _find(view_motion_lines, "root_rot[0].cpu().numpy()[[3, 0, 1, 2]]"),
            "sim_arg_motion_file": _find(sim2sim_lines, "--motion_file"),
        },
    }


def _format_motion_table(rows):
    out = [
        "| motion | exists | fps | frames | seconds | root_pos | root_rot | dof_pos | local_body_pos |",
        "|---|---:|---:|---:|---:|---|---|---|---|",
    ]
    for r in rows:
        out.append(
            "| {name} | {exists} | {fps} | {frames} | {seconds} | {root_pos} | {root_rot} | {dof_pos} | {local_body_pos} |".format(
                name=r["name"],
                exists="yes" if r["exists"] else "no",
                fps=f"{r['fps']:.6f}" if r["fps"] is not None else "-",
                frames=r["frames"] if r["frames"] is not None else "-",
                seconds=f"{r['seconds']:.3f}" if r["seconds"] is not None else "-",
                root_pos=r["root_pos"] or "-",
                root_rot=r["root_rot"] or "-",
                dof_pos=r["dof_pos"] or "-",
                local_body_pos=r["local_body_pos"] or "-",
            )
        )
    return "\n".join(out)


def build_contract(gmt_root, sim2sim_rel):
    refs = _line_map(gmt_root, sim2sim_rel)
    lines = refs["lines"]
    motions = _motion_summary(gmt_root / "assets" / "motions")
    sim2sim_path = refs["sim2sim"]
    motion_lib_path = refs["motion_lib"]
    torch_utils_path = refs["torch_utils"]
    view_motion_path = refs["view_motion"]

    source_refs = {
        name: _source_ref(path, line)
        for name, path, line in [
            ("sim_dt", sim2sim_path, lines["sim_dt"]),
            ("sim_decimation", sim2sim_path, lines["sim_decimation"]),
            ("control_dt", sim2sim_path, lines["control_dt"]),
            ("mj_reset", sim2sim_path, lines["mj_reset"]),
            ("tar_obs_steps", sim2sim_path, lines["tar_obs_steps"]),
            ("history_len", sim2sim_path, lines["history_len"]),
            ("scales", sim2sim_path, lines["scales"]),
            ("mimic_time", sim2sim_path, lines["mimic_time"]),
            ("mimic_future", sim2sim_path, lines["mimic_future"]),
            ("calc_motion_frame", sim2sim_path, lines["calc_motion_frame"]),
            ("mimic_cat", sim2sim_path, lines["mimic_cat"]),
            ("obs_prop", sim2sim_path, lines["obs_prop"]),
            ("obs_hist", sim2sim_path, lines["obs_hist"]),
            ("obs_buf", sim2sim_path, lines["obs_buf"]),
            ("policy_load", sim2sim_path, lines["policy_load"]),
            ("extract_qpos", sim2sim_path, lines["extract_qpos"]),
            ("control_loop", sim2sim_path, lines["control_loop"]),
            ("policy_call", sim2sim_path, lines["policy_call"]),
            ("pd_target", sim2sim_path, lines["pd_target"]),
            ("torque", sim2sim_path, lines["torque"]),
            ("physics_step", sim2sim_path, lines["physics_step"]),
            ("motion_load_fps", motion_lib_path, lines["motion_load_fps"]),
            ("motion_load_root", motion_lib_path, lines["motion_load_root"]),
            ("motion_vel", motion_lib_path, lines["motion_vel"]),
            ("motion_ang_vel", motion_lib_path, lines["motion_ang_vel"]),
            ("motion_dof_vel", motion_lib_path, lines["motion_dof_vel"]),
            ("frame_phase", motion_lib_path, lines["frame_phase"]),
            ("frame_idx0", motion_lib_path, lines["frame_idx0"]),
            ("loop_num", motion_lib_path, lines["loop_num"]),
            ("motion_interp", motion_lib_path, lines["motion_interp"]),
            ("motion_slerp", motion_lib_path, lines["motion_slerp"]),
            ("motion_return", motion_lib_path, lines["motion_return"]),
            ("quat_xyzw", torch_utils_path, lines["quat_xyzw"]),
            ("view_reorder", view_motion_path, lines["view_reorder"]),
            ("sim_arg_motion_file", sim2sim_path, lines["sim_arg_motion_file"]),
        ]
    }

    return f"""# GMT obs/reference 契约结论

Generated: {datetime.now().isoformat(timespec="seconds")}

GMT root source: `{gmt_root}`

## M0 简短复述

Prompt.md 的目标是在 GMT sim2sim 之上构建三层 harness，把 `walk_forward(10s) -> kick_leg -> crouch_down -> stand_up` 转成同一个 MuJoCo episode 内连续执行的 GMT reference segments。硬约束是：M0 先读源码确认 obs/reference 契约；常驻单 episode；不逐段 subprocess 调 `sim2sim.py`；段间不 reset；只使用 GMT 8 个真实 pkl；root 重锚、track 步进、reference 时间索引、归一化和摔倒策略都由 M0 事实驱动。

Plan.md milestone 顺序：P0 人工验证 GMT 原始环境；M0 GMT obs/reference 契约调查；M1 GMTTrackingRunner；M2 Task Plan 层；M3 Middle Architecture 层；M4 端到端集成；M5 产物收敛与最终验证。M0 是硬门槛，M0 validation 通过前不得写 M1 及之后实现代码。

## 环境与资产检查

- GMT root: `{gmt_root}`
- sim2sim.py: `{sim2sim_path}`, exists={sim2sim_path.exists()}
- motion directory: `{gmt_root / "assets" / "motions"}`
- checkpoint: `{gmt_root / "assets" / "pretrained_checkpoints" / "pretrained.pt"}`, exists={(gmt_root / "assets" / "pretrained_checkpoints" / "pretrained.pt").exists()}
- robot xml: `{gmt_root / "assets" / "robots" / "g1" / "g1.xml"}`, exists={(gmt_root / "assets" / "robots" / "g1" / "g1.xml").exists()}
- sim2sim CLI motion option in this GMT checkout is `--motion_file`, not `--motion` (source: {source_refs["sim_arg_motion_file"]}).

{_format_motion_table(motions)}

## GMT obs/reference 契约结论

### 1. 如何只加载一次 policy + mujoco，并在不 reset 的前提下连续步进

`HumanoidEnv.__init__` 创建 MuJoCo model/data，设置 timestep，调用一次 keyframe reset 和一次 `mj_step`，创建 viewer，加载 `MotionLib`，初始化 proprio history，并加载 TorchScript policy。对应源码：model/data/reset 在 {source_refs["mj_reset"]}，policy load 在 {source_refs["policy_load"]}。

`run()` 的循环只推进当前 `self.model` / `self.data`，没有在循环内 reset。控制步在 `i % self.sim_decimation == 0` 时计算 action，随后每个物理步都用当前 `pd_target` 算 PD torque 并 `mujoco.mj_step`。对应源码：控制门槛 {source_refs["obs_prop"]}，policy call {source_refs["policy_call"]}，PD target {source_refs["pd_target"]}，torque 和 physics step {source_refs["torque"]} / {source_refs["physics_step"]}。

Harness 结论：`GMTTrackingRunner.initialize()` 应复用 `__init__` 中的加载与 reset 逻辑；`track(reference_frames)` 只替换当前 reference source 并推进同一份 `model/data`。多次 `track()` 之间不得调用 `mj_resetDataKeyframe`，但每段 reference 的 reference time index 应从该段的 0 秒开始，policy 的 `last_action` 和 `proprio_history_buf` 应跨段保留。

### 2. policy observation 的参考目标是绝对 root，还是 root 相对量、速度量

`_get_mimic_obs()` 从 motion reference 取 20 个未来目标时间点：`root_pos, root_rot, root_vel, root_ang_vel, dof_pos`。最终 mimic obs 拼接字段是 `root_pos[..., 2:3]`、reference roll/pitch、root linear velocity（经 reference root quat 旋到局部系）、reference yaw angular velocity、reference dof_pos。对应源码：时间构造 {source_refs["mimic_time"]} / {source_refs["mimic_future"]}，motion frame 读取 {source_refs["calc_motion_frame"]}，mimic concat {source_refs["mimic_cat"]}。

结论：GMT policy 不直接观察完整 absolute_root 的 x/y/yaw reference；它只使用 reference root height z、roll/pitch、局部 root linear velocity、局部 yaw angular velocity 和 dof_pos。为了匹配 Plan.md 的二分支配置，本项目把 `reference_contract.root_reference_mode` 选为 `root_relative` 分支，并记录细化事实：它是“无 global x/y/yaw tracking target，但有 absolute root height”。因此 skill clip 不需要按当前真实 world x/y/yaw 做 root 重锚；root height 仍应保留 pkl/transition 的实际 z 轨迹。

### 3. skill clip 与 transition 是否需要重锚到当前真实 root

不需要对 skill clip 的 world x/y/yaw 做强制 reanchor。理由是 obs 不消费 reference x/y/yaw，只消费 root height、roll/pitch、局部速度和关节角。对 world x/y/yaw 重锚不会影响主要 tracking target，反而可能引入和 GMT 源 motion 速度差分不一致的 reference velocity。

实现分支选择：`reanchor_reference_frames()` 必须存在并支持 `absolute_root` / `offset_root_pos` 分支，但默认调用路径按 M0 选择 `pass_through` / `root_relative`。Transition 的第一帧仍由真实 `RobotState` 生成，目标入口使用下一段 skill 的未重锚 reference first frame；其中对 policy 有效的是 target z、roll/pitch 和 dof。

### 4. 控制频率、物理频率、decimation

- `sim_dt = 0.001` seconds，物理频率 1000 Hz（source: {source_refs["sim_dt"]}）。
- `sim_decimation = 20`（source: {source_refs["sim_decimation"]}）。
- `control_dt = sim_dt * sim_decimation = 0.02` seconds，控制频率 50 Hz（source: {source_refs["control_dt"]}）。
- 一个 action 维持 20 个 MuJoCo physics steps。

### 5. 参考帧如何按时间索引到控制步

控制步 `curr_timestep = i // sim_decimation`，base motion time 是 `curr_timestep * control_dt`。mimic obs 使用未来 target offsets `tar_obs_steps = [1, 5, 10, ..., 95]`，即相对当前控制时刻向前看 0.02s 到 1.90s。对应源码：{source_refs["tar_obs_steps"]}、{source_refs["mimic_time"]}、{source_refs["mimic_future"]}。

`MotionLib.calc_motion_frame()` 先用 motion length 对 motion time 取循环：`motion_times -= floor(motion_times / length) * length`，再用 `phase = times / motion_length` 映射到 `[0, num_frames - 1]`，取 `frame_idx0`、`frame_idx1` 和 blend。root_pos / dof_pos 线性插值，root_rot 用 slerp。对应源码：loop {source_refs["loop_num"]}，phase/index {source_refs["frame_phase"]} / {source_refs["frame_idx0"]}，插值 {source_refs["motion_interp"]} / {source_refs["motion_slerp"]}。

结论：runner 不应简单按整数 frame index 取 30fps reference；应按 control time 以 seconds 查询 reference，并在相邻 reference frames 之间插值。若自建 `ReferenceFramesMotionLib`，应复刻 `MotionLib` 的 length = `(N - 1) / fps`、loop、phase、blend、linear/slerp 规则。

### 6. obs 是否带历史窗口

带历史窗口，但只保存 proprio obs，不保存 mimic obs。`history_len = 20`，`proprio_history_buf` 初始化为 20 个零向量；每个控制步构造当前 `obs_prop` 后，先把历史 flatten 拼入 `obs_buf`，policy 推理后再 append 当前 `obs_prop`。对应源码：history init {source_refs["history_len"]}，history flatten {source_refs["obs_hist"]}，obs concat {source_refs["obs_buf"]}。

G1 维度：`n_proprio = 3 + 2 + 3 * num_actions = 74`；mimic 每个未来步为 `1 + 1 + 1 + 3 + 1 + 23 = 30`? 代码实际字段是 root_z(1), roll(1), pitch(1), root_vel(3), root_ang_vel_z(1), dof_pos(23)，合计 30；20 个未来步合计 600。总 obs 维度为 `600 + 74 + 20*74 = 2154`。

### 7. obs normalization 如何加载和应用

源码没有加载 running mean/std 或 normalizer 文件。只有显式 scaling：`dof_pos_scale = 1.0`、`dof_vel_scale = 0.05`、`ang_vel_scale = 0.25`，以及 action scale `0.5`。对应源码：scales {source_refs["scales"]}、obs_prop {source_refs["obs_prop"]}、action scale/pd target {source_refs["pd_target"]}。

结论：M1 observation normalization 不加载外部 stats；只复刻这些 scaling 和 ankle velocity masking（`obs_dof_vel[[4, 5, 10, 11]] = 0`）。

### 8. reference velocity 是否需要由参考序列差分得到

需要。pkl 文件只提供 fps、root_pos、root_rot、dof_pos、local_body_pos 等位置/姿态数据；`MotionLib` 在加载时从相邻 reference frames 差分计算 `root_vel`、`root_ang_vel` 和 `dof_vel`，并用窗口 19 做 smoothing。对应源码：motion load {source_refs["motion_load_fps"]} / {source_refs["motion_load_root"]}，root_vel {source_refs["motion_vel"]}，root_ang_vel {source_refs["motion_ang_vel"]}，dof_vel {source_refs["motion_dof_vel"]}。

runner 中若不直接使用 GMT `MotionLib`，则 `ReferenceFrames` 必须派生同等 velocity fields，至少 root velocity 与 angular velocity 要可用于 mimic obs。

### 9. `local_body_pos` 在 observation 中是否必需

不必需。GMT pkl 包含 `local_body_pos`，shape 为 `(N, 38, 3)`，但 `MotionLib` 不加载它，`calc_motion_frame()` 不返回它，`sim2sim.py` 的 mimic obs 也不拼接它。对应源码：MotionLib 只读取 `root_pos/root_rot/dof_pos` 于 {source_refs["motion_load_root"]}，返回字段于 {source_refs["motion_return"]}。

结论：Middle Architecture 的 motion adapter 仍应读取并保留 `local_body_pos`，因为架构验收要求有该字段；但 runner observation 不依赖它，插值时可线性插值或按目标填充，缺失时不阻塞 M1 tracking。

## Motion 字段、shape、root 坐标与四元数顺序

- motion pkl 是 dict，含 `fps`, `root_pos`, `root_rot`, `dof_pos`, `local_body_pos`, `link_body_list`。
- `root_pos`: `(N, 3)`，world frame root position；obs 只消费 z。
- `root_rot`: `(N, 4)`，GMT motion 内部顺序是 `xyzw`。证据：`torch_utils.quat_mul` 解包为 `x,y,z,w`（{source_refs["quat_xyzw"]}），`view_motion.py` 写入 MuJoCo qpos 时使用 `root_rot[[3,0,1,2]]` 转成 MuJoCo `wxyz`（{source_refs["view_reorder"]}）。
- MuJoCo `qpos[3:7]` 是 `wxyz`；RobotState 面向 harness 建议统一保存 MuJoCo/root sensor 的 `root_quat` 为 `wxyz`，ReferenceFrames 的 `root_rot` 保存 GMT pkl 的 `xyzw`，进入 MuJoCo 或欧拉计算时显式转换。
- `dof_pos`: `(N, 23)`，顺序与 `sim2sim.py` 的 `dof_names` 和 MuJoCo actuator 顺序一致：left leg 6, right leg 6, waist yaw/roll/pitch 3, left arm 4, right arm 4。
- `local_body_pos`: `(N, 38, 3)`，M0 结论为保存但 obs 不消费。

## sim2sim step 推进逻辑

在每个 physics step 读取当前 dof_pos/dof_vel/root orientation/angular velocity。每 20 个 physics steps 计算一次 obs 和 policy action；action clipping 到 `[-10, 10]` 后乘 `0.5`，加 `default_dof_pos` 得到 PD target。每个 physics step 都用 `torque = (pd_target - dof_pos) * stiffness - dof_vel * damping` 并按 torque limits clip 后写入 `data.ctrl`，再 `mj_step`。对应源码：extract {source_refs["extract_qpos"]}，control loop {source_refs["control_loop"]}，policy {source_refs["policy_call"]}，torque {source_refs["torque"]}，step {source_refs["physics_step"]}。

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
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gmt-root", required=True)
    parser.add_argument("--sim2sim", default="sim2sim.py")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    gmt_root = Path(args.gmt_root).expanduser().resolve()
    sim2sim_rel = Path(args.sim2sim)
    sim2sim_path = gmt_root / sim2sim_rel
    if not gmt_root.exists():
        raise FileNotFoundError(f"GMT root not found: {gmt_root}")
    if not sim2sim_path.exists():
        raise FileNotFoundError(f"sim2sim.py not found: {sim2sim_path}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_contract(gmt_root, sim2sim_rel), encoding="utf-8")
    print(f"Wrote M0 contract: {output_path} ({output_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
