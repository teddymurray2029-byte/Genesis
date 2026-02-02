"""Compatibility decoding pipeline wrapper."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np

from src.pipeline.fft_text_decoder import FFTTextDecoder
from src.memory.frequency_field import TextFrequencyAnalyzer


class DecodingPipeline:
    """Simple decoding pipeline for tests and API compatibility."""

    def __init__(self, carrier: np.ndarray, width: int = 512, height: int = 512) -> None:
        self.width = width
        self.height = height
        self.carrier = carrier
        self.decoder = FFTTextDecoder(width=width, height=height)
        self.frequency_analyzer = TextFrequencyAnalyzer(width=width, height=height)

    def decode_to_text(self, proto_identity: np.ndarray, metadata: Dict[str, Any]) -> str:
        native_stft = metadata.get("native_stft")
        original_length = metadata.get("original_length")
        resized_spectrum = metadata.get("resized_spectrum")
        if native_stft is not None and resized_spectrum is not None:
            return self.frequency_analyzer.from_frequency_spectrum(
                resized_spectrum,
                native_stft=native_stft,
                original_length=original_length,
            )
        return self.decoder.decode_text(proto_identity)
