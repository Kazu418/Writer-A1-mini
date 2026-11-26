from plotnote.fonts import glyph_paths


def test_unicode_superscript_is_raised():
    ordinary = [y for ps in glyph_paths("2") for x, y in ps]
    raised = [y for ps in glyph_paths("²") for x, y in ps]
    assert max(raised) < max(ordinary) * 0.7


def test_unicode_subscript_is_lowered():
    ordinary = [y for ps in glyph_paths("1") for x, y in ps]
    lowered = [y for ps in glyph_paths("₁") for x, y in ps]
    assert min(lowered) > min(ordinary) + 0.3
