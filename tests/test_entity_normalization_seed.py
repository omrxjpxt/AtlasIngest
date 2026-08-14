import pytest
from src.pipelines.entity_normalization import normalize_entity_name

def test_seed_exact_match():
    assert normalize_entity_name("Open AI") == "OpenAI"
    assert normalize_entity_name("OpenAI, Inc.") == "OpenAI"
    assert normalize_entity_name("Anthropic PBC") == "Anthropic"

def test_fallback_normalization():
    assert normalize_entity_name("Unknown Startup LLC") == "unknownstartup"
    assert normalize_entity_name("Random Company, Inc.") == "randomcompany"

def test_empty_string():
    assert normalize_entity_name("") == ""
    assert normalize_entity_name(None) == ""
