"""Testa _parse_value() de mcp_server.py.

Cobre os casos: bool, int, float, JSON (lista/objeto) e string literal.
O fix que adiciona parse de JSON foi motivado pelo bug onde configurar_fonte()
gravava feeds como string JSON em vez de lista YAML.
"""

import pytest

mcp_server = pytest.importorskip(
    'mcp_server',
    reason='mcp_server não importável (dependências MCP ausentes)',
)
_parse_value = mcp_server._parse_value


class TestParseValue:
    # Bool
    def test_true_string(self):
        assert _parse_value('true') is True

    def test_false_string(self):
        assert _parse_value('false') is False

    def test_sim_string(self):
        assert _parse_value('sim') is True

    def test_nao_string(self):
        assert _parse_value('não') is False

    # Int / float
    def test_integer_string(self):
        assert _parse_value('42') == 42
        assert isinstance(_parse_value('42'), int)

    def test_float_string(self):
        assert _parse_value('3.14') == pytest.approx(3.14)

    # JSON list — o caso do bug dos feeds
    def test_json_list_parsed_to_list(self):
        val = _parse_value('[{"url": "https://exemplo.com", "name": "Feed"}]')
        assert isinstance(val, list)
        assert len(val) == 1
        assert val[0]['url'] == 'https://exemplo.com'

    def test_json_empty_list(self):
        assert _parse_value('[]') == []

    def test_json_list_multiple_items(self):
        val = _parse_value('[{"a": 1}, {"b": 2}]')
        assert isinstance(val, list)
        assert len(val) == 2

    # JSON object
    def test_json_object_parsed_to_dict(self):
        val = _parse_value('{"key": "value", "num": 3}')
        assert isinstance(val, dict)
        assert val['key'] == 'value'
        assert val['num'] == 3

    def test_json_empty_object(self):
        assert _parse_value('{}') == {}

    # Invalid JSON starting with [ or { — falls back to string
    def test_invalid_json_list_returns_string(self):
        val = _parse_value('[not valid json')
        assert isinstance(val, str)

    def test_invalid_json_object_returns_string(self):
        val = _parse_value('{not valid json')
        assert isinstance(val, str)

    # Plain strings
    def test_plain_string_unchanged(self):
        assert _parse_value('claude-haiku-4-5') == 'claude-haiku-4-5'

    def test_empty_string_unchanged(self):
        assert _parse_value('') == ''

    # Non-string passthrough
    def test_bool_passthrough(self):
        assert _parse_value(True) is True

    def test_int_passthrough(self):
        assert _parse_value(99) == 99
