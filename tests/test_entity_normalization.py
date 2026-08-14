import pytest
from src.pipelines.entity_normalization import normalize_entity_name

def test_normalize_entity_name():
    assert normalize_entity_name("Open AI") == "OpenAI"
    assert normalize_entity_name("OpenAI, Inc.") == "OpenAI"
    assert normalize_entity_name("Apple") == "Apple"
    assert normalize_entity_name("Tech Corp") == "tech"
    assert normalize_entity_name("Data LLC") == "data"
    assert normalize_entity_name("A&B Ltd.") == "ab"
    assert normalize_entity_name("") == ""
    assert normalize_entity_name(None) == ""
