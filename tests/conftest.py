import os
import sys

import numpy as np
import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


@pytest.fixture
def protos():
    rng = np.random.default_rng(42)
    return [rng.standard_normal((512, 512, 4)).astype(np.float32) for _ in range(3)]
