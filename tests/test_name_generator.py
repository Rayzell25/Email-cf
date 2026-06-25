import random

from app.services import name_generator as ng
from app.utils.validators import normalize_name


def test_estimate_space_is_large():
    # PRD requires hundreds of thousands to millions of combinations
    assert ng.estimate_space() >= 100_000


def test_generate_one_no_digits_by_default():
    rnd = random.Random(123)
    for _ in range(200):
        name = ng.generate_one(rnd)
        assert name
        assert not any(ch.isdigit() for ch in name)


def test_generate_one_normalizes_to_readable():
    rnd = random.Random(7)
    for _ in range(200):
        name = ng.generate_one(rnd)
        norm = normalize_name(name)
        assert norm.isalnum()
        assert norm == norm.lower()
        assert len(norm) >= 4


def test_generate_batch_unique_within_batch():
    rnd = random.Random(42)
    batch = ng.generate_batch(10, rnd=rnd)
    assert len(batch) == 10
    norms = [normalize_name(n) for n in batch]
    assert len(set(norms)) == len(norms)


def test_generate_batch_excludes_given():
    rnd = random.Random(1)
    first = ng.generate_batch(5, rnd=rnd)
    exclude = {normalize_name(n) for n in first}
    rnd2 = random.Random(1)
    second = ng.generate_batch(5, exclude_normalized=exclude, rnd=rnd2)
    for n in second:
        assert normalize_name(n) not in exclude


def test_generate_batch_low_collision_over_many():
    rnd = random.Random(99)
    names = ng.generate_batch(500, rnd=rnd, max_attempts=20000)
    # should be able to produce a large unique set without exhausting attempts
    assert len(names) == 500
    assert len({normalize_name(n) for n in names}) == 500
