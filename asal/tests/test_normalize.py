from asal.normalize import normalise


def test_apostrophe_is_kept():
    assert normalise("ba'an iyo su'aal").text == "ba'an iyo su'aal"


def test_typographic_apostrophes_become_ascii():
    res = normalise("ba’an, loʼ, su‘aal")
    assert res.text == "ba'an, lo', su'aal"
    assert res.changes["apostrophe_variant"] == 3


def test_nfc_and_zero_width():
    res = normalise("café​ waa")
    assert res.text == "café waa"
    assert res.changes["nfc"] == 1
    assert res.changes["control_or_zero_width"] == 1


def test_whitespace_and_paragraphs():
    assert normalise("  Waa   maxay? \r\n\r\n\r\n\r\nHaa  ") .text == "Waa maxay?\n\nHaa"


def test_curly_double_quotes():
    assert normalise("“Waa run”").text == '"Waa run"'
