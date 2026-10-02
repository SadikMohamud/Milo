from asal import pii, quality

SOMALI = ("Dowladda Soomaaliya ayaa sheegtay in ay qorsheyneyso dib u habeyn lagu sameynayo "
          "nidaamka waxbarashada dalka, iyadoo la xoojinayo tayada macallimiinta.")


def test_clean_somali_passes():
    assert quality.check(SOMALI).passed


def test_too_short():
    assert quality.TOO_SHORT in quality.check("Waa haa.").reasons


def test_html_and_urls():
    html = "<div><p>" + SOMALI + "</p><a href='x'>link</a></div>"
    assert quality.HTML_MARKUP in quality.check(html).reasons
    urls = "Akhri https://example.com/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa https://example.org/bbbbbbbbbbbbbbbbbbbbbbbbbbb waa"
    assert quality.URL_HEAVY in quality.check(urls).reasons


def test_mojibake_and_replacement_char():
    assert quality.MOJIBAKE in quality.check(SOMALI + " cafÃ© â€™").reasons
    assert quality.REPLACEMENT_CHARACTER in quality.check(SOMALI + " �").reasons


def test_repeated_lines_and_low_information():
    rep = "\n".join(["Fadlan la soco wararka."] * 6 + [SOMALI])
    assert quality.REPEATED_LINES in quality.check(rep).reasons
    assert quality.LOW_INFORMATION in quality.check(" ".join(["haa waa"] * 40)).reasons


def test_excessive_punctuation():
    assert quality.EXCESSIVE_PUNCTUATION in quality.check("waa !!! ??? ... --- !!! ??? waa ;;; ::: waa haa").reasons


def test_pii_redaction():
    res = pii.redact("La xiriir axmed@example.so ama +252 61 234 5678 ama 0612345678.")
    assert "<EMAIL>" in res.text and res.text.count("<PHONE>") == 2
    assert res.redactions == {"email": 1, "phone": 2}


def test_pii_leaves_years_and_counts():
    text = "Sanadkii 1991 ayaa 250 qof la dilay."
    assert pii.redact(text).text == text
