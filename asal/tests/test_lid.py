import pytest

from asal.lid import AsalHeuristicLID

SOMALI = "Wasiirka ayaa sheegay in dowladdu ay ka shaqeyn doonto horumarinta waxbarashada iyo caafimaadka."
ENGLISH = "The minister said that the government would work on improving education and health services."
SWAHILI = "Waziri alisema kwamba serikali itafanya kazi ya kuboresha elimu na huduma za afya."


def test_heuristic_somali_english():
    h = AsalHeuristicLID()
    assert h.predict(SOMALI).label == "som"
    assert h.predict(ENGLISH).label == "eng"
    assert h.predict(SWAHILI).label != "som"


def test_heuristic_empty():
    assert AsalHeuristicLID().predict("1234 !!").label == "und"


@pytest.mark.slow
def test_lingua_backend():
    lingua_mod = pytest.importorskip("lingua")
    assert lingua_mod
    from asal.lid import LinguaLID

    lid = LinguaLID()
    assert lid.predict(SOMALI).label == "som"
    assert lid.predict(ENGLISH).label == "eng"
