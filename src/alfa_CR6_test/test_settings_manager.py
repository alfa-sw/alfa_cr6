# coding: utf-8

"""
Unit tests for SettingsManager._validate_updates (and helpers).

Run with:
    python -m pytest src/alfa_CR6_test/test_settings_manager.py -v
"""

import pytest

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

    def test_valid_popup_refill(self):
        result = SettingsManager._validate_updates({"POPUP_REFILL_CHOICES": [500, 1000]})
        assert result["POPUP_REFILL_CHOICES"] == [500, 1000]

    def test_valid_boolean(self):
        result = SettingsManager._validate_updates({"ENABLE_BTN_ORDER_NEW": True})
        assert result["ENABLE_BTN_ORDER_NEW"] is True

    def test_valid_boolean_coerced_from_string(self):
        result = SettingsManager._validate_updates({"ENABLE_BTN_ORDER_NEW": "true"})
        assert result["ENABLE_BTN_ORDER_NEW"] is True

    def test_reminder_liner_defaults_to_false(self):
        assert SettingsManager.DEFAULTS["REMINDER_LINER"] is False

    def test_reminder_liner_is_docker_only(self):
        spec = SettingsManager.SCHEMA["properties"]["REMINDER_LINER"]
        assert spec["docker_only"] is True

    def test_valid_reminder_liner(self):
        result = SettingsManager._validate_updates({"REMINDER_LINER": "true"})
        assert result["REMINDER_LINER"] is True

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
