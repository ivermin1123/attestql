"""Task 3: consequences of `set(predicted_res) == set(ground_truth_res)` over
Python tuples that are not stated anywhere in BIRD's evaluator code, only
implied by what `set()` and tuple equality do to the objects sqlite3's
default type mapping returns (https://docs.python.org/3/library/sqlite3.html
#sqlite-and-python-types). Confirmed here rather than asserted from memory.
"""

print("1 == 1.0 == True:", 1 == 1.0 == True)
print("hash(1) == hash(1.0) == hash(True):", hash(1) == hash(1.0) == hash(True))
print("{(1,)} == {(1.0,)}:", {(1,)} == {(1.0,)})
print("b'x' == 'x':", b"x" == "x")
print("{(None,)} == {(None,)}:", {(None,)} == {(None,)})
print("set() == set():", set() == set())
print("empty predicted vs empty gold scores a match:", set([]) == set([]))
print("(1, 2) == (1, 2, 3):", (1, 2) == (1, 2, 3))
print("column order matters, (1, 2) == (2, 1):", (1, 2) == (2, 1))
nan = float("nan")
print("nan == nan:", nan == nan)
print("{(nan,)} == {(nan,)} (fresh objects):", {(nan,)} == {(nan,)})
