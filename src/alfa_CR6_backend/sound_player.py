# coding: utf-8

"""
Client del router audio host.

Il container NON riproduce audio (la sua alsa-lib 1.2.2 corrompe la
conversione iec958 oltre una soglia di livello): copia i .wav nella
directory condivisa col host, dove alfa-audio-player (event-driven,
svegliato da una systemd path unit) li suona su HDMI.

Protocollo sul filesystem:
  - <nome>.wav       -> riprodotto una volta, in ordine di arrivo (FIFO)
  - <nome>.loop.wav  -> ripetuto finche' non arriva STOP
  - STOP             -> tace subito qualunque suono e svuota la coda
"""

import logging
import math
import os
import shutil
import struct
import threading
import traceback
import wave

from alfa_CR6_backend.globals import import_settings

STOP_FILENAME = 'STOP'
DEFAULT_AUDIO_SHARE_PATH = '/tmp/share/alfa_audio'

# Parametri scelti dopo i test al banco .91/.76 (2026-07-06/08): tono 2200 Hz
# amp 18000 (~55% FS) — 2200 Hz rende percettivamente di piu' di 1000 Hz sugli
# speaker piccoli, e con l'ampiezza tenuta a 18000 resta sotto la soglia di
# collasso HPD/brownout del lotto fragile (0x000F/QinHeng), dove i profili
# "caldi" (amp 24-28k) facevano crollare lo scaler. Validato a orecchio e
# strumenti su 0x0003 @ volume 80.
# La durata e' un multiplo intero del periodo bip+pausa: il file viene
# riprodotto in loop dal player host e il ritmo non deve saltare in giunzione.
REFILL_ALARM_SOUNDS = {
    'fast_beep': {'beep_ms': 200, 'silence_ms': 300, 'duration_s': 2.0},
    'slow_beep': {'beep_ms': 800, 'silence_ms': 1200, 'duration_s': 4.0},
}
REFILL_ALARM_FREQ_HZ = 2200
REFILL_ALARM_AMPLITUDE = 18000
# comando di volume per il player host (che ha il DDC; il container no):
# file SETVOL_<n> accodato PRIMA del wav -> l'host lo applica a coda ferma
SETVOL_PREFIX = 'SETVOL_'
MONITOR_STATUS_FILENAME = '.monitor_status'
_REFILL_STOP_TIMER = None


def _audio_share_path():

    settings = import_settings()
    return getattr(settings, 'AUDIO_SHARE_PATH', DEFAULT_AUDIO_SHARE_PATH)


def play_sound(wav_path, loop=False):

    """Accoda un .wav al player host; loop=True lo fa ripetere fino a stop_sound().
    Ritorna True se il file e' stato accodato, False su errore (mai eccezioni:
    un suono che non parte non deve rompere il chiamante)."""

    try:
        share_path = _audio_share_path()
        os.makedirs(share_path, exist_ok=True)

        name = os.path.basename(wav_path)
        if loop and not name.endswith('.loop.wav'):
            base, _ = os.path.splitext(name)
            name = base + '.loop.wav'

        # copia su nome temporaneo + rename atomico: il player pesca "*.wav"
        # per mtime e non deve mai vedere un file scritto a meta'
        dst = os.path.join(share_path, name)
        tmp = dst + '.part'
        shutil.copyfile(wav_path, tmp)
        os.replace(tmp, dst)
        return True
    except Exception:  # pylint: disable=broad-except
        logging.error(traceback.format_exc())
        return False


def stop_sound():

    """Tace subito qualunque suono e svuota la coda del player host.
    Ritorna True se lo STOP e' stato scritto."""

    try:
        share_path = _audio_share_path()
        os.makedirs(share_path, exist_ok=True)
        with open(os.path.join(share_path, STOP_FILENAME), 'w'):
            pass
        return True
    except Exception:  # pylint: disable=broad-except
        logging.error(traceback.format_exc())
        return False


