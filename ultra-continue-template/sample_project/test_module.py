import pytest
from module import sum_numbers


def test_basic():
    assert sum_numbers(2, 3) == 5


def test_negative():
    assert sum_numbers(-2, -3) == -5


def test_type_error():
    with pytest.raises(TypeError):
        sum_numbers(2, "3")


def test_float_addition():
    assert sum_numbers(2.5, 3.1) == pytest.approx(5.6)
