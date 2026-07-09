# coding: utf-8

# pylint: disable=missing-docstring

"""
Test del client del router audio (sound_player).

CONTESTO: il container non riproduce audio; play_sound() deve solo
depositare il .wav nella directory condivisa (rename atomico, nessun
residuo .part), stop_sound() deve scrivere il file STOP. Il player
host (alfa-audio-player, build-system) fa il resto. Nessun errore deve
propagarsi al chiamante: un suono che non parte non rompe l'app.
"""

import os
import tempfile
import unittest
import wave

import alfa_CR6_backend.sound_player as sound_player


def _make_wav(path):

    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(b'\x00\x00\x00\x00' * 480)


class TestSoundPlayer(unittest.TestCase):

    def setUp(self):

        self.share_dir = tempfile.TemporaryDirectory()
        self.src_dir = tempfile.TemporaryDirectory()
        self._orig = sound_player._audio_share_path  # pylint: disable=protected-access
        sound_player._audio_share_path = lambda: self.share_dir.name  # pylint: disable=protected-access

        self.src_wav = os.path.join(self.src_dir.name, 'beep.wav')
        _make_wav(self.src_wav)

    def tearDown(self):

        sound_player._audio_share_path = self._orig  # pylint: disable=protected-access
        self.share_dir.cleanup()
        self.src_dir.cleanup()

    def test_play_sound_queues_copy(self):

        self.assertTrue(sound_player.play_sound(self.src_wav))
        dst = os.path.join(self.share_dir.name, 'beep.wav')
        self.assertTrue(os.path.isfile(dst))
        with open(self.src_wav, 'rb') as fsrc, open(dst, 'rb') as fdst:
            self.assertEqual(fsrc.read(), fdst.read())

    def test_play_sound_loop_renames(self):

        self.assertTrue(sound_player.play_sound(self.src_wav, loop=True))
        self.assertTrue(os.path.isfile(os.path.join(self.share_dir.name, 'beep.loop.wav')))
        self.assertFalse(os.path.exists(os.path.join(self.share_dir.name, 'beep.wav')))

    def test_play_sound_loop_name_already_loop(self):

        src = os.path.join(self.src_dir.name, 'alarm.loop.wav')
        _make_wav(src)
        self.assertTrue(sound_player.play_sound(src, loop=True))
        self.assertTrue(os.path.isfile(os.path.join(self.share_dir.name, 'alarm.loop.wav')))

    def test_no_partial_files_left(self):

        self.assertTrue(sound_player.play_sound(self.src_wav))
        leftovers = [f for f in os.listdir(self.share_dir.name) if f.endswith('.part')]
        self.assertEqual(leftovers, [])

    def test_play_sound_missing_source_returns_false(self):

        missing = os.path.join(self.src_dir.name, 'not_there.wav')
        self.assertFalse(sound_player.play_sound(missing))
        self.assertEqual(os.listdir(self.share_dir.name), [])

    def test_stop_sound_writes_stop(self):

        self.assertTrue(sound_player.stop_sound())
        self.assertTrue(os.path.isfile(os.path.join(self.share_dir.name, 'STOP')))

    def test_share_dir_created_if_missing(self):

        nested = os.path.join(self.share_dir.name, 'sub', 'alfa_audio')
        sound_player._audio_share_path = lambda: nested  # pylint: disable=protected-access
        self.assertTrue(sound_player.play_sound(self.src_wav))
        self.assertTrue(os.path.isfile(os.path.join(nested, 'beep.wav')))


class _FakeSettings:  # pylint: disable=too-few-public-methods

    def __init__(self, tmp_path, refill_cfg):
        self.TMP_PATH = tmp_path  # pylint: disable=invalid-name
        self.REFILL_ALARM_NOTIFICATION = refill_cfg  # pylint: disable=invalid-name


