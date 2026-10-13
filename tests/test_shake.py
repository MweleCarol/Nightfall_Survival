from src.world.shake import ScreenShake


def test_no_trauma_means_no_shake():
    assert ScreenShake().offset.length() == 0


def test_the_shake_never_exceeds_the_maximum():
    shake = ScreenShake(max_offset=14.0, decay=0.0)
    shake.add_trauma(1.0)
    for _ in range(300):
        shake.update(0.013)
        assert abs(shake.offset.x) <= 14.0 and abs(shake.offset.y) <= 14.0


def test_trauma_decays_to_nothing():
    shake = ScreenShake(decay=1.6)
    shake.add_trauma(0.5)
    shake.update(1.0)
    assert shake.trauma == 0.0 and shake.offset.length() == 0


def test_trauma_is_clamped_and_negatives_are_ignored():
    shake = ScreenShake()
    shake.add_trauma(0.8)
    shake.add_trauma(0.8)
    assert shake.trauma == 1.0
    shake.add_trauma(-5.0)
    assert shake.trauma == 1.0


def test_more_trauma_shakes_harder():
    def peak(trauma: float) -> float:
        shake = ScreenShake(decay=0.0)
        shake.add_trauma(trauma)
        best = 0.0
        for _ in range(300):
            shake.update(0.01)
            best = max(best, shake.offset.length())
        return best

    assert peak(0.9) > peak(0.3)