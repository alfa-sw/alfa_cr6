# Change Log
All notable changes to this project will be documented in this file.

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
