import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from jarvis import memory


def test_to_vec_from_list():
    vec = memory._to_vec([0.1, 0.2, 0.3])
    assert vec.shape == (3,)
    assert str(vec.dtype) == "float32"
