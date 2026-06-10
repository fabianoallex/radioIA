from src.text_utils import normalize_for_tts


class TestNormalizeForTTS:
    def test_no_currency_unchanged(self):
        text = "O clima está bom hoje."
        assert normalize_for_tts(text) == text

    def test_simple_value(self):
        assert normalize_for_tts("R$ 250,00") == "250 reais"

    def test_thousands(self):
        assert normalize_for_tts("R$ 3.000,00") == "3 mil reais"

    def test_one_million(self):
        assert normalize_for_tts("R$ 1.000.000,00") == "1 milhão de reais"

    def test_two_millions(self):
        assert normalize_for_tts("R$ 2.000.000,00") == "2 milhões de reais"

    def test_millions_and_thousands(self):
        result = normalize_for_tts("R$ 1.500.000,00")
        assert "1 milhão" in result
        assert "500 mil" in result
        assert "reais" in result

    def test_zero_value(self):
        assert normalize_for_tts("R$ 0,00") == "zero reais"

    def test_multiple_currencies_in_text(self):
        text = "Comprou por R$ 100,00 e vendeu por R$ 200,00."
        result = normalize_for_tts(text)
        assert "R$" not in result
        assert "100 reais" in result
        assert "200 reais" in result

    def test_currency_inside_sentence(self):
        result = normalize_for_tts("O produto custa R$ 50,00 no mercado.")
        assert "R$" not in result
        assert "50 reais" in result

    def test_large_value_with_parts(self):
        result = normalize_for_tts("R$ 2.300.000,00")
        assert "2 milhões" in result
        assert "300 mil" in result
