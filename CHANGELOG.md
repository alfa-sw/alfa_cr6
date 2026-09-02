# Change Log
All notable changes to this project will be documented in this file.

## 1.11 branch

### 1.11.0
 - PR#___ - issue RM#553 - added refill alarm sound notification on monitor speakers via the host audio router (REFILL_ALARM_NOTIFICATION setting, snowball machines only); the sound follows the attention-LED lifecycle and is silenced by OK/Cancel on the frozen dialog or by timeout; sound_level offers only "auto" for now (percent options deferred to monitor PSU handling)
 - PR#___ - issue RM#574 - Low Pigments popup: added print-label button (one DYMO label per head listing its low-level pipes), label rendered vertically on the long side, localized label
 - PR#___ - issue RM#573 - shifted barcode print button to the right in the browser overlay
 - PR#___ - issue RM#586 - database: composite index on jar (order_id, index) created idempotently at startup; bounded cleanup of event/document/jar/order tables moved out of the ORM hot path into a dedicated worker (startup catch-up + once per day, waits for idle jar runners/recovery)
 - PR#___ - issue RM#492 - Orders page: explicit column sizing and cached decorations instead of ResizeToContents; fixed QAbstractTableModel contract for empty tables (Qt 5.12 crash); added service page performance tracing
 - PR#___ - issue RM#587 - browser page: webview kept resident on hide with page WebSocket suspended/resumed instead of blanking, WebEngine warm-up with blank page, fallback when page WS hooks are unavailable; "pending operations" modal temporarily suppressed behind SHOW_PENDING_OPERATIONS_MODAL
 - PR#___ - issue RM#589 - tintometer levels refreshed after dispensing so low-level JSON files and reserve icon reflect the quantities just dispensed
 - PR#___ - issue RM#594 - added localized PPS liner reminder popup (REMINDER_PPS_LINER setting, migrated from REMINDER_LINER, also exposed on legacy machines)
 - PR#___ - issue RM#595 - fixed legacy settings page URL persistence when submitted together with numeric values
 - PR#___ - shuttle package barcode labels: print the barcode configured in Package json_info (label_barcode), show barcode information in the package sizes dialog, support decimal ounce quantities; shuttle label scans validated and synchronized with formula readings; restored EAN-13 check digit truncation on scan
 - PR#___ - fixed memory leak of modal dialogs (ModalMessageBox, TroubleshootingDialog, RecoveryInfoDialog were never destroyed after close); cached freeze msgbox exempted from deletion; regression test suite added
 - PR#___ - UI performance: status-driven repaints coalesced (UI_REFRESH_INTERVAL_MS, ~10 Hz) and gated on home page visibility, cached visual state and precomputed jar/head lookups, cached app_settings module, lazy logging formatting, redundant live_can_list broadcasts avoided
 - PR#___ - machine head: hardened WebSocket lifecycle with close telemetry (close_timeout 40s -> 5s, faulty message no longer tears down the connection); watchdog and WebSocket tasks supervised, machine task restarted on unexpected termination
 - PR#___ - recovery mode: fail closed on ambiguous dispensing state (jar/order marked ERROR, never re-dispensed), recovery records preserved and cleaned safely, resume allowed between carousel sensors, no event loop blocking during recovery wait (see doc/TEST_HARDWARE_FREE.md)
 - PR#___ - carousel: both outputs stopped on failed transfer starts, busy head A released on any transfer outcome (cancel/fault), refill retry loop exits when pigments become sufficient, watchdog timer preserved until output actually stops, safe STANDBY awaited after dispense cancellation
 - PR#___ - fixed KCC multi-coat PDF split: FIRST/SECOND COAT sections produce distinct orders with separate ingredients and labels
 - PR#___ - fixed generated order numbers constrained to the daily sequence; fixed float multipleOf settings validation
 - PR#___ - home page: prevent stray ENTER (e.g. barcode gun trailing newline) from clicking action buttons
 - PR#___ - disabled shuttle barcode format pre-filter, relying on package lookup only
 - added hardware-free test suite (alfa_CR6_test_hardware_free) and accelerated multi-variant emulator (--time-scale, --machine-variant)

