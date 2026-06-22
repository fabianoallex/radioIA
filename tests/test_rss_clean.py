from src.sources.rss import _clean_rss_text


class TestHtmlDecoding:
    def test_html_entities_decoded(self):
        result = _clean_rss_text("", "Texto com &amp; empresa e &lt;destaque&gt; no mercado internacional")
        assert "&amp;" not in result
        assert "&lt;" not in result
        assert "empresa" in result

    def test_html_tags_stripped(self):
        result = _clean_rss_text(
            "",
            '<a href="https://news.google.com">EU courts Brazil</a>&nbsp;<font color="#6f6f6f">Reuters</font>',
        )
        assert "<a" not in result
        assert "<font" not in result
        assert "EU courts Brazil" in result
        assert "Reuters" in result

    def test_nbsp_normalized(self):
        result = _clean_rss_text("", "Texto&nbsp;&nbsp;Reuters")
        assert "\xa0" not in result
        # múltiplos espaços colapsados
        assert "  " not in result


class TestTitleDeduplication:
    def test_exact_title_at_start_removed(self):
        title = "Galaxy S27 Pro pode chegar com tela de privacidade em 2027"
        text = f"{title}\nA Samsung planeja lançar o modelo com nova tecnologia de display."
        result = _clean_rss_text(title, text)
        assert result.count(title.strip()) == 0

    def test_content_after_title_preserved(self):
        title = "Galaxy S27 Pro pode chegar com tela de privacidade em 2027"
        text = f"{title}\nA Samsung planeja lançar o modelo com nova tecnologia de display."
        result = _clean_rss_text(title, text)
        assert "Samsung" in result

    def test_line_containing_title_but_longer_preserved(self):
        title = "Evento do ano"
        text = "Notícia sobre o Evento do ano aconteceu ontem em São Paulo."
        result = _clean_rss_text(title, text)
        assert "Notícia" in result


class TestAuthorLines:
    def test_canaltech_author_removed(self):
        text = "Por Nathan Vieira • Editado por Léo Müller |\nO Galaxy S27 pode chegar com tela de privacidade."
        result = _clean_rss_text("", text)
        assert "Nathan Vieira" not in result
        assert "Galaxy S27" in result

    def test_ofertas_author_removed(self):
        text = "Por Canaltech Ofertas |\nA Fast Shop cortou o preço do PlayStation 5."
        result = _clean_rss_text("", text)
        assert "Canaltech Ofertas" not in result
        assert "Fast Shop" in result

    def test_regular_line_starting_with_por_preserved(self):
        text = "Por meio de nota, a empresa confirmou os planos de expansão para 2027."
        result = _clean_rss_text("", text)
        # Não termina com | ou •, então não é linha de autor
        assert "empresa confirmou" in result


class TestPhotoCaptions:
    def test_standalone_foto_line_removed(self):
        text = "Quadrilha vence etapa regional do festival.\nFoto: Pedro Melo/Batucada\nA competição reuniu grupos de todo o Brasil."
        result = _clean_rss_text("", text)
        assert "Pedro Melo" not in result
        assert "Quadrilha" in result
        assert "competição" in result

    def test_trailing_foto_on_line_removed(self):
        text = "Quadrilha Lumiar vence etapa regional do festival — Foto: Pedro Melo/Batucada"
        result = _clean_rss_text("", text)
        assert "Pedro Melo" not in result
        assert "Lumiar" in result

    def test_imagem_caption_removed(self):
        text = "Imagem: Reprodução/CNN\nO calor extremo afeta mais de um bilhão de pessoas no mundo."
        result = _clean_rss_text("", text)
        assert "Reprodução" not in result
        assert "bilhão" in result

    def test_credito_caption_removed(self):
        text = "Crédito: AFP\nA reunião entre os líderes durou mais de três horas."
        result = _clean_rss_text("", text)
        assert "AFP" not in result
        assert "reunião" in result


class TestNavigationSections:
    def test_leia_tambem_section_removed(self):
        text = (
            "O Brasil registrou crescimento econômico no trimestre.\n"
            "LEIA TAMBÉM:\n"
            "Veja os dados do PIB segundo o IBGE\n"
        )
        result = _clean_rss_text("", text)
        assert "LEIA TAMBÉM" not in result
        assert "Brasil" in result

    def test_nossos_videos_section_removed(self):
        text = (
            "Fãs de Chainsaw Man comemoram novidades do estúdio Mappa.\n"
            "Nossos vídeos em destaque\n"
            "Trailer da segunda temporada\n"
        )
        result = _clean_rss_text("", text)
        assert "vídeos em destaque" not in result
        assert "Chainsaw Man" in result

    def test_assista_videos_section_removed(self):
        text = (
            "Irmã do humorista Renato Aragão faleceu neste domingo.\n"
            "Assista aos vídeos mais vistos do Ceará:\n"
            "Vídeo 1: Título ignorado\n"
        )
        result = _clean_rss_text("", text)
        assert "Assista" not in result
        assert "Renato Aragão" in result

    def test_section_resumes_after_blank_line(self):
        text = (
            "Conteúdo antes da seção relevante.\n"
            "LEIA TAMBÉM:\n"
            "Link que deve ser ignorado\n"
            "\n"
            "Conteúdo após a seção deve aparecer normalmente.\n"
        )
        result = _clean_rss_text("", text)
        assert "Link que deve ser ignorado" not in result
        assert "Conteúdo após" in result


class TestPromoLines:
    def test_emoji_compre_removed(self):
        text = (
            "A Fast Shop cortou o preço do PlayStation 5 Slim Digital.\n"
            "👉 Compre agora o PS5 Slim Digital por R$ 3.219 na Fast Shop\n"
            "O PlayStation 5 Slim entrega o melhor desempenho da geração."
        )
        result = _clean_rss_text("", text)
        assert "Compre agora" not in result
        assert "Fast Shop cortou" in result

    def test_emoji_garanta_removed(self):
        text = (
            "Promoção imperdível de eletrônicos no e-commerce nacional.\n"
            "✅ Garanta o seu com desconto exclusivo de 30% hoje\n"
        )
        result = _clean_rss_text("", text)
        assert "Garanta o seu" not in result


class TestEdgeCases:
    def test_empty_text_returns_empty(self):
        assert _clean_rss_text("Título", "") == ""

    def test_none_equivalent_empty_returns_empty(self):
        assert _clean_rss_text("", "") == ""

    def test_only_boilerplate_returns_empty(self):
        text = "Por Autor |\nFoto: Agência"
        result = _clean_rss_text("", text)
        assert result == ""

    def test_clean_text_preserved(self):
        text = "O Brasil registrou crescimento econômico no primeiro trimestre de 2026 segundo o IBGE."
        result = _clean_rss_text("", text)
        assert "Brasil" in result
        assert "IBGE" in result

    def test_multiline_clean_text_preserved(self):
        text = (
            "A inflação medida pelo IPCA ficou em 5,2% nos últimos doze meses.\n"
            "O Banco Central sinalizou nova alta da taxa de juros na próxima reunião do Copom."
        )
        result = _clean_rss_text("", text)
        assert "inflação" in result
        assert "Banco Central" in result
