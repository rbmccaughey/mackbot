from datetime import date

from config import BookingConfig, KANANASKIS, CALGARY, VALLEY_RIDGE, SITES


class TestBookingConfig:
    def test_course_ids_populated_from_site_when_empty(self):
        cfg = BookingConfig(target_date=date(2026, 6, 15), site=KANANASKIS)
        assert cfg.course_ids == [1, 2]

    def test_explicit_course_ids_not_overridden(self):
        cfg = BookingConfig(target_date=date(2026, 6, 15), site=KANANASKIS, course_ids=[1])
        assert cfg.course_ids == [1]

    def test_default_num_players_is_4(self):
        cfg = BookingConfig(target_date=date(2026, 6, 15), site=KANANASKIS)
        assert cfg.num_players == 4

    def test_default_poll_interval(self):
        cfg = BookingConfig(target_date=date(2026, 6, 15), site=KANANASKIS)
        assert cfg.poll_interval_secs == 300

    def test_calgary_course_ids_from_site(self):
        cfg = BookingConfig(target_date=date(2026, 6, 15), site=CALGARY)
        assert cfg.course_ids == CALGARY.course_ids


class TestSiteConfigs:
    def test_all_three_sites_present(self):
        assert "kananaskis" in SITES
        assert "calgary" in SITES
        assert "valley_ridge" in SITES

    def test_kananaskis_requires_payment_with_deposit(self):
        assert KANANASKIS.requires_payment is True
        assert KANANASKIS.deposit_amount == 35

    def test_kananaskis_courses_are_lorette_and_kidd(self):
        assert KANANASKIS.course_ids == [1, 2]

    def test_kananaskis_class_code(self):
        assert KANANASKIS.class_code == "ABRES"

    def test_calgary_no_payment_required(self):
        assert CALGARY.requires_payment is False
        assert CALGARY.deposit_amount == 0

    def test_calgary_platform_is_cps(self):
        assert CALGARY.platform == "cps"

    def test_valley_ridge_platform_is_tcu(self):
        assert VALLEY_RIDGE.platform == "tcu"

    def test_valley_ridge_no_payment(self):
        assert VALLEY_RIDGE.requires_payment is False

    def test_sites_dict_returns_correct_objects(self):
        assert SITES["kananaskis"] is KANANASKIS
        assert SITES["calgary"] is CALGARY
        assert SITES["valley_ridge"] is VALLEY_RIDGE