## 1.10 branch

### 1.10.0
 - PR#___ - added CRX80 support (4 linear heads A, B, C, G): carousel sequence, recovery mode steps and heads map, barcode logic, home page synoptic, action pages and admin page layout
 - PR#___ - issue RM#464 - added troubleshooting page: localized per-error help (title, error code, translated error name) reachable via the Info button of the FW-error alert dialog; Cancel button disabled on FW-error alerts
 - PR#___ - issue RM#526 - KCC QR refill: decode/validation delegated to the device endpoint, QR_code_info attached to REFILL items, cap on overfill and specific_weight recomputed on the confirmed quantity
 - PR#___ - issue RM#525 - show KCC download button only when DOWNLOAD_KCC_LOT_STEP > 0
 - PR#___ - issue RM#521 - added SKIP_FREEZE_ON_UNKNOWN_PIGMENTS setting: jars with only unknown pigments show a non-blocking alert instead of freezing the carousel
 - PR#___ - issue RM#503 - minor fixes for non-snowball machines (MACHINE_VARIANT default)
 - PR#___ - added timing-belt health blinking indicator per head on the home page (new "table_belt_health" message)
 - PR#___ - fixed in-transit jar blink not stopping on task cancel from the debug page (present since 1.9.0)
 - PR#___ - increased dispensing timeout from 12 to 24 min to handle CRX 20 pipes; added a 4-second delay before stopping the output roller
 - PR#___ - HeadStatusApi cleanup; order files deleted via os.remove instead of shell
 - shuttle barcode label width reduced by 10%
 - updated existing translations

## 1.9 branch

### 1.9.0
 - PR#___ - issue RM#417 - added LED management (SET_ATTENTION_REQUEST_STATUS) for software error messages, insufficient pigment, and carousel move failures; refcount-based cross-task refill messages; in-transit jar labels with blinking error step
 - PR#___ - claim RM#479 - shuttle barcode reader: validation and filter for spurious reads (evdev); dual barcode synchronization via asyncio.Event; fix state machine for dual-reader machines
 - PR#___ - claim RM#289 - added snapshot of heads state on "waiting for dispense position to get available" and "Condition not valid while reading barcode" errors (diagnostics)
 - PR#___ - claim RM#432 - added Axalta CCC XML parser
 - PR#___ - issue RM#499 - hardened WebSocket server: input validation, structured error responses, parallel broadcast, stale client cleanup, ConnectionClosed logging
 - PR#___ - issue RM#488 - async label printing via run_in_executor; fix corrupted PDF on Pillow 8.x; 300 DPI resolution
 - PR#___ - refactored SettingsManager validation: single source of truth from JSON schema, fixed critical bug where except Exception swallowed jsonschema errors
 - PR#___ - removed remote_ui feature; /settings route moved to alfa_CR6_flask/views.py
 - PR#___ - preserve DONE/ERROR can state during carousel movement
 - added Portuguese language
 - added unit tests for WsMessageHandler, SettingsManager, and can status guard

## 1.8 branch

### 1.8.0
 - PR#153 - task RM#381 - added CRX40 & CRX60 logic
 - PR#___ - task RM#154 - sinottico event description is always saved in eng into the db
 - PR#___ - task RM#321 - handle custom extension X-WINE-EXTENSION-INI (PaliniColor)
 - PR#___ - task RM#335 - added web gui to modify the APP_SETTINGS (instead of editing directly the python file)
 - PR#___ - task RM#338 - improved RECOVERY MODE popup infos
 - PR#___ - task RM#339 - added MIXIT XML parser
 - PR#___ - task RM#343 - sinottico REFILL POPUP now ignores data from input barcode reader
 - PR#___ - task RM#355 - fixed output roller stop delay at photocell trigger by using a incorrect FW-managed stop command
 - PR#___ - task RM#393 - improved barcode-based refill: added REFILL UP logic (instead of calculating the volume based on the current level)
 - PR#___ - task RM#394 - improved barcode-based refill: when a product is mapped to multiple circuits, the operator can now select which circuit to top up (instead of refilling only the first match)
 - PR#___ - task RM#396 - added barcode-based shuttle volume detection (requires 2 YOKO Barcode Readers)
 - PR#___ - task RM#400 - replaced blocking alert()/confirm()/prompt() dialogs with non-blocking async modals (Promise-based) to prevent WebSocket backpressure and keep the UI responsive.
 - PR#___ - task RM#414 - Added PPS presence check on HEAD 1 (A): if no PPS signal is detected, the UI now shows an error message and the order will be aborted.
 - added Thai language
 - updated existing translations
 - tweaked the UI to accommodate long-label languages

