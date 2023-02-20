
var __g_ws_client = null;
var __g_child_win_proxy_queue = {};

var get_page_id_by_element = function(element) {
    let parent = element.parentElement;
    if (parent) {
        if (parent.classList.contains("ui_page")) return parent.id;
        else return get_page_id_by_element(parent);
    } else return null;
}


var obj_from_element = function(element, event) {
    let page_id = get_page_id_by_element(element);
    let obj = {
        'event': event, 
        'page_id': page_id, 
        'el_id': element.id
    };
    if (element.value) {obj['el_value'] = element.value;}
    if (element.title) {obj['el_title'] = element.title;}
    if (element.name) {obj['el_name'] = element.name;}
    if (element.type) {obj['el_type'] = element.type;}
    if (element.data) {obj['data'] = element.data;}
    if (element.form) {obj['form'] = element.form;}
    if (element.tagName) {obj['tagName'] = element.tagName;}
    return obj;
}

var onkeyup_event_handler = function(element_id) {
    try {
        let element = document.getElementById(element_id);
        if (element) {
            wsocket_send(obj_from_element(element, 'keyup'));
        }
    } catch(error) {
        alert(error);
        console.error(error);
    }
}

var change_event_handler = function(element_id) {
    try {
        let element = document.getElementById(element_id);
        if (element) {
            wsocket_send(obj_from_element(element, 'change'));
        }
    } catch(error) {
        alert(error);
        console.error(error);
    }
}

var click_event_handler = function(event) {
    try {
        let element = event.target;
        if (element.id) {
            wsocket_send(obj_from_element(element, 'click'));
        }
    } catch(error) {
        alert(error);
        console.error(error);
    }
}

var open_alert_dialog = function(url, target, win_options, html_) {

    if (__g_child_win_proxy_queue[target]) {
        __g_child_win_proxy_queue[target].close();
    }

    __g_child_win_proxy_queue[target] = window.open(url, target, win_options);

    try {
        __g_child_win_proxy_queue[target].document.innerHTML = '';
        __g_child_win_proxy_queue[target].document.write(html_);
        __g_child_win_proxy_queue[target].focus();
    } catch(error) {
        alert(error);
        console.error(error);
    }
}

var open_child_window = function(url, target, win_options) {

    if (__g_child_win_proxy_queue[target]) {
        __g_child_win_proxy_queue[target].close();
    }

    __g_child_win_proxy_queue[target] = window.open(url, target, win_options);
}

var close_child_windows = function(needle_) {

    for (i in __g_child_win_proxy_queue) {
        if (needle_) {
            let pos = i.search(needle_);
            if (pos >= 0) {
                __g_child_win_proxy_queue[i].close();
            }
        } else {
            __g_child_win_proxy_queue[i].close();
        }
    }
}

var show_page = function(page_id) {
    window.scrollTo(0, 0); 
    wsocket_send({'event': 'refresh_page', 'page_id': page_id, 'el_id': null});
    let page_els = document.getElementsByClassName("ui_page");
    for (let i = 0; i < page_els.length; i++) {
        if (page_els[i].classList) {
            if (page_els[i].id == page_id) {
                page_els[i].classList.remove("hidden");
            } else {
                page_els[i].classList.add("hidden");
            }
        }
    }
};

var ws_message_handler = function(event) {
    //~ console.log("ws_message_handler(), event:" + JSON.stringify(event));
    try {
        let data = JSON.parse(event.data);
        //~ console.log("ws_message_handler(), data.type:" + JSON.stringify(data.type));

        if (data.type == 'html') {
            let el = document.getElementById(data.target); 
            if (data.mode == 'append') {el.innerHTML = el.innerHTML + data.value;}
            else {el.innerHTML = data.value;}
        } else if (data.type == 'css') {
            let el = document.getElementById(data.target); 
            //~ let _style = JSON.parse(data.value);
            let _style = data.value;
            for (const property in _style) {
                el.style[property] = _style[property];
            }
        } else if (data.type == 'js') {
            eval(data.value);
        }
    } catch(error) {
      alert(error);
      console.error(error);
    }
};

var wsocket_send = function(obj) {
    let msg = JSON.stringify(obj);
    //~ console.log('wsocket_send() msg:', msg);
    __g_ws_client.send(msg);
};

var wsocket_connect = function(ws_server_url, on_open_cb) {
    console.log('wsocket_connect() ws_server_url:', ws_server_url);
    if ((__g_ws_client === null) || (ws_client.readyState == 3)/* CLOSED */) {
        __g_ws_client = new WebSocket(ws_server_url);
        __g_ws_client.onerror = function(event) { console.log('__on_wsocket_error, event: ' + JSON.stringify(event)); }; 
        __g_ws_client.onopen  = function(event) { 
            console.log('__on_wsocket_open , event: ' + JSON.stringify(event)); 
            console.log('__on_wsocket_open , on_open_cb: ' + on_open_cb); 
            if (on_open_cb) {
                on_open_cb();
            }
        };  
        __g_ws_client.onclose = function(event) { console.log('__on_wsocket_close, event: ' + JSON.stringify(event)); };
        __g_ws_client.onmessage = function(event) { ws_message_handler(event); };
    } else {
        if ((__g_ws_client) && (__g_ws_client.readyState == 1)/* OPEN */) {
            try {
              __g_ws_client.close(); 
            }
            catch(error) {
              console.error(error);
              __g_ws_client = null;
            }
        }
    }
    console.log('wsocket_connect() __g_ws_client:', __g_ws_client)
};

var init_ui = function(ws_server_url) {
    wsocket_connect(ws_server_url, function () {show_page('home_page');});
    document.body.onclick = click_event_handler;
}
