# coding: utf-8

import os
import json
import logging
import sys
import re
import traceback

from typing_extensions import Literal

CONF_PATH = "/opt/alfa_cr6/conf"



class SettingsManager:

    SETTING_RENAMES = {
        'REMINDER_LINER': 'REMINDER_PPS_LINER',
    }

    SCHEMA = {
        '$schema': 'http://json-schema.org/draft-06/schema#',
        'type': 'object',
        'properties': {
            'WEBENGINE_CUSTOMER_URL': {
                'type': 'string',
                'format': 'uri',
                'default': 'http://alfadispenser.com/',
            },
            'LANGUAGE': {
                'type': 'string',
                'default': 'it',
                'ui_show': False,
            },
            'USE_PIGMENT_ID_AS_BARCODE': {
                'type': 'boolean',
                'default': True,
            },
            'LOAD_LIFTER_IS_UP_LONG_TIMEOUT': {
                'type': 'number',
                'minimum': 30.3,
                'maximum': 100,
                'default': 90.0,
                'description': 'Timeout in secs (30.3 - 99.3)',
                'ui_error': 'Error: value must be between 30.3 and 99.3 secs',
            },
            'MOVE_01_02_TIME_INTERVAL': {
                'type': 'number',
                'minimum': 7.0,
                'maximum': 8.5,
                'default': 8.0,
                'multipleOf': 0.1,
                'description': 'Time interval in seconds (7.0 - 8.5) for the shuttle to travel from INPUT ROLLER PHOTOCELL to HEAD A PHOTOCELL',
                'ui_error': 'Error: value must be between 7.0 and 8.5 secs',
            },
            'FORCE_ORDER_JAR_TO_ONE': {
                'type': 'boolean',
                'default': False,
                'description': 'When enabled, creating multiple jars for the same order is not more allowed.'
            },
            'ENABLE_BTN_PURGE_ALL': {
                'type': 'boolean',
                'default': False,
            },
            'ENABLE_BTN_ORDER_NEW': {
                'type': 'boolean',
                'default': True,
            },
            'ENABLE_BTN_ORDER_CLONE': {
                'type': 'boolean',
                'default': True,
            },
            'MANUAL_BARCODE_INPUT': {
                'type': 'boolean',
                'default': False,
                'description': 'Enables manual entry of an order barcode in case the roller input barcode scanner is not working.',
            },
            'REMINDER_PPS_LINER': {
                'type': 'boolean',
                'default': False,
                'docker_only': True,
                'description': 'When enabled, shows a PPS liner reminder while the shuttle starts feeding a jar.',
            },
            'SKIP_FREEZE_ON_UNKNOWN_PIGMENTS': {
                'type': 'boolean',
                'default': False,
                'description': 'When enabled, jars with only unknown pigments (to be added by hand) show an alert but do not freeze the carousel. Does not apply if insufficient pigments are also present.',
            },
            'POPUP_REFILL_CHOICES': {
                'type': 'array',
                'minItems': 2,
                'maxItems': 5,
                'items': {
                    'type': 'integer',
                    'minimum': 1,
                    'ui_error': 'Each value must be ≥ 1',
                },
                'default': [500, 1000],
                'description': 'Defines the available choices displayed in the HMI refill popup.',
                'ui_error': 'Error: it must contain numeric values (integers or floats) with at least 2 elements and no more than 5 elements.',
            },
            'DOWNLOAD_KCC_LOT_STEP': {
                'type': 'integer',
                'minimum': 0,
                'maximum': 4000,
                'default': 0,
                'description': 'Interval of time (in secs) to download lot lot specific info from KCC site. 0 means disabled; maximum value 4000',
            },
            'TROUBLESHOOTING': {
                'type': 'boolean',
                'default': True,
                'description': 'When enabled, the alarm popup shows an "Info" button that opens a web page with the error description and resolution.',
            },
            'REFILL_ALARM_NOTIFICATION': {
                'type': 'object',
                'docker_only': True,
                'properties': {
                    'enabled': {'type': 'boolean'},
                    'sound': {'type': 'string', 'enum': ['fast_beep', 'slow_beep']},
                    'timeout': {'type': 'integer', 'minimum': 10, 'maximum': 120},
                    'sound_level': {'type': 'string', 'enum': ['auto', '100%', '75%', '50%']},
                },
                'required': ['enabled', 'sound', 'timeout'],
                'additionalProperties': False,
                'default': {'enabled': False, 'sound': 'fast_beep', 'timeout': 30, 'sound_level': 'auto'},
                'description': 'Refill alarm notification played on the monitor speakers (snowball machines only). '
                               'sound: "fast_beep" (200ms beep / 300ms pause) or "slow_beep" (800ms beep / 1200ms pause); '
                               'timeout: seconds (10-120) after which the sound stops by itself; '
                               'sound_level: for now only "auto" is offered (the host already drives a safe per-monitor '
                               'volume: QinHeng/0x000F units to 40% via DDC/CI). The percent options are deferred: raising '
                               'the volume is safe only with the monitor dedicated power supply, so they will be re-enabled '
                               'once the PSU requirement is handled.',
                'ui_error': 'Error: expected {"enabled": true|false, "sound": "fast_beep"|"slow_beep", "timeout": 10..120, "sound_level": "auto"|"100%"|"75%"|"50%"}',
            },
        },
    }

    DEFAULTS = {
        k: v.get('default')
        for k, v in SCHEMA.get('properties', {}).items()
        if 'default' in v
    }

    @staticmethod
    def _in_docker() -> bool:
        return os.getenv('IN_DOCKER', False) in ['1', 'true']
        # return False

    @staticmethod
    def save_user_settings(filename, user_settings_dict):
        try:
            with open(filename, "w") as f:
                f.write(json.dumps(user_settings_dict))
        except:
            logging.error("unable to save user settings")
            traceback.print_exc(file=sys.stderr)

    @staticmethod
    def migrate_user_settings(user_settings: dict) -> bool:
        """Rename deprecated persisted settings in place.

        If both names are present, the current name takes precedence.
        Returns True when at least one deprecated key was removed.
        """
        changed = False
        for old_name, new_name in SettingsManager.SETTING_RENAMES.items():
            if old_name not in user_settings:
                continue
            if new_name not in user_settings:
                user_settings[new_name] = user_settings[old_name]
            del user_settings[old_name]
            changed = True
        return changed

    @staticmethod
    def _update_settings_in_docker(
        updates: dict,
        mode: Literal["align", "overwrite"]
    ):
        sys.path.append(CONF_PATH)
        try:
            import app_settings as s  # pylint: disable=import-error,import-outside-toplevel
        finally:
            sys.path.remove(CONF_PATH)

        fn = s.USER_SETTINGS_JSON_FILE
        us = s.USER_SETTINGS
        changed = False

        for k, v in (updates or {}).items():
            if k.startswith("_"):
                continue
            
            should_update = (
                (mode == "align" and k not in us) or
                (mode == "overwrite" and us.get(k) != v)
            )

            if not should_update:
                continue
            old_val = us.get(k)
            us[k] = v
            changed = True

            msg = (
                f"added missing setting {k!r}: {v!r}"
                if old_val is None
                else f"updated setting {k!r}: {old_val!r} -> {v!r}"
            )
            logging.warning(msg)

        if changed:
            SettingsManager.save_user_settings(fn, us)

    @staticmethod
    def _update_settings_legacy(
        updates: dict,
        mode: Literal["align", "overwrite"] = "overwrite",
    ) -> bool:

        path_app_settings = os.path.join(CONF_PATH, "app_settings.py")
        if not os.path.exists(path_app_settings):
            raise RuntimeError(f"Missing app_settings.py file in path {CONF_PATH!r}")

        with open(path_app_settings, "r", encoding="utf-8") as f:
            content = f.read()

        changed = False

        for k, v in (updates or {}).items():
            if k.startswith("_"):
                continue

            try:
                if isinstance(v, str):
                    try:
                        v = json.loads(v)
                    except Exception:
                        pass
                new_val = repr(v)
            except Exception:
                new_val = repr(str(v))

            key_re = re.escape(k)
            pattern = rf'^(\s*{key_re}\s*=\s*)(.*)$'
            m = re.search(pattern, content, flags=re.MULTILINE)

            if mode == "align":
                if not m:
                    content += f"\n{k} = {new_val}\n"
                    logging.warning("host: add missing setting %r -> %s", k, new_val)
                    changed = True
                continue

            # mode == "overwrite"
            if m:
                current_val_txt = m.group(2).strip()
                if current_val_txt != new_val:
                    # A replacement string such as ``\1`` + ``3600`` is parsed
                    # by re.sub as a (non-existent) group reference ``\13600``.
                    # A callable also keeps backslashes in string values literal.
                    content = re.sub(
                        pattern,
                        lambda match, value=new_val: match.group(1) + value,
                        content,
                        count=1,
                        flags=re.MULTILINE,
                    )
                    logging.warning("host: update %r: %s -> %s", k, current_val_txt, new_val)
                    changed = True
            else:
                content += f"\n{k} = {new_val}\n"
                logging.warning("host: add new setting %r -> %s", k, new_val)
                changed = True

        if changed:
            with open(path_app_settings, "w", encoding="utf-8") as f:
                f.write(content)

        return changed

    # ---------- backends: set ----------
    @staticmethod
    def _set_settings_in_docker(updates: dict):
        SettingsManager._update_settings_in_docker(updates, "overwrite")

    @staticmethod
    def _set_settings_on_host(updates: dict):

        SettingsManager._update_settings_legacy(updates, "overwrite")

    @staticmethod
    def get_editable_settings() -> dict:

        sys.path.append(CONF_PATH)
        try:
            import app_settings as s  # pylint: disable=import-error,import-outside-toplevel
        finally:
            sys.path.remove(CONF_PATH)

        properties = SettingsManager.SCHEMA.get('properties', {})
        editable_keys = set(properties.keys())
        visible_keys = {
            k for k, spec in properties.items()
            if spec.get('ui_show', True)
            and (SettingsManager._in_docker() or not spec.get('docker_only'))
        }

        if hasattr(s, "USER_SETTINGS") and isinstance(getattr(s, "USER_SETTINGS"), dict):
            source = dict(getattr(s, "USER_SETTINGS"))
        else:
            source = {k: getattr(s, k) for k in editable_keys if hasattr(s, k)}

        filtered = {k: v for k, v in source.items() if k in editable_keys and k in visible_keys}

        return filtered

    # ---------- API pubblica ----------
    @staticmethod
    def _normalize_updates(updates: dict) -> dict:
        """Coercizione leggera dei tipi per migliorare la UX dell'API.

        - stringhe booleane ("true"/"false"/...) -> bool
        - numeri passati come stringa -> int/float
        - array JSON passati come stringa -> list
        Non modifica il dict originale.
        """
        known_keys = set(SettingsManager.SCHEMA.get('properties', {}).keys())
        normalized = {}

        for key, val in updates.items():
            if key.startswith("_"):
                continue
            if key not in known_keys:
                raise ValueError(f"Unknown setting: {key!r}")

            spec = SettingsManager.SCHEMA['properties'][key]
            expected_type = spec.get('type')

            if expected_type == 'boolean' and isinstance(val, str):
                low = val.lower()
                if low in ('true', '1', 'yes', 'on'):
                    val = True
                elif low in ('false', '0', 'no', 'off'):
                    val = False

            elif expected_type == 'number' and isinstance(val, str):
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    pass

            elif expected_type == 'integer' and isinstance(val, str):
                try:
                    val = int(val)
                except (ValueError, TypeError):
                    pass

            elif expected_type == 'array' and isinstance(val, str):
                try:
                    val = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass

            elif expected_type == 'object' and isinstance(val, str):
                try:
                    val = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass

            normalized[key] = val

        return normalized

    @staticmethod
    def _validate_against_schema(updates: dict):
        """Valida updates contro lo SCHEMA. Alza ValueError se invalido."""
        try:
            from jsonschema import Draft6Validator  # pylint: disable=import-outside-toplevel
        except ImportError:
            raise RuntimeError(
                "jsonschema is required to validate settings "
                "(listed in setup.py install_requires)"
            )

        validator = Draft6Validator(SettingsManager.SCHEMA)
        errors = []
        for key, val in updates.items():
            for err in validator.iter_errors({key: val}):
                spec = SettingsManager.SCHEMA['properties'].get(key, {})
                ui_msg = spec.get('ui_error')
                errors.append(ui_msg if ui_msg else f"{key}: {err.message}")
        if errors:
            raise ValueError('; '.join(errors))

    @staticmethod
    def _validate_updates(updates: dict) -> dict:
        """Normalizza e valida gli updates contro lo schema.
        Ritorna una copia normalizzata. Alza ValueError se invalido.
        """
        if updates is None:
            return {}
        if not isinstance(updates, dict):
            raise ValueError('updates must be a dict')

        normalized = SettingsManager._normalize_updates(dict(updates))
        SettingsManager._validate_against_schema(normalized)
        return normalized

    @staticmethod
    def ensure_missing_defaults():

        defaults = SettingsManager.DEFAULTS
        logging.warning(f"jsonschema settings defaults: {defaults}")
        if SettingsManager._in_docker():
            SettingsManager._update_settings_in_docker(defaults, "align")
        else:
            # i setting docker_only (es. REFILL_ALARM_NOTIFICATION) non hanno
            # senso sulle macchine host/legacy: non vanno aggiunti al loro conf
            host_defaults = {
                k: v for k, v in defaults.items()
                if not SettingsManager.SCHEMA['properties'][k].get('docker_only')
            }
            SettingsManager._update_settings_legacy(host_defaults, "align")

    @staticmethod
    def set_updates(updates: dict):

        safe_updates = SettingsManager._validate_updates(dict(updates or {}))
        if SettingsManager._in_docker():
            SettingsManager._set_settings_in_docker(safe_updates)
        else:
            SettingsManager._set_settings_on_host(safe_updates)

        from alfa_CR6_backend.globals import (  # pylint: disable=import-outside-toplevel
            invalidate_settings_cache,
        )
        invalidate_settings_cache()
