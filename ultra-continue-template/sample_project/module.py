def sum_numbers(a: float, b: float) -> float:
    """Return the sum of two numeric values (integers or floats).

    Parameters
    - a, b: numbers (int or float) to add

    Raises:
        TypeError: if either argument is not numeric (int or float).
    """
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError("Inputs must be numeric (int or float)")
    return a + b
