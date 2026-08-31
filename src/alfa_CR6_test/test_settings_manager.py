# coding: utf-8

"""
Unit tests for SettingsManager._validate_updates (and helpers).

Run with:
    python -m pytest src/alfa_CR6_test/test_settings_manager.py -v
"""

import sys
import types

import pytest

from alfa_CR6_backend import settings_manager
from alfa_CR6_backend.settings_manager import SettingsManager


# ---------------------------------------------------------------------------
# _normalize_updates
# ---------------------------------------------------------------------------

class TestNormalizeUpdates:

    def test_bool_string_true(self):
        for val in ("true", "True", "1", "yes", "on"):
            result = SettingsManager._normalize_updates({"FORCE_ORDER_JAR_TO_ONE": val})
            assert result["FORCE_ORDER_JAR_TO_ONE"] is True

    def test_bool_string_false(self):
        for val in ("false", "False", "0", "no", "off"):
            result = SettingsManager._normalize_updates({"FORCE_ORDER_JAR_TO_ONE": val})
            assert result["FORCE_ORDER_JAR_TO_ONE"] is False

    def test_bool_native_passthrough(self):
        result = SettingsManager._normalize_updates({"ENABLE_BTN_PURGE_ALL": True})
        assert result["ENABLE_BTN_PURGE_ALL"] is True

    def test_number_from_string(self):
        result = SettingsManager._normalize_updates({"MOVE_01_02_TIME_INTERVAL": "8.0"})
        assert result["MOVE_01_02_TIME_INTERVAL"] == 8.0

    def test_integer_from_string(self):
        result = SettingsManager._normalize_updates({"DOWNLOAD_KCC_LOT_STEP": "120"})
        assert result["DOWNLOAD_KCC_LOT_STEP"] == 120

    def test_array_from_json_string(self):
        result = SettingsManager._normalize_updates({"POPUP_REFILL_CHOICES": "[500, 1000]"})
        assert result["POPUP_REFILL_CHOICES"] == [500, 1000]

    def test_unknown_key_rejected(self):
        with pytest.raises(ValueError, match="Unknown setting"):
            SettingsManager._normalize_updates({"NO_SUCH_KEY": 42})

    def test_underscore_keys_skipped(self):
        result = SettingsManager._normalize_updates({"_internal": "x", "LANGUAGE": "en"})
        assert "_internal" not in result
        assert result["LANGUAGE"] == "en"


# ---------------------------------------------------------------------------
# persisted settings migrations
# ---------------------------------------------------------------------------

class TestMigrateUserSettings:

    def test_renames_legacy_reminder_liner(self):
        settings = {"REMINDER_LINER": True}

        changed = SettingsManager.migrate_user_settings(settings)

        assert changed is True
        assert settings == {"REMINDER_PPS_LINER": True}

    def test_current_name_takes_precedence(self):
        settings = {
            "REMINDER_LINER": True,
            "REMINDER_PPS_LINER": False,
        }

        changed = SettingsManager.migrate_user_settings(settings)

        assert changed is True
        assert settings == {"REMINDER_PPS_LINER": False}

    def test_no_legacy_name_is_unchanged(self):
        settings = {"REMINDER_PPS_LINER": False}

        changed = SettingsManager.migrate_user_settings(settings)

        assert changed is False
        assert settings == {"REMINDER_PPS_LINER": False}


# ---------------------------------------------------------------------------
# editable settings visibility
# ---------------------------------------------------------------------------

class TestEditableSettings:

    def test_new_default_is_visible_on_legacy_host_without_second_restart(
        self, monkeypatch
    ):
        app_settings = types.ModuleType("app_settings")

        monkeypatch.setitem(sys.modules, "app_settings", app_settings)
        monkeypatch.setattr(SettingsManager, "_in_docker", staticmethod(lambda: False))

        editable = SettingsManager.get_editable_settings()

        assert editable["REMINDER_PPS_LINER"] is False
        assert "REFILL_ALARM_NOTIFICATION" not in editable


# ---------------------------------------------------------------------------
# legacy persistence
# ---------------------------------------------------------------------------