class TestRefillAlarm(unittest.TestCase):

    def setUp(self):

        self.share_dir = tempfile.TemporaryDirectory()
        self.tmp_dir = tempfile.TemporaryDirectory()
        self._orig_share = sound_player._audio_share_path  # pylint: disable=protected-access
        self._orig_import = sound_player.import_settings
        sound_player._audio_share_path = lambda: self.share_dir.name  # pylint: disable=protected-access

    def tearDown(self):

        sound_player.stop_refill_alarm()
        sound_player._audio_share_path = self._orig_share  # pylint: disable=protected-access
        sound_player.import_settings = self._orig_import
        self.share_dir.cleanup()
        self.tmp_dir.cleanup()

    def _set_cfg(self, refill_cfg):

        fake = _FakeSettings(self.tmp_dir.name, refill_cfg)
        sound_player.import_settings = lambda: fake

    def test_disabled_does_not_play(self):

        self._set_cfg({'enabled': False, 'sound': 'fast_beep', 'timeout': 10})
        self.assertFalse(sound_player.play_refill_alarm())
        self.assertEqual(os.listdir(self.share_dir.name), [])

    def test_enabled_queues_loop_wav_and_arms_timer(self):

        self._set_cfg({'enabled': True, 'sound': 'fast_beep', 'timeout': 60})
        self.assertTrue(sound_player.play_refill_alarm())
        queued = f'refill_fast_beep_{sound_player.REFILL_ALARM_FREQ_HZ}_{sound_player.REFILL_ALARM_AMPLITUDE}.loop.wav'
        self.assertTrue(os.path.isfile(os.path.join(self.share_dir.name, queued)))
        self.assertIsNotNone(sound_player._REFILL_STOP_TIMER)  # pylint: disable=protected-access
        self.assertTrue(sound_player._REFILL_STOP_TIMER.is_alive())  # pylint: disable=protected-access

    def test_production_params(self):

        # parametri scelti sul campo 2026-07-08: 2200 Hz, ampiezza 18000
        self.assertEqual(sound_player.REFILL_ALARM_FREQ_HZ, 2200)
        self.assertEqual(sound_player.REFILL_ALARM_AMPLITUDE, 18000)

    def test_slow_beep_synthesis_params(self):

        self._set_cfg({'enabled': True, 'sound': 'slow_beep', 'timeout': 60})
        self.assertTrue(sound_player.play_refill_alarm())
        queued = os.path.join(
            self.share_dir.name,
            f'refill_slow_beep_{sound_player.REFILL_ALARM_FREQ_HZ}_{sound_player.REFILL_ALARM_AMPLITUDE}.loop.wav')
        self.assertTrue(os.path.isfile(queued))
        with wave.open(queued, 'rb') as w:
            self.assertEqual(w.getframerate(), 48000)
            self.assertEqual(w.getnchannels(), 2)
            self.assertEqual(w.getnframes(), 48000 * 4)  # 2 periodi interi da 2 s

    def _write_monitor_status(self, ddc):

        with open(os.path.join(self.share_dir.name, sound_player.MONITOR_STATUS_FILENAME), 'w') as f:
            f.write(f'ddc={ddc} vendor=RTK product_code=0x000f\n')

    def _setvol_files(self):

        return [f for f in os.listdir(self.share_dir.name) if f.startswith(sound_player.SETVOL_PREFIX)]

    def test_sound_level_writes_setvol_before_wav_when_ddc(self):

        self._write_monitor_status(1)
        self._set_cfg({'enabled': True, 'sound': 'fast_beep', 'timeout': 60, 'sound_level': '75%'})
        self.assertTrue(sound_player.play_refill_alarm())
        self.assertEqual(self._setvol_files(), ['SETVOL_75'])

    def test_sound_level_auto_writes_no_setvol(self):

        self._write_monitor_status(1)
        self._set_cfg({'enabled': True, 'sound': 'fast_beep', 'timeout': 60, 'sound_level': 'auto'})
        self.assertTrue(sound_player.play_refill_alarm())
        self.assertEqual(self._setvol_files(), [])

    def test_sound_level_without_ddc_degrades_to_auto(self):

        self._write_monitor_status(0)
        self._set_cfg({'enabled': True, 'sound': 'fast_beep', 'timeout': 60, 'sound_level': '100%'})
        self.assertTrue(sound_player.play_refill_alarm())
        self.assertEqual(self._setvol_files(), [])

    def test_monitor_supports_ddc(self):

        self.assertFalse(sound_player.monitor_supports_ddc())  # file assente
        self._write_monitor_status(0)
        self.assertFalse(sound_player.monitor_supports_ddc())
        self._write_monitor_status(1)
        self.assertTrue(sound_player.monitor_supports_ddc())

    def test_unknown_sound_returns_false(self):

        self._set_cfg({'enabled': True, 'sound': 'no_such_sound', 'timeout': 10})
        self.assertFalse(sound_player.play_refill_alarm())

    def test_stop_refill_alarm_writes_stop_and_clears_timer(self):

        self._set_cfg({'enabled': True, 'sound': 'fast_beep', 'timeout': 60})
        self.assertTrue(sound_player.play_refill_alarm())
        self.assertTrue(sound_player.stop_refill_alarm())
        self.assertTrue(os.path.isfile(os.path.join(self.share_dir.name, 'STOP')))
        self.assertIsNone(sound_player._REFILL_STOP_TIMER)  # pylint: disable=protected-access

    def test_timeout_fires_stop_refill_alarm(self):

        self._set_cfg({'enabled': True, 'sound': 'fast_beep', 'timeout': 60})
        self.assertTrue(sound_player.play_refill_alarm())
        timer = sound_player._REFILL_STOP_TIMER  # pylint: disable=protected-access
        self.assertIs(timer.function, sound_player.stop_refill_alarm)
        timer.function()  # simula lo scadere del timeout
        self.assertTrue(os.path.isfile(os.path.join(self.share_dir.name, 'STOP')))
        self.assertIsNone(sound_player._REFILL_STOP_TIMER)  # pylint: disable=protected-access


