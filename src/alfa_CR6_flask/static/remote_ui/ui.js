
var __g_ws_client = null;

var get_page_id_by_element = function(element) {
    let parent = element.parentElement;
    if (parent) {
        if (parent.classList.contains("ui_page")) return parent.id;
        else return get_page_id_by_element(parent);
    } else return null;
}

var click_event_handler = function(event) {
    let element = event.target;
    let page_id = get_page_id_by_element(element);
    if (element.id) {
        wsocket_send({'event': 'click', 'page_id': page_id, 'element_id': element.id});
    }
}

var show_page = function(page_id) {
    window.scrollTo(0, 0); 
    wsocket_send({'event': 'refresh_page', 'page_id': page_id, 'element_id': null});
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
    console.log("ws_message_handler(), event:" + JSON.stringify(event));
    try {
        let data = JSON.parse(event.data);
        console.log("ws_message_handler(), data.type:" + JSON.stringify(data.type));
        if (data.type == 'html') {
            let el = document.getElementById(data.target); 
            el.innerHTML = data.value;
        } else if (data.type == 'js') {
            eval(data.value);
        }
    }
    catch(error) {
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
    if ((__g_ws_client === null) || (__g_ws_client.readyState == 3)/* CLOSED */) {
        __g_ws_client = new WebSocket(ws_server_url);
        __g_ws_client.onerror = function(event) {
            console.log('__on_wsocket_error, event: ' + JSON.stringify(event));
            alert('Websocket connection error! Try to refresh the page (F5)');
        }; 
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