def monitor_supports_ddc():

    """True se l'host ha rilevato un monitor comandabile via DDC/CI.
    Lo stato lo scrive alfa-audio-volume (host) nel file .monitor_status
    della directory condivisa, al boot e ad ogni hotplug."""

    try:
        with open(os.path.join(_audio_share_path(), MONITOR_STATUS_FILENAME)) as f:
            return 'ddc=1' in f.read()
    except OSError:
        return False


def _ensure_refill_wav(sound_name):

    """Sintetizza (una volta, poi cache su disco) il wav del suono refill
    richiesto in TMP_PATH. Ritorna il path o None se il nome e' sconosciuto."""

    spec = REFILL_ALARM_SOUNDS.get(sound_name)
    if not spec:
        logging.error(f"unknown refill alarm sound: {sound_name}")
        return None

    settings = import_settings()
    # freq/amp nel nome: cambiando i parametri la cache si invalida da sola
    out_name = f'refill_{sound_name}_{REFILL_ALARM_FREQ_HZ}_{REFILL_ALARM_AMPLITUDE}.wav'
    out_path = os.path.join(getattr(settings, 'TMP_PATH', '/tmp'), out_name)
    if os.path.exists(out_path):
        return out_path

    frame_rate = 48000
    beep_n = int(frame_rate * spec['beep_ms'] / 1000)
    period_n = beep_n + int(frame_rate * spec['silence_ms'] / 1000)
    buf = bytearray()
    for i in range(int(frame_rate * spec['duration_s'])):
        s = 0
        if (i % period_n) < beep_n:
            s = int(REFILL_ALARM_AMPLITUDE * math.sin(2 * math.pi * REFILL_ALARM_FREQ_HZ * i / frame_rate))
        buf += struct.pack('<hh', s, s)

    with wave.open(out_path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(frame_rate)
        w.writeframes(bytes(buf))
    return out_path


def play_refill_alarm():

    """Suona (in loop) la notifica refill secondo il setting
    REFILL_ALARM_NOTIFICATION {enabled, sound, timeout}: parte solo se
    enabled, sceglie fast_beep/slow_beep e si ferma da sola dopo 'timeout'
    secondi (o con stop_refill_alarm()). Ritorna True se il suono e' partito."""

    global _REFILL_STOP_TIMER  # pylint: disable=global-statement

    try:
        settings = import_settings()
        cfg = getattr(settings, 'REFILL_ALARM_NOTIFICATION', None) or {}
        if not cfg.get('enabled'):
            return False

        # sound_level: volume OSD del monitor applicato dall'host PRIMA del
        # suono ('auto' = non toccare). Il comando viaggia come file SETVOL_<n>
        # accodato prima del wav: il player host li processa in ordine e non
        # cambia mai il volume durante una riproduzione. Solo per monitor DDC.
        level = str(cfg.get('sound_level', 'auto')).rstrip('%')
        if level != 'auto' and level.isdigit() and monitor_supports_ddc():
            share_path = _audio_share_path()
            os.makedirs(share_path, exist_ok=True)
            with open(os.path.join(share_path, SETVOL_PREFIX + level), 'w'):
                pass

        wav_path = _ensure_refill_wav(cfg.get('sound', 'fast_beep'))
        if not wav_path or not play_sound(wav_path, loop=True):
            return False

        timeout = cfg.get('timeout', 30)
        if _REFILL_STOP_TIMER is not None:
            _REFILL_STOP_TIMER.cancel()
        # allo scadere passa da stop_refill_alarm (non stop_sound diretto):
        # cosi' il timer si azzera e lo stop ha un'unica strada
        _REFILL_STOP_TIMER = threading.Timer(timeout, stop_refill_alarm)
        _REFILL_STOP_TIMER.daemon = True
        _REFILL_STOP_TIMER.start()
        return True
    except Exception:  # pylint: disable=broad-except
        logging.error(traceback.format_exc())
        return False


def stop_refill_alarm():

    """Ferma subito la notifica refill (e il suo timer di timeout)."""

    global _REFILL_STOP_TIMER  # pylint: disable=global-statement

    if _REFILL_STOP_TIMER is not None:
        _REFILL_STOP_TIMER.cancel()
        _REFILL_STOP_TIMER = None
    return stop_sound()
