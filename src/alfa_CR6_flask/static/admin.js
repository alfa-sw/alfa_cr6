var g_ws_client = null;

var toggle_element_visibility = function(el_id) {
    var el = document.getElementById(el_id); 
    if(el){
        if (el.style.visibility === "hidden") {
            el.style.visibility = "visible"; 
        } else {
            el.style.visibility = "hidden"; 
        }
    }
}

var send_debug_cmd = function() {
    var el = document.getElementById("debug_command"); 
    if((el) && (g_ws_client)){
        el.value;
        console.debug('send_debug_cmd(), el.value: ' + el.value); 
        g_ws_client.send(JSON.stringify({"debug_command": el.value}));
    }
}

var ask_temperature_logs = function(head_letter) {

    console.debug('ask_temperature_logs(), head_letter: ' + head_letter); 
    var cmd = {"command": 'ask_temperature_logs', 'params': {'head_letter': head_letter}};
    cmd = JSON.stringify(cmd);
    g_ws_client.send(cmd);
};

var ask_platform_info = function(head_letter) {

    console.log('ask_platform_info(), head_letter: ' + head_letter); 
    var cmd = {"command": 'ask_platform_info', 'params': {'head_letter': head_letter}};
    cmd = JSON.stringify(cmd);
    g_ws_client.send(cmd);
};

var ask_settings = function() {

    console.log('ask_settings()'); 
    var cmd = {"command": 'ask_settings', 'params': {}};
    cmd = JSON.stringify(cmd);
    g_ws_client.send(cmd);
};

var ask_formula_files = function() {

    console.log('ask_formula_files()'); 
    var cmd = {"command": 'ask_formula_files', 'params': {}};
    cmd = JSON.stringify(cmd);
    g_ws_client.send(cmd);
};

var ask_aliases = function() {

    console.log('ask_aliases()'); 
    var cmd = {"command": 'ask_aliases', 'params': {}};
    cmd = JSON.stringify(cmd);
    g_ws_client.send(cmd);
};

var create_order_from_file = function(file_name) {

    console.log('create_order_from_file()'); 
    var cmd = {"command": 'create_order_from_file', 'params': {'file_name': file_name}};
    cmd = JSON.stringify(cmd);
    g_ws_client.send(cmd);
};

var change_language = function(lang_) {

    var msg_ = "Confirm changing language to " + lang_ + "? WARN: Application will be restarted.";
    if (window.confirm(msg_)) {
        console.debug('change_language(), lang_: ' + lang_); 
        var cmd = {"command": 'change_language', 'params': {'lang': lang_}};
        cmd = JSON.stringify(cmd);
        g_ws_client.send(cmd);
    };
};

var on_wsocket_open = function(event) {
    console.debug('on_wsocket_open, event: ' + JSON.stringify(event)); 
};
var on_wsocket_close =  function(event) {
    console.log('on_wsocket_close, event: ' + JSON.stringify(event)); 
};
var on_wsocket_error = function(event) {
    console.log('on_wsocket_error, event: ' + JSON.stringify(event));
};
var on_wsocket_message = function(event) {
    var data = JSON.parse(event.data);
    var el = document.getElementById(data.type); 
    if(el){
        el.innerHTML = data.value;
        if (data.make_visible) { el.style.visibility = "visible"; }
    }
    if (data.server_time) {
        var el1 = document.getElementById('server_time'); 
        if(el1){
            el1.innerHTML = data.server_time;
        }
    }
};

var connect_wsocket = function(ws_server_url) {
    console.log('connect_wsocket() ws_server_url:', ws_server_url)
    if ((g_ws_client === null) || (ws_client.readyState == 3)/* CLOSED */) {
        g_ws_client = new WebSocket(ws_server_url);
        g_ws_client.onerror = on_wsocket_error; 
        g_ws_client.onopen = on_wsocket_open;  
        g_ws_client.onclose = on_wsocket_close;
        g_ws_client.onmessage = on_wsocket_message;
    } else {
        if ((g_ws_client) && (g_ws_client.readyState == 1)/* OPEN */) {
            try {
              g_ws_client.close(); 
            }
            catch(error) {
              console.error(error);
              g_ws_client = null;
            }
        }
    }
    console.log('connect_wsocket() g_ws_client:', g_ws_client)
};
