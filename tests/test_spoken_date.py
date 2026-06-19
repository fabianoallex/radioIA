from datetime import date

from serve import _spoken_date


class TestSpokenDate:
    def test_first_day_uses_primeiro(self):
        # 1º de janeiro de 2026 é quinta-feira
        d = date(2026, 1, 1)
        result = _spoken_date(d)
        assert 'primeiro' in result

    def test_day_31(self):
        d = date(2026, 1, 31)
        assert 'trinta e um' in _spoken_date(d)

    def test_month_name_in_result(self):
        d = date(2026, 6, 18)
        assert 'junho' in _spoken_date(d)

    def test_weekday_in_result(self):
        # 18 de junho de 2026 é quinta-feira
        d = date(2026, 6, 18)
        assert 'quinta-feira' in _spoken_date(d)

    def test_year_2000(self):
        d = date(2000, 3, 15)
        assert 'dois mil' in _spoken_date(d)
        assert 'dois mil e' not in _spoken_date(d)

    def test_year_single_digit(self):
        # 2001
        d = date(2001, 1, 1)
        assert 'dois mil e um' in _spoken_date(d)

    def test_year_teen(self):
        # 2015 → "dois mil e quinze"
        d = date(2015, 7, 10)
        assert 'dois mil e quinze' in _spoken_date(d)

    def test_year_round_tens(self):
        # 2020 → "dois mil e vinte"
        d = date(2020, 3, 20)
        assert 'dois mil e vinte' in _spoken_date(d)

    def test_year_compound(self):
        # 2026 → "dois mil e vinte e seis"
        d = date(2026, 6, 18)
        assert 'dois mil e vinte e seis' in _spoken_date(d)

    def test_result_starts_with_hoje_e(self):
        d = date(2026, 6, 18)
        assert _spoken_date(d).startswith('hoje é')

    def test_saturday(self):
        # 20 de junho de 2026 é sábado
        d = date(2026, 6, 20)
        assert 'sábado' in _spoken_date(d)

    def test_sunday(self):
        # 21 de junho de 2026 é domingo
        d = date(2026, 6, 21)
        assert 'domingo' in _spoken_date(d)

    def test_all_months_present(self):
        months_expected = [
            (1, 'janeiro'), (2, 'fevereiro'), (3, 'março'), (4, 'abril'),
            (5, 'maio'), (6, 'junho'), (7, 'julho'), (8, 'agosto'),
            (9, 'setembro'), (10, 'outubro'), (11, 'novembro'), (12, 'dezembro'),
        ]
        for month, name in months_expected:
            d = date(2026, month, 1)
            assert name in _spoken_date(d), f'Mês {month} deveria ser "{name}"'
