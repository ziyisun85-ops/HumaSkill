import numpy as np


class SplitScreenViewer:
    """Renders reference (left) and tracked (right) robot states side by side."""

    def __init__(self, model, tracked_data, num_dofs=23, width=640, height=480):
        import mujoco
        import cv2

        self._mujoco = mujoco
        self._cv2 = cv2
        self.model = model
        self.tracked_data = tracked_data
        self.num_dofs = num_dofs
        self.width = width
        self.height = height

        self.ref_data = mujoco.MjData(model)
        mujoco.mj_resetDataKeyframe(model, self.ref_data, 0)

        self.renderer_ref = mujoco.Renderer(model, height, width)
        self.renderer_track = mujoco.Renderer(model, height, width)

        self._cam_ref = mujoco.MjvCamera()
        self._cam_ref.distance = 3.5
        self._cam_ref.elevation = -15
        self._cam_ref.azimuth = 90

        self._cam_track = mujoco.MjvCamera()
        self._cam_track.distance = 3.5
        self._cam_track.elevation = -15
        self._cam_track.azimuth = 90

    def update_reference(self, root_pos: np.ndarray, root_rot_xyzw: np.ndarray, dof_pos: np.ndarray):
        mujoco = self._mujoco
        x, y, z, w = root_rot_xyzw
        self.ref_data.qpos[:3] = root_pos
        self.ref_data.qpos[3:7] = [w, x, y, z]  # MuJoCo expects wxyz
        self.ref_data.qpos[7:7 + self.num_dofs] = dof_pos
        mujoco.mj_kinematics(self.model, self.ref_data)

    def render(self):
        cv2 = self._cv2

        self._cam_ref.lookat[:] = self.ref_data.qpos[:3]
        self.renderer_ref.update_scene(self.ref_data, self._cam_ref)
        left_img = self.renderer_ref.render().copy()

        self._cam_track.lookat[:] = self.tracked_data.qpos[:3]
        self.renderer_track.update_scene(self.tracked_data, self._cam_track)
        right_img = self.renderer_track.render().copy()

        combined = np.concatenate([left_img, right_img], axis=1)
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(combined, "Reference", (10, 30), font, 0.9, (255, 255, 255), 2)
        cv2.putText(combined, "Tracker", (self.width + 10, 30), font, 0.9, (255, 255, 255), 2)
        cv2.imshow("HumaSkill", combined[:, :, ::-1])
        cv2.waitKey(1)

    def close(self):
        self._cv2.destroyAllWindows()
        self.renderer_ref.close()
        self.renderer_track.close()
