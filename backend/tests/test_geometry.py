from app.core.geometry import CountLinePx, line_side_sign, segments_intersect


def test_segments_intersect_true():
    assert segments_intersect((0, 0), (10, 10), (0, 10), (10, 0))


def test_segments_intersect_false_parallel():
    assert not segments_intersect((0, 0), (10, 0), (0, 5), (10, 5))


def test_line_side_sign_opposite_sides():
    p1, p2 = (0, 0), (10, 0)
    above = line_side_sign(p1, p2, (5, -5))
    below = line_side_sign(p1, p2, (5, 5))
    assert (above > 0) != (below > 0)


def _vertical_line(positive_on_right: bool) -> CountLinePx:
    # Вертикальная линия x=5, y от 0 до 10. positive_side_point справа (x=10) или слева (x=0).
    p1, p2 = (5, 0), (5, 10)
    pos_pt = (10, 5) if positive_on_right else (0, 5)
    sign = line_side_sign(p1, p2, pos_pt)
    return CountLinePx(p1=p1, p2=p2, positive_sign=sign, direction="positive")


def test_crossing_in_correct_direction_is_counted():
    line = _vertical_line(positive_on_right=True)
    # Движение слева направо (x: 0 -> 10) на уровне y=5 пересекает линию и
    # переходит на положительную (правую) сторону.
    assert line.counts((0, 5), (10, 5)) is True


def test_crossing_in_wrong_direction_is_not_counted():
    line = _vertical_line(positive_on_right=True)
    # Направление задано только 'positive', переход справа налево не считается.
    assert line.counts((10, 5), (0, 5)) is False


def test_both_directions_mode_counts_either_way():
    p1, p2 = (5, 0), (5, 10)
    sign = line_side_sign(p1, p2, (10, 5))
    line_both = CountLinePx(p1=p1, p2=p2, positive_sign=sign, direction="both")
    assert line_both.counts((0, 5), (10, 5)) is True
    assert line_both.counts((10, 5), (0, 5)) is True


def test_no_crossing_when_segment_does_not_reach_line():
    line = _vertical_line(positive_on_right=True)
    # Остаётся по одну сторону линии — пересечения нет.
    assert line.counts((0, 5), (2, 5)) is False


def test_jitter_near_line_does_not_double_count_without_real_crossing():
    """Дрожание рамки у самой линии (микродвижения на одной стороне) не
    должно регистрироваться как пересечение — только реальный переход через
    отрезок линии засчитывается."""
    line = _vertical_line(positive_on_right=True)
    jitter_points = [(4.9, 5), (4.95, 5), (4.8, 5), (4.99, 5)]
    crossed_any = False
    prev = (4.9, 5)
    for p in jitter_points[1:]:
        if line.counts(prev, p):
            crossed_any = True
        prev = p
    assert crossed_any is False