## 1.7 branch

### 1.7.0
 - PR#___ - task RM#366, RM#350 - improved recovery mode's logic to avoid data inconsistencies in the JSON file (JARs deleted but still present in the file, or JARs with unknown locations)
 - PR#___ - task RM#369 - added the DevTools component on demand to QTWebPages.
 - Improved barcode reader logic to further reduce spurious event readings. 

## 1.6 branch

### 1.6.0
 - PR#148 - task RM#46 - implements jar recovery mode: in the event of a shutdown, it is possible to resume interrupted orders (except those that were dispensing)
 - PR#149 - task RM#216 - improving jar recovery mode
 - PR#151 - task RM#287 - refactoring popup Barcode Refill to enhance user experience
 - PR#152 - task RM#234 - fixed the issue with the label creation popup not being dismissed immediately: every press of the OK button sent the command to generate labels.
 - PR#152 - task RM#299 - added setting to show/hide purge all button.
 - PR#152 - task RM#312 - added KCC QRCode refill logic using the refill popup.
 - PR#152 - task RM#300 - added setting to show/hide copy/clone orders buttons.
 - PR#152 - task RM#301 - added a manual barcode input mode (enabled via settings) that bypasses automatic scanning from the physical barcode reader, preventing machine downtime in case of a malfunction of it.
 - PR#152 - task RM#327 - added Arabic language

## 1.5 branch

### 1.5.0.post3 - 2024-12-06

 - fixed printing of missing data on label in case of order from akzo mixit cloud 

### 1.5.0.post2 - 2024-11-29

 - fixed the RedisOrderPublisher communication setup required for Akzo cloud responses after an order is completed

### 1.5.0.post1 - 2024-11-20

 - fixed error caused by missing keyword 'async' on call_api_rest function

### 1.5.0 - 2024-10-28 (same as 1.5.0.rc3)

 - PR#145 - task RM#111 - added carcolorservice order parser
 - PR#___ - task RM#200 - added new manuals and QRCodes to help page
 - PR#___ - task RM#199 - optimized the understanding and readability of user interface messages related to initial checks and dispensation management
 - added Polish language

## 1.4 branch

### 1.4.1 - 2024-09-05

 - added Polish language

### 1.4.0 - 2024-06-27

 - PR#142 - task RM#11 - send order result on redis
 - removed code related to empty cans on machines, since not codified using feature branch method
 - PR#___ - task RM#8 - added parser for akzo azure orders
 - PR#___ - task RM#75 - Fixed check for JSON file orders
 - PR#144 - task RM#82 - improved SERVIND pdf template parsing to handle EN and CZ languages
 - minor improvements for application

## 1.3 branch

### 1.3.0 - 2024-05-21

#### Added
 - Manage TINY Dymo label (19mm x 51mm)
 - Improved photocells visualization page for each HEAD
 - Added function to print all label for pigment labels

#### Fixed
 - Removed develop purpose buttons from the debug page that caused unintended effects (eg delete all orders)
 - Fixed wrong total volum calculation during barcode jar checks

## 1.2 branch

### 1.2.1 - 2024-04-18

#### Fixed
 - Revised handling of restore_machine_helper when it is disabled; the poor management was generating a huge amount of event records.

### 1.2.0 - 2024-04-09

#### Added
 - Implemented logic to analyze CarColourService PDF orders.

### 1.1.1 - 2024-03-22
 
#### Fixed
 - Removed certain buttons from the debug page that caused unintended and unmanaged effects, potentially due to specific system configurations or operational scenarios not fully tested following the introduction of 485 communication and software evolution.