class TestUpdateSettingsLegacy:

    def test_set_updates_saves_url_with_full_legacy_ui_payload(
        self, tmp_path, monkeypatch
    ):
        app_settings = tmp_path / "app_settings.py"
        app_settings.write_text(
            'WEBENGINE_CUSTOMER_URL = "http://old.example/"\n'
            'DOWNLOAD_KCC_LOT_STEP = 60 * 60\n'
            'FORCE_ORDER_JAR_TO_ONE = False\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(settings_manager, "CONF_PATH", str(tmp_path))
        monkeypatch.setattr(SettingsManager, "_in_docker", staticmethod(lambda: False))

        cache_invalidated = []
        globals_stub = types.ModuleType("alfa_CR6_backend.globals")
        globals_stub.invalidate_settings_cache = lambda: cache_invalidated.append(True)
        monkeypatch.setitem(sys.modules, "alfa_CR6_backend.globals", globals_stub)

        SettingsManager.set_updates({
            "WEBENGINE_CUSTOMER_URL": "https://new.example/orders",
            "DOWNLOAD_KCC_LOT_STEP": 3600,
            "FORCE_ORDER_JAR_TO_ONE": True,
        })

        assert app_settings.read_text(encoding="utf-8") == (
            "WEBENGINE_CUSTOMER_URL = 'https://new.example/orders'\n"
            "DOWNLOAD_KCC_LOT_STEP = 3600\n"
            "FORCE_ORDER_JAR_TO_ONE = True\n"
        )
        assert cache_invalidated == [True]


# ---------------------------------------------------------------------------
# _validate_updates (orchestrator)
# ---------------------------------------------------------------------------

class TestValidateUpdates:

    def test_none_returns_empty(self):
        assert SettingsManager._validate_updates(None) == {}

    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="must be a dict"):
            SettingsManager._validate_updates("not a dict")

    # --- valid cases ---

    def test_valid_move_interval(self):
        result = SettingsManager._validate_updates({"MOVE_01_02_TIME_INTERVAL": 8.0})
        assert result["MOVE_01_02_TIME_INTERVAL"] == 8.0

    @pytest.mark.parametrize("value", [7.0, 7.1, 8.1, 8.2, 8.5])
    def test_accept_move_interval_decimal_steps(self, value):
        result = SettingsManager._validate_updates({
            "MOVE_01_02_TIME_INTERVAL": value,
        })
        assert result["MOVE_01_02_TIME_INTERVAL"] == value

    def test_accept_move_interval_decimal_string(self):
        result = SettingsManager._validate_updates({
            "MOVE_01_02_TIME_INTERVAL": "8.2",
        })
        assert result["MOVE_01_02_TIME_INTERVAL"] == 8.2

    def test_valid_popup_refill(self):
        result = SettingsManager._validate_updates({"POPUP_REFILL_CHOICES": [500, 1000]})
        assert result["POPUP_REFILL_CHOICES"] == [500, 1000]

    def test_valid_boolean(self):
        result = SettingsManager._validate_updates({"ENABLE_BTN_ORDER_NEW": True})
        assert result["ENABLE_BTN_ORDER_NEW"] is True

    def test_valid_boolean_coerced_from_string(self):
        result = SettingsManager._validate_updates({"ENABLE_BTN_ORDER_NEW": "true"})
        assert result["ENABLE_BTN_ORDER_NEW"] is True

    def test_reminder_pps_liner_defaults_to_false(self):
        assert SettingsManager.DEFAULTS["REMINDER_PPS_LINER"] is False

    def test_reminder_pps_liner_is_available_on_all_machines(self):
        spec = SettingsManager.SCHEMA["properties"]["REMINDER_PPS_LINER"]
        assert spec.get("docker_only", False) is False

    def test_valid_reminder_pps_liner(self):
        result = SettingsManager._validate_updates({"REMINDER_PPS_LINER": "true"})
        assert result["REMINDER_PPS_LINER"] is True

    def test_valid_load_lifter_timeout(self):
        result = SettingsManager._validate_updates({"LOAD_LIFTER_IS_UP_LONG_TIMEOUT": 45.0})
        assert result["LOAD_LIFTER_IS_UP_LONG_TIMEOUT"] == 45.0

    def test_valid_download_kcc(self):
        result = SettingsManager._validate_updates({"DOWNLOAD_KCC_LOT_STEP": 3600})
        assert result["DOWNLOAD_KCC_LOT_STEP"] == 3600

    # --- invalid cases: schema must reject ---

    def test_reject_move_interval_too_high(self):
        with pytest.raises(ValueError):
            SettingsManager._validate_updates({"MOVE_01_02_TIME_INTERVAL": 999.0})

    def test_reject_move_interval_too_low(self):
        with pytest.raises(ValueError):
            SettingsManager._validate_updates({"MOVE_01_02_TIME_INTERVAL": 1.0})

    def test_reject_move_interval_not_on_decimal_step(self):
        with pytest.raises(ValueError):
            SettingsManager._validate_updates({
                "MOVE_01_02_TIME_INTERVAL": 8.25,
            })

    def test_reject_popup_refill_too_few_items(self):
        with pytest.raises(ValueError):
            SettingsManager._validate_updates({"POPUP_REFILL_CHOICES": [500]})

    def test_accept_popup_refill_small_values(self):
        result = SettingsManager._validate_updates({"POPUP_REFILL_CHOICES": [1, 2]})
        assert result["POPUP_REFILL_CHOICES"] == [1, 2]

    def test_reject_popup_refill_items_below_minimum(self):
        with pytest.raises(ValueError):
            SettingsManager._validate_updates({"POPUP_REFILL_CHOICES": [0, 2]})

    def test_reject_load_lifter_negative(self):
        with pytest.raises(ValueError):
            SettingsManager._validate_updates({"LOAD_LIFTER_IS_UP_LONG_TIMEOUT": -5})

    def test_reject_download_kcc_too_high(self):
        with pytest.raises(ValueError):
            SettingsManager._validate_updates({"DOWNLOAD_KCC_LOT_STEP": 999999})

    def test_reject_boolean_garbage_string(self):
        with pytest.raises(ValueError):
            SettingsManager._validate_updates({"USE_PIGMENT_ID_AS_BARCODE": "banana"})

    def test_reject_unknown_key(self):
        with pytest.raises(ValueError, match="Unknown setting"):
            SettingsManager._validate_updates({"INVENTED_KEY": 123})

    # --- regression: the original bug ---

    def test_regression_schema_error_not_swallowed(self):
        """The original bug: except Exception swallowed ValueError from
        jsonschema validation, falling through to a permissive fallback.
        MOVE_01_02_TIME_INTERVAL=3000 must be rejected (schema max is 8.5),
        not accepted by a fallback with max 3600."""
        with pytest.raises(ValueError):
            SettingsManager._validate_updates({"MOVE_01_02_TIME_INTERVAL": 3000})
