from src.tts_generator import parse_script, MAX_LINE_CHARS


class TestParseScript:
    def test_single_line(self):
        result = parse_script("[LOCUTOR_A]: Bom dia ouvintes!")
        assert result == [{'locutor': 'LOCUTOR_A', 'text': 'Bom dia ouvintes!'}]

    def test_three_locutors(self):
        script = "[LOCUTOR_A]: Olá!\n[LOCUTOR_B]: Oi!\n[LOCUTOR_C]: Eae!"
        result = parse_script(script)
        assert len(result) == 3
        assert [r['locutor'] for r in result] == ['LOCUTOR_A', 'LOCUTOR_B', 'LOCUTOR_C']

    def test_bold_markdown_stripped(self):
        result = parse_script("**[LOCUTOR_A]**: Texto formatado.")
        assert len(result) == 1
        assert result[0]['locutor'] == 'LOCUTOR_A'
        assert result[0]['text'] == 'Texto formatado.'

    def test_invalid_lines_skipped(self):
        script = "Linha inválida\n[LOCUTOR_A]: Linha válida"
        result = parse_script(script)
        assert len(result) == 1
        assert result[0]['locutor'] == 'LOCUTOR_A'

    def test_empty_script(self):
        assert parse_script('') == []

    def test_html_entities_decoded(self):
        # &amp; → & após html.unescape, mas & é removido pelo sanitizer (fora do charset)
        result = parse_script("[LOCUTOR_A]: Água &amp; café")
        assert '&amp;' not in result[0]['text']
        assert 'Água' in result[0]['text']
        assert 'café' in result[0]['text']

    def test_asterisks_removed_from_text(self):
        result = parse_script("[LOCUTOR_A]: Texto **importante** aqui.")
        assert '**' not in result[0]['text']
        assert 'importante' in result[0]['text']

    def test_curly_quotes_normalized(self):
        result = parse_script('[LOCUTOR_A]: Disse “olá” para mim.')
        assert '“' not in result[0]['text']
        assert '”' not in result[0]['text']

    def test_text_truncated_at_max_chars(self):
        long_text = 'A' * (MAX_LINE_CHARS + 50)
        result = parse_script(f"[LOCUTOR_A]: {long_text}")
        assert len(result[0]['text']) <= MAX_LINE_CHARS

    def test_unknown_locutor_skipped(self):
        assert parse_script("[LOCUTOR_D]: Linha fora do padrão") == []

    def test_extra_whitespace_collapsed(self):
        result = parse_script("[LOCUTOR_A]: Texto   com   espaços   extras")
        assert '  ' not in result[0]['text']

    def test_leading_trailing_whitespace_stripped(self):
        result = parse_script("  [LOCUTOR_A]: Texto com espaços  ")
        assert result[0]['text'] == 'Texto com espaços'

    def test_multiline_only_valid_lines_collected(self):
        script = (
            "# Bloco de Notícias\n"
            "[LOCUTOR_A]: Boa tarde!\n"
            "Texto solto\n"
            "[LOCUTOR_B]: Vamos às notícias.\n"
            "\n"
            "[LOCUTOR_A]: Até amanhã!\n"
        )
        result = parse_script(script)
        assert len(result) == 3
        assert result[1]['locutor'] == 'LOCUTOR_B'
