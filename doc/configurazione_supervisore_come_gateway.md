
## T.o.C.

### 1. Come configurare il supervisore di cr6 come gateway aperto per tutte le schede raspberry
### 2. Come configurare le schede raspberry perche' usino il supervisore di cr6 come gateway aperto

===========================

## 1. Come configurare il supervisore di cr6 come gateway aperto per tutte le schede raspberry

### 1.1. show ip tables content (to run if you need it)

    pi@raspberrypi:~ $ sudo iptables --list -v
    pi@raspberrypi:~ $ sudo iptables -t nat --list -v

### 1.2. reset all ip tables content (to run if you need it)

    pi@raspberrypi:~ $ sudo iptables -P INPUT ACCEPT
    pi@raspberrypi:~ $ sudo iptables -P FORWARD ACCEPT
    pi@raspberrypi:~ $ sudo iptables -P OUTPUT ACCEPT
    pi@raspberrypi:~ $ sudo iptables -t nat -F
    pi@raspberrypi:~ $ sudo iptables -t mangle -F
    pi@raspberrypi:~ $ sudo iptables -F
    pi@raspberrypi:~ $ sudo iptables -X

### 1.3. set ip tables on the fly:

#### 1.3.1. bridge wlan0 <-> eth0: wlan0 connected to web and eth0 connected to intra-machine network

    pi@raspberrypi:~ $ sudo iptables -A FORWARD -i eth0 -o wlan0 -j ACCEPT
    pi@raspberrypi:~ $ sudo iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT
    pi@raspberrypi:~ $ sudo iptables -t nat -A POSTROUTING -o wlan0 -j MASQUERADE

#### 1.3.2. bridge eth1 <-> eth0: eth1 connected to web and eth0 connected to intra-machine network

    pi@raspberrypi:~ $ sudo iptables -A FORWARD -i eth0 -o eth1 -j ACCEPT
    pi@raspberrypi:~ $ sudo iptables -A FORWARD -i eth1 -o eth0 -j ACCEPT
    pi@raspberrypi:~ $ sudo iptables -t nat -A POSTROUTING -o eth1 -j MASQUERADE
    
### 1.3. Permanently set ip tables:

    pi@raspberrypi:~ $ apt-get install iptables-persistent
    pi@raspberrypi:~ $ iptables-save > /etc/iptables/rules.v4

### 1.4. Enable IP Forwarding:

#### 1.4.1. Check if IP Forwarding is enabled

    pi@raspberrypi:~ $ sysctl net.ipv4.ip_forward

#### 1.4.2. Enable IP Forwarding on the fly

    pi@raspberrypi:~ $ sysctl -w net.ipv4.ip_forward=1

#### 1.4.3. Permanently set IP Forwarding using /etc/sysctl.conf

    in /etc/sysctl.conf add a (or uncomment the) line containing "net.ipv4.ip_forward = 1"

NOTE: To enable the changes made in sysctl.conf you will need to run the command:

    pi@raspberrypi:~ $ sysctl -p /etc/sysctl.conf

## 2. Come configurare le schede raspberry perche' usino il supervisore di cr6 come gateway aperto

#### 2.1. Permanently set gateway address (editing /etc/network/interfaces)

    in /etc/network/interfaces add the following section :
        
    auto eth0
    iface eth0 inet static
        address 192.168.0.<id of the machine-head 1, ..., 6>
        netmask 255.255.255.0
        gateway 192.168.0.100

NOTE: To enable the changes made in sysctl.conf you will need to run the command:

    pi@raspberrypi:~ $ sudo ifdown eth0 && sudo ifup eth0

check results with:

    pi@raspberrypi:~ $ wget google.com
    pi@raspberrypi:~ $ wget www.alfadispenser.com



################
useful commands:

sudo nano /etc/network/interfaces

sudo service networking restart
sudo supervisorctl restart all
sudo supervisorctl status
ifconfig 
route
ping google.com

################
