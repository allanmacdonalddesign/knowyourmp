from types import SimpleNamespace

from civic import cache
from civic.analysis.classify import Classifier, parse_topics

TAX = {"housing": "", "health": "", "other": ""}


def test_parse_topics_filters_unknown_and_caps():
    assert parse_topics('["housing", "bogus", "health", "other"]', TAX) == ["housing", "health"]
    assert parse_topics("no json", TAX) == ["other"]


def test_never_reclassifies_same_source():
    calls = []

    class Fake:
        class messages:
            @staticmethod
            def create(**kw):
                calls.append(kw)
                return SimpleNamespace(content=[SimpleNamespace(text='["housing"]')])

    c = Classifier(Fake, cache.ClassificationCache(cache.connect(":memory:")), TAX)
    assert c.classify("u1", "rent is too high") == ["housing"]
    assert c.classify("u1", "rent is too high") == ["housing"]
    assert len(calls) == 1
