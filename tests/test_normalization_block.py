from src.script_generator import _build_normalization_block


class TestAlwaysPresent:
    def test_header_always_present(self):
        assert "NORMALIZAÇÃO PARA LEITURA EM VOZ ALTA" in _build_normalization_block("")

    def test_siglas_conhecidas_always_present(self):
        result = _build_normalization_block("")
        assert "Siglas conhecidas" in result
        assert "CEO" in result

    def test_siglas_desconhecidas_always_present(self):
        result = _build_normalization_block("")
        assert "Siglas desconhecidas" in result
        assert "MCP" in result

    def test_ends_with_double_newline(self):
        assert _build_normalization_block("").endswith("\n\n")


class TestNoPatterns:
    def test_no_conditional_rules_for_clean_content(self):
        content = "Toy Story 5 é um filme de aventura com personagens animados da Pixar."
        result = _build_normalization_block(content)
        assert "Moeda BRL" not in result
        assert "Percentual" not in result
        assert "Distância" not in result
        assert "Temperatura" not in result
        assert "Rodovia" not in result

    def test_only_two_rule_lines_when_no_patterns(self):
        content = "Toy Story 5 é um filme de aventura com personagens animados da Pixar."
        result = _build_normalization_block(content)
        rule_lines = [l for l in result.splitlines() if l.startswith("- ")]
        assert len(rule_lines) == 2  # só siglas conhecidas + desconhecidas

    def test_recipe_content_no_conditional(self):
        content = "Ingredientes: farinha, ovos, leite. Misture bem e asse por 30 minutos."
        result = _build_normalization_block(content)
        rule_lines = [l for l in result.splitlines() if l.startswith("- ")]
        assert len(rule_lines) == 2


class TestCurrencyRules:
    def test_brl_detected(self):
        assert "Moeda BRL" in _build_normalization_block("O produto custa R$ 29,90.")

    def test_usd_detected(self):
        assert "Moeda USD" in _build_normalization_block("A empresa vale US$ 2,5 bilhões.")

    def test_brl_not_injected_without_symbol(self):
        assert "Moeda BRL" not in _build_normalization_block("O produto custa vinte reais.")

    def test_usd_not_injected_without_symbol(self):
        assert "Moeda USD" not in _build_normalization_block("O câmbio do dólar subiu hoje.")


class TestMeasureRules:
    def test_percent_detected(self):
        assert "Percentual" in _build_normalization_block("A inflação subiu 5% no mês.")

    def test_km_detected(self):
        assert "Distância" in _build_normalization_block("O carro atingiu 120 km/h na rodovia.")

    def test_km_not_detected_without_word_boundary(self):
        # "km" dentro de outra palavra não deve disparar
        assert "Distância" not in _build_normalization_block("kilometragem não está aqui")

    def test_area_m2_detected(self):
        assert "Área/volume" in _build_normalization_block("O apartamento tem 80 m² de área útil.")

    def test_temperature_celsius_detected(self):
        assert "Temperatura" in _build_normalization_block("A temperatura chegou a 38°C em São Paulo.")

    def test_time_h_format_detected(self):
        assert "Tempo" in _build_normalization_block("O programa vai ao ar às 3h45 da manhã.")

    def test_time_colon_format_detected(self):
        assert "Tempo" in _build_normalization_block("O jogo começa às 09:30 no estádio.")

    def test_date_detected(self):
        assert "Data" in _build_normalization_block("O evento ocorreu em 21/06/2026.")

    def test_rodovia_br_detected(self):
        assert "Rodovia" in _build_normalization_block("Acidente grave na BR-163 no Mato Grosso.")

    def test_rodovia_sp_detected(self):
        assert "Rodovia" in _build_normalization_block("Obra na SP-330 afeta trânsito na região.")

    def test_ordinal_masculino_detected(self):
        assert "Ordinal" in _build_normalization_block("O 1º colocado recebeu o prêmio principal.")

    def test_ordinal_feminino_detected(self):
        assert "Ordinal" in _build_normalization_block("A 2ª edição do festival foi um sucesso.")

    def test_tech_5g_detected(self):
        assert "Tecnologia" in _build_normalization_block("O novo celular suporta redes 5G de alta velocidade.")

    def test_tech_4k_detected(self):
        assert "Tecnologia" in _build_normalization_block("A TV tem resolução 4K com HDR.")

    def test_large_trilhao_detected(self):
        assert "Valores grandes" in _build_normalization_block("A dívida pública atingiu R$ 6,8 trilhões.")

    def test_large_bilhao_detected(self):
        assert "Valores grandes" in _build_normalization_block("O fundo tem 3,2 bilhões sob gestão.")


class TestMultiplePatterns:
    def test_news_content_detects_multiple_rules(self):
        content = (
            "O Banco Central elevou a SELIC para 13,75%.\n"
            "O dólar fechou em R$ 5,23 no mercado financeiro.\n"
            "Temperatura em São Paulo: 28°C na tarde desta terça.\n"
            "Acidente na BR-163 foi registrado às 07h30."
        )
        result = _build_normalization_block(content)
        assert "Percentual" in result
        assert "Moeda BRL" in result
        assert "Temperatura" in result
        assert "Rodovia" in result
        assert "Tempo" in result

    def test_conditional_rules_appear_before_siglas(self):
        content = "R$ 100,00 e 15% de desconto na loja."
        result = _build_normalization_block(content)
        assert result.index("Moeda BRL") < result.index("Siglas conhecidas")

    def test_youtube_content_detects_date_and_ordinal(self):
        # "22/06/2026" e "360º" no título CNN
        content = "AO VIVO: CNN 360º - 22/06/2026\nEspanha 3 x 1 Coreia do Sul"
        result = _build_normalization_block(content)
        assert "Data" in result
        assert "Ordinal" in result
        assert "Moeda BRL" not in result