class TestAttentionLedsSoundHook(unittest.TestCase):

    """L'aggancio del suono refill segue il ciclo di vita dei LED di attenzione:
    play al primo token richiesto, stop al rilascio dell'ultimo."""

    def setUp(self):

        import alfa_CR6_backend.base_application as ba  # pylint: disable=import-outside-toplevel
        self.ba = ba
        self.calls = []
        self._orig_play = ba.play_refill_alarm
        self._orig_stop = ba.stop_refill_alarm
        ba.play_refill_alarm = lambda: self.calls.append('play')
        ba.stop_refill_alarm = lambda: self.calls.append('stop')

        class _FakeApp:  # pylint: disable=too-few-public-methods
            _refill_alarm_tokens = set()

            def request_attention_led(self, head, token, reason=None):
                pass

            def release_attention_led(self, head, token, reason=None):
                pass

        self.app = _FakeApp()
        self.app._refill_alarm_tokens = set()  # pylint: disable=protected-access

    def tearDown(self):

        self.ba.play_refill_alarm = self._orig_play
        self.ba.stop_refill_alarm = self._orig_stop

    def _request(self, heads, token):
        self.ba.BaseApplication.request_attention_leds(self.app, heads, token)

    def _release(self, heads, token):
        self.ba.BaseApplication.release_attention_leds(self.app, heads, token)

    def test_play_on_first_request_stop_on_last_release(self):

        self._request(['head_a'], ('jar_refill', 'BC1', 1))
        self._request(['head_a'], ('dispense_step_refill', 'BC2', 'A', 1))
        self._release(['head_a'], ('jar_refill', 'BC1', 1))
        self.assertNotIn('stop', self.calls)
        self._release(['head_a'], ('dispense_step_refill', 'BC2', 'A', 1))
        self.assertEqual(self.calls, ['play', 'play', 'stop'])

    def test_no_heads_no_sound(self):

        self._request([], ('jar_refill', 'BC1', 1))
        self._release([], ('jar_refill', 'BC1', 1))
        self.assertEqual(self.calls, [])

    def test_release_unknown_token_does_not_stop(self):

        self._release(['head_a'], ('mai', 'visto', 0))
        self.assertEqual(self.calls, [])


class TestRefillAlarmSchema(unittest.TestCase):

    """Validazione del nuovo setting REFILL_ALARM_NOTIFICATION contro lo SCHEMA."""

    def _validate(self, value):

        from alfa_CR6_backend.settings_manager import SettingsManager  # pylint: disable=import-outside-toplevel
        return SettingsManager._validate_updates({'REFILL_ALARM_NOTIFICATION': value})  # pylint: disable=protected-access

    def test_valid_config(self):

        cfg = {'enabled': True, 'sound': 'slow_beep', 'timeout': 120}
        self.assertEqual(self._validate(cfg)['REFILL_ALARM_NOTIFICATION'], cfg)

    def test_json_string_is_normalized(self):

        out = self._validate('{"enabled": false, "sound": "fast_beep", "timeout": 10}')
        self.assertEqual(out['REFILL_ALARM_NOTIFICATION']['timeout'], 10)

    def test_timeout_out_of_range_rejected(self):

        for bad in (9, 121):
            with self.assertRaises(ValueError):
                self._validate({'enabled': True, 'sound': 'fast_beep', 'timeout': bad})

    def test_unknown_sound_rejected(self):

        with self.assertRaises(ValueError):
            self._validate({'enabled': True, 'sound': 'triple_beep', 'timeout': 30})

    def test_missing_field_rejected(self):

        with self.assertRaises(ValueError):
            self._validate({'enabled': True, 'sound': 'fast_beep'})

    def test_sound_level_valid_values(self):

        for lv in ('auto', '100%', '75%', '50%'):
            cfg = {'enabled': True, 'sound': 'fast_beep', 'timeout': 30, 'sound_level': lv}
            self.assertEqual(self._validate(cfg)['REFILL_ALARM_NOTIFICATION']['sound_level'], lv)

    def test_sound_level_invalid_rejected(self):

        with self.assertRaises(ValueError):
            self._validate({'enabled': True, 'sound': 'fast_beep', 'timeout': 30, 'sound_level': '80%'})

    def test_legacy_object_without_sound_level_accepted(self):

        # i user_settings.json esistenti sul parco non hanno sound_level:
        # non e' required, il runtime degrada ad 'auto'
        cfg = {'enabled': True, 'sound': 'slow_beep', 'timeout': 60}
        self.assertEqual(self._validate(cfg)['REFILL_ALARM_NOTIFICATION'], cfg)


if __name__ == '__main__':
    unittest.main()
