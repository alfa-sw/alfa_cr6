import os
import json
import logging
import sys
import re
import traceback

from typing_extensions import Literal

CONF_PATH = "/opt/alfa_cr6/conf"



class SettingsManager:

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
            },
            'USE_PIGMENT_ID_AS_BARCODE': {
                'type': 'boolean',
                'default': True,
            },
            'LOAD_LIFTER_IS_UP_LONG_TIMEOUT': {
                'type': 'number',
                'minimum': 30.3,
                'default': 90.0,
            },
            'MOVE_01_02_TIME_INTERVAL': {
                'type': 'number',
                'minimum': 7.0,
                'maximum': 8.5,
                'default': 8.0,
            },
            'FORCE_ORDER_JAR_TO_ONE': {
                'type': 'boolean',
                'default': False,
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
            },
            'POPUP_REFILL_CHOICES': {
                'type': 'array',
                'minItems': 2,
                'maxItems': 5,
                'items': {
                    'type': 'integer',
                    'minimum': 50
                },
                'default': [500, 1000]
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

        path_app_settings = "/opt/alfa_cr6/conf/app_settings.py"
        if not os.path.exists(path_app_settings):
            raise RuntimeError("Missing app_settings.py file in path '/opt/alfa_cr6/conf/'")

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
                    replacement = rf'\1{new_val}'
                    content = re.sub(pattern, replacement, content, count=1, flags=re.MULTILINE)
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

        editable_keys = set(SettingsManager.SCHEMA.get('properties', {}).keys())

        if hasattr(s, "USER_SETTINGS") and isinstance(getattr(s, "USER_SETTINGS"), dict):
            source = dict(getattr(s, "USER_SETTINGS"))
        else:
            source = {k: getattr(s, k) for k in editable_keys if hasattr(s, k)}

        filtered = {k: v for k, v in source.items() if k in editable_keys}

        return filtered

    # ---------- API pubblica ----------
    @staticmethod
    def _validate_updates(updates: dict) -> dict:
        """Valida (e coercede leggermente) gli updates contro lo schema.
        Ritorna una copia possibilmente coerced. Alza ValueError se invalido.
        """
        if updates is None:
            return {}
        if not isinstance(updates, dict):
            raise ValueError('updates must be a dict')

        # Prova con jsonschema se disponibile
        try:
            from jsonschema import Draft6Validator  # type: ignore
            validator = Draft6Validator(SettingsManager.SCHEMA)
            errors = []
            for key, val in updates.items():
                if key in SettingsManager.SCHEMA['properties']:
                    for err in validator.iter_errors({key: val}):
                        errors.append(f"{key}: {err.message}")
            if errors:
                raise ValueError('Invalid settings: ' + '; '.join(errors))
        except Exception:
            # Fallback minimale
            for key, val in list(updates.items()):
                if key == 'MOVE_01_02_TIME_INTERVAL':
                    try:
                        ival = int(val)
                        if ival < 1 or ival > 3600:
                            raise ValueError
                        updates[key] = ival
                    except Exception:
                        raise ValueError('MOVE_01_02_TIME_INTERVAL must be integer in [1,3600]')
                elif key in (
                    'FORCE_ORDER_JAR_TO_ONE',
                    'ENABLE_BTN_PURGE_ALL',
                    'ENABLE_BTN_ORDER_NEW',
                    'ENABLE_BTN_ORDER_CLONE',
                    'MANUAL_BARCODE_INPUT',
                ):
                    if isinstance(val, str):
                        if val.lower() in ('true', '1', 'yes', 'on'):
                            updates[key] = True
                        elif val.lower() in ('false', '0', 'no', 'off'):
                            updates[key] = False
                    if not isinstance(updates[key], bool):
                        raise ValueError(f'{key} must be boolean')
                elif key == 'POPUP_REFILL_CHOICES':
                    if isinstance(val, str):
                        # accetta JSON testuale
                        try:
                            val = json.loads(val)
                        except Exception:
                            pass
                    if not isinstance(val, list) or not val:
                        raise ValueError('POPUP_REFILL_CHOICES must be non-empty list of positive integers')
                    coerced = []
                    for it in val:
                        ival = int(it)
                        if ival < 1:
                            raise ValueError('POPUP_REFILL_CHOICES items must be >=1')
                        coerced.append(ival)
                    updates[key] = coerced
                # Chiavi sconosciute: lasciate inalterate
        return updates

    @staticmethod
    def ensure_missing_defaults():
        """Garantisce la presenza dei default noti."""
        defaults = SettingsManager.DEFAULTS
        logging.warning(f"jsonschema settings defaults: {defaults}")
        if SettingsManager._in_docker():
            SettingsManager._update_settings_in_docker(defaults, "align")
        else:
            SettingsManager._update_settings_legacy(defaults)

    @staticmethod
    def set_updates(updates: dict):
        """Valida e applica gli updates sul backend appropriato."""
        safe_updates = SettingsManager._validate_updates(dict(updates or {}))
        if SettingsManager._in_docker():
            SettingsManager._set_settings_in_docker(safe_updates)
        else:
            SettingsManager._set_settings_on_host(safe_updates)

