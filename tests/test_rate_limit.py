from utils.rate_limit import RateLimiter


def test_allows_up_to_max_then_blocks():
    rl = RateLimiter(max_calls=3, per_seconds=10.0)
    assert rl.allow(1, now=0.0)
    assert rl.allow(1, now=1.0)
    assert rl.allow(1, now=2.0)
    assert rl.allow(1, now=3.0) is False


def test_window_slides():
    rl = RateLimiter(max_calls=2, per_seconds=10.0)
    assert rl.allow(1, now=0.0)
    assert rl.allow(1, now=1.0)
    assert rl.allow(1, now=2.0) is False
    # After the window passes, earlier hits expire.
    assert rl.allow(1, now=11.5) is True


def test_keys_are_independent():
    rl = RateLimiter(max_calls=1, per_seconds=10.0)
    assert rl.allow(1, now=0.0)
    assert rl.allow(2, now=0.0)
    assert rl.allow(1, now=0.1) is False
