 'MACHINE_STATUS': {'MAB_code': 200,                                        # STATO_MACCHINA = 200
    'comm_bus_db_expire_time_sec': 3,
    'direction': "MAB2MGB",
    'description': """This is the message that the MAB sends to the MGB, carrying all of the details about the status of the MAB.""",
    'in_params': {'jsonschema': {'$schema': 'http://json-schema.org/draft-06/schema#', 'properties': {}}},
    'out_params': {
        'example': {
            'status_level'              : 'STANDBY',
            'cycle_step'                : 0x09,
            'protocol_version'          : 0x00,   
            'error_code'                : 0x00,   
            'cover_reserve'             : [], 
            'cover_availability'        : [],
            'cover_enabled'             : [], 
            'container_reserve'         : [],
            'container_availability'    : [],
            'container_enabled'         : [],
            'color_reserve'             : [],
            'container_presence'        : False,
            'autocap_status'            : False,
            'canlift_status'            : False,
            'doors_status'              : True,
            'clamp_position'            : 0x00, # "POS0",
            'recirculation_status'      : [9, 10, 12, 18], 
            'stirring_status'           : [],
            'slave_status'              : [9, 10, 12, 18],
            'can_on_plate'              : True,
            'can_lifter_current_height' : 249.0,
            'can_lifter_range'          : 400.0,
            'current_temperature'       : 25.1,
            'current_rel_humidity'      : 82.1,
            'water_level'               : False,
            'critical_temperature'      : False,
            'temperature'               : 25.1,
            'bases_carriage'            : False,
            'circuit_engaged'           : 0x0A,
            'table_steps_position'      : 0x0BB8,
            'autotest_cycles_number'    : 0x05, 
            'table_cleaning_status'     : [0, 2, 3, 4],
            'panel_table_status'        : True,
            'photocells_status'         : 61,
            'can_available'             : True,
            'mixer_door_status'         : True, 
            'slave_enable_mask'         : [2, 8, 12, 63],
            'jar_photocells_status'     : 33,
            'stop_formula'              : 1,
        },
        'jsonschema': {
            '$schema': 'http://json-schema.org/draft-06/schema#',
            'properties': {
                # ~ 'cycle_step'             : {"type": "string", "propertyOrder":  2, 'fmt': 'B', 'conversion_list': ['INIT', 'CONTAINER', 'TO_FILLING', 'FILLING_L1', 'FILLING_L2', 'FILLING_L3', 'CAPPING', 'NEGATIVE_DISCHARGE', 'DISCARGE', 'COMPLETION']}, 
                # ~ 'protocol_version'       : {"type": "number", "propertyOrder":  3, 'fmt': 'B'}, 
                # ~ 'error_code'             : {"type": "number", "propertyOrder":  4, 'fmt': 'B'}, 
                # ~ enum {
                  # ~ /* 0 */ POWER_OFF_ST,
                  # ~ /* 1 */ INIT_ST,
                  # ~ /* 2 */ IDLE_ST,
                  # ~ /* 3 */ RESET_ST,
                  # ~ /* 4 */ COLOR_RECIRC_ST,
                  # ~ /* 5 */ COLOR_SUPPLY_ST,
                  # ~ /* 6 */ ALARM_ST,
                  # ~ /* 7 */ DIAGNOSTIC_ST,
                  # ~ /* 8 */ POSITIONING_ST,
                  # ~ /* 9 */ JUMP_TO_BOOT_ST,
                  # ~ /* 10*/ ROTATING_ST,
                  # ~ /* 11*/ AUTOTEST_ST,
                  # ~ /* 12*/ JAR_POSITIONING_ST,
                  # ~ /* 13*/ N_STATUS
                # ~ };
                'status_level'              : {"type": "string" , "propertyOrder":  1, 'fmt': 'B', 'conversion_list': ['POWER_OFF', 'INIT', 'IDLE', 'RESET', 'STANDBY', 'DISPENSING', 'ALARM', 'DIAGNOSTIC', 'POSITIONING', 'JUMP_TO_BOOT', 'ROTATING', 'AUTOTEST', 'JAR_POSITIONING',]}, 
                'cycle_step'                : {"type": "number" , "propertyOrder":  2, 'fmt': 'B'}, 
                'error_code'                : {"type": "number" , "propertyOrder":  3, 'fmt': 'H'}, 
                'cover_reserve'             : {"type": "array"  , "propertyOrder":  4, 'fmt': '1s', 'is_index_list': True}, 
                'cover_availability'        : {"type": "array"  , "propertyOrder":  5, 'fmt': '1s', 'is_index_list': True}, 
                'cover_enabled'             : {"type": "array"  , "propertyOrder":  6, 'fmt': '1s', 'is_index_list': True}, 
                'container_reserve'         : {"type": "array"  , "propertyOrder":  7, 'fmt': '1s', 'is_index_list': True}, 
                'container_availability'    : {"type": "array"  , "propertyOrder":  8, 'fmt': '1s', 'is_index_list': True}, 
                'container_enabled'         : {"type": "array"  , "propertyOrder":  9, 'fmt': '1s', 'is_index_list': True}, 
                'color_reserve'             : {"type": "array"  , "propertyOrder": 10, 'fmt': '4s', 'is_index_list': True},  
                'container_presence'        : {"type": "boolean", "propertyOrder": 11, 'fmt': '?', 'description': "0: NOT present, 1: present"},
                'autocap_status'            : {"type": "boolean", "propertyOrder": 12, 'fmt': '?', 'description': "0: closed, 1: open"}, 
                'canlift_status'            : {"type": "boolean", "propertyOrder": 13, 'fmt': '?', 'description': "0: canlift NOT extended, 1: canlift extended"}, 
                'doors_status'              : {"type": "boolean", "propertyOrder": 14, 'fmt': '?', 'description': "0: closed, 1: open"},
                'clamp_position'            : {"type": "number" , "propertyOrder": 15, 'fmt': 'B', 'description': "meaningful only for Color Tester"},  
                'recirculation_status'      : {"type": "array"  , "propertyOrder": 16, 'fmt': '4s', 'is_index_list': True, 'description': "list of recirculating slave boards"}, 
                'stirring_status'           : {"type": "array"  , "propertyOrder": 17, 'fmt': '4s', 'is_index_list': True, 'description': "list of slave boards in stirring mode"}, 
                'slave_status'              : {"type": "array"  , "propertyOrder": 18, 'fmt': '6s', 'is_index_list': True, 'description': "list of active slave boards"},  
                'can_on_plate'              : {"type": "boolean", "propertyOrder": 19, 'fmt': '?', 'description': "0: can is NOT on plate, 1:can is on plate"},
                'can_lifter_current_height' : {"type": "number" , "propertyOrder": 20, 'fmt': 'I', 'conversion_factor': 1./10000,'description': "current position (height) in mm"}, 
                'can_lifter_range'          : {"type": "number" , "propertyOrder": 21, 'fmt': 'I', 'conversion_factor': 1./10000, 'description': "maximum extension ('position low'-'position high') calculated during Reset, in mm"}, 
                'current_temperature'       : {"type": "number" , "propertyOrder": 22, 'fmt': 'H', 'conversion_factor': 0.1, 'description': "TÂ°C. If not configured: â€˜3276.7â€™"},
                'current_rel_humidity'      : {"type": "number" , "propertyOrder": 23, 'fmt': 'H', 'conversion_factor': 0.1, 'description': "RH%. If not configured: â€˜3276.7â€™"},
                'water_level'               : {"type": "boolean", "propertyOrder": 24, 'fmt': '?', 'description': "0: above minimal threshold (OK), 1:below minimal threshold (NOT OK)"},
                'critical_temperature'      : {"type": "boolean", "propertyOrder": 25, 'fmt': '?', 'description': "0: below critical threshold (OK), 1:above critical threshold (NOT OK)"}, 
                'temperature'               : {"type": "number" , "propertyOrder": 26, 'fmt': 'H', 'conversion_factor': 0.1, 'description': "TÂ°C. If not configured: â€˜3276.7â€™"},
                'bases_carriage'            : {"type": "boolean", "propertyOrder": 27, 'fmt': '?', 'description': "0: bases carriage inside, 1: bases carriage extracted (NOT OK)"},
                'circuit_engaged'           : {"type": "number",  "propertyOrder": 28, 'fmt': 'B', 'description': "circuit engaged on rotating table"},
                'table_steps_position'      : {"type": "number",  "propertyOrder": 29, 'fmt': 'H', 'description': "rotating table steps position with respect to reference"},
                'autotest_cycles_number'    : {"type": "number",  "propertyOrder": 30, 'fmt': 'H', 'description': "number of autotest cycles completed so far"},                
                'table_cleaning_status'     : {"type": "array",   "propertyOrder": 31, 'fmt': '4s', 'is_index_list': True, 'description': "list of cleaning colorants on rotating table"},
                'panel_table_status'        : {"type": "boolean", "propertyOrder": 32, 'fmt': '?', 'description': "0: table panel inside, 1: table panel open (NOT OK)"},
                'photocells_status'         : {"type": "number",  "propertyOrder": 33, 'fmt': 'B', 'description': "photocells status on mmt board"},
                # 'photocells_status' mask bit coding:
                # bit0: THOR PUMP HOME_PHOTOCELL - MIXER HOME PHOTOCELL
                # bit1: THOR PUMP COUPLING_PHOTOCELL - MIXER JAR PHOTOCELL
                # bit2: THOR VALVE_PHOTOCELL - MIXER DOOR OPEN PHOTOCELL
                # bit3: THOR TABLE_PHOTOCELL - 
                # bit4: THOR VALVE_OPEN_PHOTOCELL                
                # bit5: THOR AUTOCAP_CLOSE_PHOTOCELL
                # bit6: THOR AUTOCAP_OPEN_PHOTOCELL
                # bit7: THOR BRUSH_PHOTOCELL 
                'can_available'             : {"type": "boolean", "propertyOrder": 34, 'fmt': '?', 'description': "0: NOT available, 1: available"},
                'mixer_door_status'         : {"type": "boolean", "propertyOrder": 35, 'fmt': '?', 'description': "0: door closed, 1: door open"},                                       
                'slave_enable_mask'         : {"type": "array", "propertyOrder": 36, 'fmt': '6s', 'is_index_list': True},                     # BRANCH: "alfa40" or "CT3.0"                 
#                'slave_enable_mask'          : {"type": "array", "propertyOrder": 36, 'fmt': '6s', 'is_index_list': True, 'index_offset': 1, 'description': "0 = Disabled, 1 = Enabled"},     # BRANCH: "master"   
                'jar_photocells_status'         : {"type": "number",  "propertyOrder": 37, 'fmt': 'H', 'description': "jar presence on roller or lifter. The single bit in this byte represent a different photocell status: 1 for canister detected; 0 otherwise"},
                # 'jar photocells_status' mask bit coding:
                # bit0: JAR_INPUT_ROLLER_PHOTOCELL
                # bit1: JAR_LOAD_LIFTER_ROLLER_PHOTOCELL
                # bit2: JAR_OUTPUT_ROLLER_PHOTOCELL
                # bit3: LOAD_LIFTER_DOWN_PHOTOCELL 
                # bit4: LOAD_LIFTER_UP_PHOTOCELL
                # bit5: UNLOAD_LIFTER_DOWN_PHOTOCELL 
                # bit6: UNLOAD_LIFTER_UP_PHOTOCELL
                # bit7: JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL
                # bit8: JAR_DISPENSING_POSITION_PHOTOCELL   
                # bit9: JAR_DETECTION_MICROSWITCH_1
                # bit10:JAR_DETECTION_MICROSWITCH_2                
				#
                # bit0 -> Least significant bit
                # bit10 -> Most significant bit
                #
                # e.g. first CR6 head canister roller photocell detected:
                # 0 0 0 0 0 0 0 0 1 (binary) = 0x001 (hex) = 1 (decimal)
                #
                # e.g. first CR6 head JAR_INPUT_ROLLER_PHOTOCELL and JAR_DISPENSING_POSITION_PHOTOCELL detected:
                # 1 0 0 0 0 0 0 0 1 (binary) = 0x101 (hex) = 257 (decimal)
                'stop_formula'         : {"type": "number",  "propertyOrder": 38, 'fmt': 'B', 'description': "0: formula not interrupted, 1 = formula interrupted"},                                                    
            }}}},
