"""Frequency band shifting utilities."""

from __future__ import annotations

import numpy as np

from src.memory.frequency_bands import FrequencyBand


class FrequencyEnhancer:
    """Shift frequency spectra between LOW/MID/HIGH bands."""

    def __init__(self) -> None:
        self.shift_factors = {
            (FrequencyBand.LOW, FrequencyBand.MID): 10.0,
            (FrequencyBand.MID, FrequencyBand.HIGH): 4.0,
            (FrequencyBand.LOW, FrequencyBand.HIGH): 40.0,
            (FrequencyBand.MID, FrequencyBand.LOW): 0.1,
            (FrequencyBand.HIGH, FrequencyBand.MID): 0.25,
            (FrequencyBand.HIGH, FrequencyBand.LOW): 0.025,
        }

    def shift_band(
        self,
        spectrum: np.ndarray,
        from_band: FrequencyBand,
        to_band: FrequencyBand,
    ) -> np.ndarray:
        """Shift the dominant frequency band by scaling radius."""
        if spectrum.ndim != 3 or spectrum.shape[-1] != 4:
            raise ValueError("Expected (H, W, 4) spectrum")
        if from_band == to_band:
            return spectrum.copy()
        factor = self.shift_factors.get((from_band, to_band))
        if factor is None:
            raise KeyError(f"No shift factor for {from_band} -> {to_band}")

        h, w = spectrum.shape[:2]
        center_y, center_x = h // 2, w // 2
        shifted = np.zeros_like(spectrum)

        if not np.any(spectrum):
            return shifted
        dominant_radius = self._dominant_radius(spectrum, center_y, center_x)
        max_radius = np.sqrt(center_y**2 + center_x**2)
        base_radius = max(dominant_radius, max_radius * 0.01)
        target_radius = min(base_radius * factor, max_radius)

        if dominant_radius <= 1e-6 and target_radius > 0:
            new_x = int(round(center_x + target_radius))
            if 0 <= new_x < w:
                shifted[center_y, new_x] = spectrum[center_y, center_x]
            return shifted

        for y in range(h):
            dy = y - center_y
            for x in range(w):
                dx = x - center_x
                if not np.any(spectrum[y, x]):
                    continue
                distance = np.sqrt(dx**2 + dy**2)
                if distance <= 1e-6:
                    continue
                scale = target_radius / distance
                new_y = int(round(center_y + dy * scale))
                new_x = int(round(center_x + dx * scale))
                if 0 <= new_y < h and 0 <= new_x < w:
                    shifted[new_y, new_x] += spectrum[y, x]

        return shifted

    def _dominant_radius(self, spectrum: np.ndarray, center_y: int, center_x: int) -> float:
        magnitude = np.sqrt(spectrum[..., 0] ** 2 + spectrum[..., 1] ** 2)
        if not np.any(magnitude):
            return 0.0
        max_index = np.unravel_index(np.argmax(magnitude), magnitude.shape)
        dy = max_index[0] - center_y
        dx = max_index[1] - center_x
        return float(np.sqrt(dx**2 + dy**2))

    def validate_roundtrip(
        self,
        spectrum: np.ndarray,
        path: list[FrequencyBand],
    ) -> tuple[float, float]:
        if len(path) < 2:
            raise ValueError("Roundtrip path must include at least 2 bands")
        current = spectrum
        for start, end in zip(path, path[1:]):
            current = self.shift_band(current, start, end)
        freq_error = self._dominant_radius_error(spectrum, current)
        structure_sim = self._structure_similarity(spectrum, current)
        return freq_error, structure_sim

    def _dominant_radius_error(self, original: np.ndarray, shifted: np.ndarray) -> float:
        h, w = original.shape[:2]
        center_y, center_x = h // 2, w // 2
        orig_radius = self._dominant_radius(original, center_y, center_x)
        shifted_radius = self._dominant_radius(shifted, center_y, center_x)
        if orig_radius <= 1e-6:
            return 0.0
        return abs(orig_radius - shifted_radius) / orig_radius

    def _structure_similarity(self, original: np.ndarray, shifted: np.ndarray) -> float:
        flat_orig = original[..., 0].flatten()
        flat_shifted = shifted[..., 0].flatten()
        denom = np.linalg.norm(flat_orig) * np.linalg.norm(flat_shifted)
        if denom <= 1e-8:
            return 0.0
        return float(np.dot(flat_orig, flat_shifted) / denom)
