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


class TestParseScriptItemMarkers:
    def test_item_marker_sets_item_index(self):
        script = "[ITEM_1]\n[LOCUTOR_A]: Primeira notícia."
        result = parse_script(script)
        assert result[0].get('item_index') == 1

    def test_lines_before_marker_have_no_item_index(self):
        script = "[LOCUTOR_A]: Abertura.\n[ITEM_1]\n[LOCUTOR_A]: Notícia."
        result = parse_script(script)
        assert 'item_index' not in result[0]
        assert result[1].get('item_index') == 1

    def test_marker_with_trailing_text_still_parsed(self):
        # LLM pode escrever [ITEM_1]: texto — o regex permissivo deve aceitar
        script = "[ITEM_2]: Fim do item anterior\n[LOCUTOR_A]: Segunda notícia."
        result = parse_script(script)
        assert result[0].get('item_index') == 2

    def test_multiple_items_tracked_independently(self):
        script = (
            "[ITEM_1]\n"
            "[LOCUTOR_A]: Fala do item 1.\n"
            "[ITEM_2]\n"
            "[LOCUTOR_B]: Fala do item 2.\n"
        )
        result = parse_script(script)
        assert result[0].get('item_index') == 1
        assert result[1].get('item_index') == 2

    def test_marker_number_matches_correctly(self):
        script = "[ITEM_10]\n[LOCUTOR_A]: Décimo item."
        result = parse_script(script)
        assert result[0].get('item_index') == 10

    def test_item_index_persists_across_consecutive_lines(self):
        script = (
            "[ITEM_3]\n"
            "[LOCUTOR_A]: Linha um.\n"
            "[LOCUTOR_B]: Linha dois.\n"
        )
        result = parse_script(script)
        assert result[0].get('item_index') == 3
        assert result[1].get('item_index') == 3
