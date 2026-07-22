from alfred import doctor


def test_checks_return_bool_line_pairs():
    results = doctor.checks()
    assert results
    for ok, line in results:
        assert isinstance(ok, bool)
        assert isinstance(line, str) and line


def test_optional_extras_are_never_required():
    for present, label in doctor.optional_extras():
        assert isinstance(present, bool)
        assert isinstance(label, str) and label
