from app.utils.pagination import paginate


def test_basic_pagination():
    items = list(range(47))
    page = paginate(items, 1, 20)
    assert page.total_items == 47
    assert page.total_pages == 3
    assert page.page == 1
    assert page.items == list(range(20))
    assert not page.has_prev
    assert page.has_next
    assert page.label == "1/3"


def test_last_page():
    items = list(range(47))
    page = paginate(items, 3, 20)
    assert page.items == list(range(40, 47))
    assert page.has_prev
    assert not page.has_next


def test_clamp_out_of_range():
    items = list(range(10))
    high = paginate(items, 99, 20)
    assert high.page == 1  # clamped (only 1 page)
    low = paginate(items, 0, 5)
    assert low.page == 1


def test_empty():
    page = paginate([], 1, 20)
    assert page.total_items == 0
    assert page.total_pages == 1
    assert page.items == []
    assert not page.has_next
    assert not page.has_prev


def test_exact_multiple():
    page = paginate(list(range(40)), 2, 20)
    assert page.total_pages == 2
    assert page.items == list(range(20, 40))
    assert not page.has_next
