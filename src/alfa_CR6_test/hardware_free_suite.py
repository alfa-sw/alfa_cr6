# coding: utf-8

"""Entry point della suite di regressione che non richiede una CR6 reale."""

import argparse
import logging
import os
import tempfile
import unittest


CORE_TEST_MODULES = (
    # Hardware abstraction e flusso macchina.
    "alfa_CR6_test.test_machine_head_jar_size",
    "alfa_CR6_test.test_machine_head_hardware_free",
    "alfa_CR6_test.test_carousel_hardware_free",
    "alfa_CR6_test.test_application_hardware_free",
    "alfa_CR6_test.test_barcode_pipeline_hardware_free",
    "alfa_CR6_test.test_barcode_reader_matrix_hardware_free",
    "alfa_CR6_test.test_order_barcode_dispense_e2e",
    "alfa_CR6_test.test_emulator_time_scale",
    "alfa_CR6_test.test_post_dispense_tintometer_refresh",
    "alfa_CR6_test.test_hardware_free_suite_manifest",
    # Persistenza e stato ordini/barattoli.
    "alfa_CR6_test.test_database_cleanup",
    "alfa_CR6_test.test_db_indexes",
    "alfa_CR6_test.test_dupont_order_archive",
    "alfa_CR6_test.test_order_number_format",
    "alfa_CR6_test.test_status_guard",
    "alfa_CR6_test.test_kcc_double_order",
    # Comunicazione e concorrenza.
    "alfa_CR6_test.test_send_command_race",
    "alfa_CR6_test.test_ws_server",
    "alfa_CR6_test.test_flask_api_hardware_free",
    # Periferiche sostituite con filesystem/fake UI.
    "alfa_CR6_test.test_sound_player",
    "alfa_CR6_test.test_liner_reminder",
    "alfa_CR6_test.test_browser_page_ws_lifecycle",
    "alfa_CR6_test.test_order_page_rendering",
)

NETWORK_TEST_MODULES = (
    # Apre soltanto websocket loopback locali; nessuna testa fisica.
    "alfa_CR6_test.test_ws_telemetry",
)


# Questi file hanno un nome test_*.py, ma non appartengono al runner
# hardware-free. La motivazione esplicita impedisce che un nuovo modulo venga
# dimenticato o che uno script con effetti collaterali venga importato per
# errore. Il meta-test verifica che l'inventario resti completo e disgiunto.
EXCLUDED_TEST_MODULES = {
    "alfa_CR6_test.test_barcode_scanner":
        "apre evdev e avvia il loop del lettore durante l'import",
    "alfa_CR6_test.test_create_label_image":
        "genera e apre un'immagine etichetta durante l'import",
    "alfa_CR6_test.test_create_package_label_image":
        "esegue la generazione etichetta durante l'import",
    "alfa_CR6_test.test_db":
        "utility legacy che avvia l'app e usa path database fissi",
    "alfa_CR6_test.test_dialog_cancel_stops_refill":
        "test Qt standalone non ancora incluso nel gate hardware-free",
    "alfa_CR6_test.test_dialog_leak":
        "misura Qt standalone dipendente da WebEngine e risorse grafiche",
    "alfa_CR6_test.test_download_KCC_specific_gravity_lot":
        "esegue una richiesta di rete durante l'import",
    "alfa_CR6_test.test_dymo_labeler":
        "utility manuale che puo' invocare CUPS e periferiche di stampa",
    "alfa_CR6_test.test_settings_manager":
        "suite pytest, non caricabile dal runner unittest",
    "alfa_CR6_test.test_ui":
        "utility manuale che avvia l'applicazione Qt completa",
    "alfa_CR6_test.test_ws_comm":
        "utility manuale che avvia applicazione e comunicazione websocket",
    "alfa_CR6_test.webengine.test_WebenginePage":
        "utility manuale WebEngine con URL esterno",
    "alfa_CR6_test.webengine.test_webengine":
        "avvia WebEngine e il display reale durante l'import",
}


def build_suite(include_network=False):
    names = list(CORE_TEST_MODULES)
    if include_network:
        names.extend(NETWORK_TEST_MODULES)
    return unittest.defaultTestLoader.loadTestsFromNames(names)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Esegue i test alfa_cr6 che non richiedono la macchina reale."
    )
    parser.add_argument(
        "--network", action="store_true",
        help="include i test websocket end-to-end su loopback",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--show-logs", action="store_true",
        help="mostra anche i log attesi dei percorsi di errore",
    )
    args = parser.parse_args(argv)

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    runtime_dir = os.path.join(
        tempfile.gettempdir(), "alfa-cr6-test-runtime-{}".format(os.getuid())
    )
    os.makedirs(runtime_dir, mode=0o700, exist_ok=True)
    os.chmod(runtime_dir, 0o700)
    os.environ["XDG_RUNTIME_DIR"] = runtime_dir
    # I test di telemetria verificano esplicitamente alcuni record di log e
    # quindi non possono essere eseguiti con logging.disable().
    logs_disabled = not args.show_logs and not args.network
    if logs_disabled:
        logging.disable(logging.CRITICAL)

    try:
        result = unittest.TextTestRunner(
            verbosity=2 if args.verbose else 1
        ).run(build_suite(include_network=args.network))
    finally:
        if logs_disabled:
            logging.disable(logging.NOTSET)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
