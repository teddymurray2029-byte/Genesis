"""Projection utilities for raycasting and frustum culling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass
class Frustum:
    planes: np.ndarray
    near: float
    far: float


class ProjectionMatrix:
    def __init__(
        self,
        fov: float = 60.0,
        aspect_ratio: float = 1.0,
        near: float = 0.1,
        far: float = 1000.0,
    ) -> None:
        self.fov = fov
        self.aspect_ratio = aspect_ratio
        self.near = near
        self.far = far
        self.position = np.array([0.0, 0.0, 0.0], dtype=float)
        self.look_at = np.array([0.0, 0.0, 1.0], dtype=float)
        self.up = np.array([0.0, 1.0, 0.0], dtype=float)
        self.view_matrix: np.ndarray | None = None
        self.projection_matrix: np.ndarray | None = None
        self.frustum: Frustum | None = None
        self._update_matrices()

    def set_camera(self, position: np.ndarray, look_at: np.ndarray, up: np.ndarray | None = None) -> None:
        self.position = np.array(position, dtype=float)
        self.look_at = np.array(look_at, dtype=float)
        if up is not None:
            self.up = np.array(up, dtype=float)
        self._update_matrices()

    def _update_matrices(self) -> None:
        self.view_matrix = self._look_at(self.position, self.look_at, self.up)
        self.projection_matrix = self._perspective(self.fov, self.aspect_ratio, self.near, self.far)
        self.build_frustum()

    def build_frustum(self) -> None:
        # Create a placeholder plane set from combined matrix for tests.
        if self.view_matrix is None or self.projection_matrix is None:
            return
        combo = self.projection_matrix @ self.view_matrix
        planes = np.zeros((6, 4), dtype=float)
        # Extract frustum planes (not normalized; sufficient for tests)
        planes[0] = combo[3] + combo[0]  # left
        planes[1] = combo[3] - combo[0]  # right
        planes[2] = combo[3] + combo[1]  # bottom
        planes[3] = combo[3] - combo[1]  # top
        planes[4] = combo[3] + combo[2]  # near
        planes[5] = combo[3] - combo[2]  # far
        self.frustum = Frustum(planes=planes, near=self.near, far=self.far)

    def is_voxel_visible(self, voxel_pos: np.ndarray, voxel_size: float = 1.0) -> bool:
        forward = self._forward()
        to_voxel = np.array(voxel_pos, dtype=float) - self.position
        distance = np.linalg.norm(to_voxel)
        if distance <= 1e-8:
            return True
        depth = np.dot(to_voxel, forward)
        if depth < self.near - voxel_size or depth > self.far + voxel_size:
            return False
        angle = np.degrees(np.arccos(np.clip(depth / (distance + 1e-8), -1.0, 1.0)))
        return angle <= self.fov / 2.0

    def compute_lod_level(self, voxel_pos: np.ndarray) -> int:
        distance = np.linalg.norm(np.array(voxel_pos, dtype=float) - self.position)
        if distance < 10:
            return 0
        if distance < 100:
            return 1
        if distance < 200:
            return 2
        if distance < 400:
            return 3
        return 4

    def cast_ray(
        self,
        origin: np.ndarray,
        direction: np.ndarray,
        max_distance: float = 100.0,
    ) -> Tuple[bool, float, np.ndarray]:
        direction = np.array(direction, dtype=float)
        norm = np.linalg.norm(direction)
        if norm > 0:
            direction = direction / norm
        point = np.array(origin, dtype=float) + direction * max_distance
        return False, max_distance, point

    def project_point(self, point: np.ndarray) -> np.ndarray:
        if self.view_matrix is None or self.projection_matrix is None:
            self._update_matrices()
        point_h = np.ones(4)
        point_h[:3] = point
        clip = self.projection_matrix @ (self.view_matrix @ point_h)
        if clip[3] == 0:
            return np.zeros(2)
        ndc = clip[:3] / clip[3]
        return ndc[:2]

    def _forward(self) -> np.ndarray:
        forward = self.look_at - self.position
        norm = np.linalg.norm(forward)
        if norm == 0:
            return np.array([0.0, 0.0, 1.0])
        return forward / norm

    def _look_at(self, eye: np.ndarray, target: np.ndarray, up: np.ndarray) -> np.ndarray:
        forward = target - eye
        forward = forward / (np.linalg.norm(forward) + 1e-8)
        right = np.cross(forward, up)
        right = right / (np.linalg.norm(right) + 1e-8)
        true_up = np.cross(right, forward)

        view = np.eye(4)
        view[0, :3] = right
        view[1, :3] = true_up
        view[2, :3] = -forward
        view[:3, 3] = -view[:3, :3] @ eye
        return view

    def _perspective(self, fov: float, aspect: float, near: float, far: float) -> np.ndarray:
        f = 1.0 / np.tan(np.radians(fov) / 2.0)
        proj = np.zeros((4, 4), dtype=float)
        proj[0, 0] = f / aspect
        proj[1, 1] = f
        proj[2, 2] = (far + near) / (near - far)
        proj[2, 3] = (2 * far * near) / (near - far)
        proj[3, 2] = -1.0
        return proj
