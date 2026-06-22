from src.sources.youtube import _clean_description, _is_worthless_comment


class TestCleanDescriptionUrls:
    def test_line_with_http_url_removed(self):
        text = "Descrição relevante do vídeo.\nhttps://www.youtube.com/@canal\nMais conteúdo aqui."
        result = _clean_description(text)
        assert "youtube.com" not in result
        assert "Descrição relevante" in result

    def test_line_with_http_without_s_removed(self):
        text = "Veja mais em http://site.com/link\nOutro conteúdo relevante do vídeo."
        result = _clean_description(text)
        assert "http://" not in result
        assert "conteúdo relevante" in result

    def test_clean_line_without_url_preserved(self):
        text = "Neste vídeo mostramos como preparar uma massa de pizza caseira em casa."
        assert "pizza" in _clean_description(text)


class TestCleanDescriptionHashtags:
    def test_hashtag_only_line_removed(self):
        text = "Boa descrição do vídeo.\n#brasil #esporte #futebol\nMais texto relevante."
        result = _clean_description(text)
        assert "#brasil" not in result
        assert "Boa descrição" in result

    def test_trailing_hashtags_stripped(self):
        text = "Texto do vídeo sobre futebol #brasil #esporte"
        result = _clean_description(text)
        assert "#brasil" not in result
        assert "Texto do vídeo" in result

    def test_hashtag_inside_sentence_not_removed(self):
        # Linha com URL + hashtag é removida pelo filtro de URL antes
        # Mas hashtag no meio de texto sem URL deve ser preservada
        text = "O #CNNBrasil acompanha os principais acontecimentos do país."
        result = _clean_description(text)
        # Linha não é só hashtags, então não é removida pelo _HASHTAG_LINE_RE
        assert "CNN" in result


class TestCleanDescriptionSeparators:
    def test_tilde_separator_removed(self):
        text = "Conteúdo antes.\n~~~~~~~\nConteúdo depois do separador."
        result = _clean_description(text)
        assert "~~~" not in result
        assert "Conteúdo depois" in result

    def test_dash_separator_removed(self):
        text = "Conteúdo antes.\n-------\nConteúdo depois do separador."
        result = _clean_description(text)
        assert "---" not in result

    def test_equals_separator_removed(self):
        text = "Conteúdo antes.\n=======\nConteúdo depois."
        result = _clean_description(text)
        assert "===" not in result


class TestCleanDescriptionSocialLabels:
    def test_instagram_label_line_removed(self):
        text = "Vídeo sobre tecnologia e inovação.\nInstagram: @perfil\nMais informações sobre o tema."
        result = _clean_description(text)
        assert "Instagram:" not in result
        assert "tecnologia" in result

    def test_twitter_label_line_removed(self):
        text = "Conteúdo relevante.\nTwitter: @handle\nFim do conteúdo relevante."
        result = _clean_description(text)
        assert "Twitter:" not in result

    def test_email_line_removed(self):
        text = "Contato comercial: parceiro@empresa.com.br\nAssista ao vídeo completo em nosso canal."
        result = _clean_description(text)
        assert "@empresa.com" not in result
        assert "vídeo completo" in result


class TestCleanDescriptionBlockHeaders:
    def test_redes_sociais_block_skipped(self):
        text = (
            "Descrição relevante do vídeo sobre Copa do Mundo.\n"
            "REDES SOCIAIS\n"
            "Instagram: @perfil\n"
            "Twitter: @handle\n"
        )
        result = _clean_description(text)
        assert "REDES SOCIAIS" not in result
        assert "Copa do Mundo" in result

    def test_vire_membro_block_skipped(self):
        text = (
            "Conteúdo do Flow Podcast sobre tecnologia.\n"
            "VIRE MEMBRO DO FLOW PRA TER CONTEÚDOS EXCLUSIVOS\n"
            "https://youtube.com/@FlowPodcast/join\n"
        )
        result = _clean_description(text)
        assert "VIRE MEMBRO" not in result
        assert "Flow Podcast" in result

    def test_acompanhe_plataformas_block_skipped(self):
        text = (
            "Transmissão ao vivo da CNN Brasil desta segunda-feira.\n"
            "ACOMPANHE A CNN BRASIL TAMBÉM NAS OUTRAS PLATAFORMAS:\n"
            "Site: https://cnnbrasil.com.br/\n"
            "Facebook: https://facebook.com/cnnbrasil\n"
        )
        result = _clean_description(text)
        assert "ACOMPANHE" not in result
        assert "CNN Brasil" in result

    def test_siga_nos_block_skipped(self):
        text = (
            "Episódio sobre inteligência artificial no mercado.\n"
            "SIGA-NOS NAS REDES SOCIAIS\n"
            "Instagram, Twitter e YouTube\n"
        )
        result = _clean_description(text)
        assert "SIGA-NOS" not in result
        assert "inteligência artificial" in result


class TestCleanDescriptionEdgeCases:
    def test_empty_returns_empty(self):
        assert _clean_description("") == ""

    def test_only_boilerplate_returns_empty(self):
        text = "REDES SOCIAIS\nhttps://insta.com\nhttps://twitter.com"
        assert _clean_description(text) == ""

    def test_clean_description_fully_preserved(self):
        text = "Neste corte, o Iberê investiga por que você nunca vê cocô de formiga no ambiente natural."
        result = _clean_description(text)
        assert "Iberê" in result
        assert "formiga" in result


class TestIsWorthlessComment:
    def test_too_short_worthless(self):
        assert _is_worthless_comment("Boa!") is True

    def test_exactly_14_chars_worthless(self):
        assert _is_worthless_comment("a" * 14) is True

    def test_exactly_15_chars_not_worthless(self):
        assert _is_worthless_comment("a" * 15) is False

    def test_no_letters_worthless(self):
        assert _is_worthless_comment("12345 !!! 999") is True

    def test_only_numbers_and_spaces_worthless(self):
        assert _is_worthless_comment("1234 5678 9012") is True

    def test_ordinal_primeiro_worthless(self):
        assert _is_worthless_comment("Primeiro a comentar aqui!") is True

    def test_ordinal_segundo_worthless(self):
        assert _is_worthless_comment("Segundo nessa live irmão!") is True

    def test_ordinal_quarto_worthless(self):
        # Caso real: "Quarto aeeeeeeeeeeeeee melhor canal do universo!!"
        assert _is_worthless_comment("Quarto aeeeeeeeeeeeeee melhor canal do universo!!") is True

    def test_ordinal_first_english_worthless(self):
        assert _is_worthless_comment("First to comment on this amazing video!") is True

    def test_ordinal_1st_worthless(self):
        assert _is_worthless_comment("1st here congrats everyone watching!") is True

    def test_ordinal_1_grau_worthless(self):
        assert _is_worthless_comment("1° aqui, que vídeo incrível mano!") is True

    def test_valid_comment_not_worthless(self):
        assert _is_worthless_comment("Que vídeo incrível, aprendi muito sobre o assunto hoje!") is False

    def test_valid_comment_with_numbers_not_worthless(self):
        assert _is_worthless_comment("Esse canal tem mais de 5 anos e nunca decepcionou ninguém.") is False

    def test_valid_long_ordinal_sentence_not_worthless(self):
        # "primeiro" dentro de frase não iniciando com o ordinal
        assert _is_worthless_comment("Esse foi o primeiro vídeo que assisti do canal e já me inscrevi!") is False
