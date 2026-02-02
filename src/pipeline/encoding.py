"""Compatibility encoding pipeline wrapper."""

from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np

from src.pipeline.fft_text_encoder import FFTTextEncoder
from src.memory.frequency_field import TextFrequencyAnalyzer


class EncodingPipeline:
    """Simple encoding pipeline for tests and API compatibility."""

    def __init__(self, carrier: np.ndarray, width: int = 512, height: int = 512) -> None:
        self.width = width
        self.height = height
        self.carrier = carrier
        self.encoder = FFTTextEncoder(width=width, height=height)
        self.frequency_analyzer = TextFrequencyAnalyzer(width=width, height=height)

    def encode_text(self, text: str) -> Tuple[np.ndarray, Dict[str, Any]]:
        proto_identity = self.encoder.encode_text(text)
        resized_spectrum, native_stft = self.frequency_analyzer.text_to_frequency(text)
        metadata = {
            "native_stft": native_stft,
            "original_length": len(text),
            "resized_spectrum": resized_spectrum,
        }
        return proto_identity, metadata
