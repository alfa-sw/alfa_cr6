<a name="top"></a>
##### Appunti che riportano le operazioni eseguite per l'allestimento della immagine ISO per la raspberry Pi da usare come Supervisor Linux Unit per la CR6.

<a name="toc"></a>
____________________________________
T.O.C.:

  1. [Start from Raspbian](#p1)
  1. [upgrade raspian buster to bullseye](#p2)
  1. [create user *admin*](#p3)
  1. [copy rsa keys to the target](#p4)
  1. [install system packages](#p5)
  1. [allow graphical application programs to user admin](#p6)
  1. [create a virtualenv](#p7)
  1. [setup RT hwclock](#p8)
  1. [Set up DYMO 450 labeler in CUPS Server](#p9)
  1. [install the 'alfa_CR6' package](#p10)
  1. [install the 'alfa40' package](#p11)
  1. [install D2XX Direct Drivers - FTDI Chip](#p12)
  1. [re-create the ISO image *alfaberry cr6*](#p13)
  1. [known issues](#p14)

____________________________________


<a name="p1"></a>
##### 1. Start from Raspbian:

  * [download the latest raspbian arm64 ISO image](http://downloads.raspberrypi.org/raspios_arm64/images/). Raspbian GNU/Linux 10 (e.g. 2020-08-20-raspios-buster-arm64.zip) 

  * [copy it to ssd card](https://www.raspberrypi.org/documentation/installation/installing-images/linux.md)
```
    sudo dd bs=4M if=/opt/RASPBERRY/2020-08-20-raspios-buster-arm64.img  of=/dev/sdf conv=fsync
```

  * Insert the ssd card into the RBPi, plug peripheral devices (monitor, mouse, keyboard) and boot it

  * Change password for user 'pi'
```
            pi@raspberry:$ sudo raspi-config

                1 Change User Password (from raspberry to alfapi)
```

  * Connect RBPi to the WEB

  * Enable SSH
  ```
            pi@raspberry:$ sudo raspi-config

                5 Interfacing Options  Configure connections to peripherals
                    P2 SSH         Enable/Disable remote command line access to your Pi using SSH

```

  * Disable screen blanking
  ```
            pi@raspberry:$ sudo raspi-config

                7 Advanced Options     Configure advanced settings  
                    A6 Screen Blanking   Enable/Disable screen blanking
                         Would you like to enable screen blanking?   <No>
```
   * (optional) Setup Italian keyboard layout

   ```

            Preferences  
                Keyboard and Mouse
                    Keyboard Tab
                      Keyboard Layout...
                        Set Layout
                        (Set Variant)
```

   * (optional) Disable Bluetooth

<a name="p2"></a>
##### 2. upgrade raspian buster to bullseye  - ([back to top](#top))

upgrade from buster to bullseye (testing phase)

```
pi@raspberrypi:~ $ sudo apt update -y
pi@raspberrypi:~ $ sudo apt upgrade -y

pi@raspberrypi:~ $ echo $'deb http://deb.debian.org/debian bullseye  main contrib non-free
#deb http://deb.debian.org/debian-security/ buster/updates main contrib non-free
deb http://deb.debian.org/debian bullseye-updates main contrib non-free
# Uncomment deb-src lines below then 'apt-get update' to enable 'apt-get source'
#deb-src http://deb.debian.org/debian buster main contrib non-free
#deb-src http://deb.debian.org/debian-security/ buster/updates main contrib non-free
#deb-src http://deb.debian.org/debian buster-updates main contrib non-free'|sudo -u root -i tee /etc/apt/sources.list

# execute again update & upgrade
pi@raspberrypi:~ $ sudo apt update -y
pi@raspberrypi:~ $ sudo apt upgrade -y

# (optionally) check current release
pi@raspberrypi:~ $  lsb_release -a
No LSB modules are available.
Distributor ID: Debian
Description:  Debian GNU/Linux bullseye/sid
Release:  testing
Codename: bullseye

# install gcc
pi@raspberrypi:~ $ sudo apt install -y gcc-8-base
```

**NOTE**

* known issue [gcc-8-base](doc/issues_setup_platform_RBPi_alfaCR6.md#issue-7)

* created ISO into SVRCLIENTI > 2020-11-20-rapsios-bullseye-testing-arm64-full.img


<a name="p3"></a>
##### 3. create user *admin* (sudo).  - ([back to top](#top))

```
    pi@target $ sudo adduser --disabled-password admin
    pi@target $ sudo usermod -a -G adm,dialout,cdrom,sudo,audio,plugdev,users,input,netdev,gpio,i2c,spi admin 
    pi@target $ sudo mkdir /home/admin/.ssh && sudo chown admin:admin /home/admin/.ssh
    pi@target $ sudo mkdir /opt/alfa && sudo chown admin:admin /opt/alfa
    pi@target $ sudo mkdir /opt/alfa_cr6 && sudo chown admin:admin /opt/alfa_cr6
    # let admin run sudo cmds without password
    pi@target $ echo "admin     ALL=(ALL) NOPASSWD:ALL" | sudo tee -a /etc/sudoers
    pi@target $ sudo reboot
```

<a name="p4"></a>
##### 4. copy rsa keys to the target  - ([back to top](#top))

```
    pi@target $ mkdir /home/pi/tmp
    host $ scp  .ssh/alfa_rsa .ssh/alfa_rsa.pub .ssh/authorized_keys pi@192.168.0.100:/home/pi/tmp/
    pi@target $ sudo cp /home/pi/tmp/* /home/admin/.ssh/ 
    pi@target $ sudo chown admin:admin -R /home/admin/.ssh
    pi@target $ sudo rm -rf /home/pi/tmp
```

<a name="p5"></a>
##### 5. install system packages - ([back to top](#top))

```
    pi@target $ sudo apt update -y
    pi@target $ sudo apt install -y python3-pip python3 python3-dev supervisor openvpn virtualenv python3-pyqt5 python3-pyqt5.qtwebengine python3-evdev cups printer-driver-dymo redis sqlite3
``` 

disable the save-on-disk-feature of redis (limit flash mem write access):
```
    pi@target $ redis-cli config set save ""
    pi@target $ redis-cli config rewrite
```
raspian bullseye (testing) [known issue redis 6.0.9](doc/issues_setup_platform_RBPi_alfaCR6.md#issue-1)

redis issue [fix](doc/issues_setup_platform_RBPi_alfaCR6.md#issue-1-fix)

add user "admin" to the groups input, lpadmin (for printer), video:
```
    admin@raspberrypi:~ $ sudo usermod -aG input,lpadmin,video admin
```

change group and permissions to dev "/dev/uinput"
```
    admin@raspberrypi:~ $ sudo chgrp input /dev/uinput && sudo chmod 770 /dev/uinput
```

<a name="p6"></a>
##### 6. allow graphical application programs (e.g alfa_CR6) to user admin  - ([back to top](#top))

Possible suggestion here [issue launch alfa_CR6 with user admin](doc/issues_setup_platform_RBPi_alfaCR6.md#issue-4)

<a name="p7"></a>
##### 7. create a virtualenv - ([back to top](#top))

create virtualenv for alfa_CR6
```
    admin@raspberrypi:~ $ virtualenv --system-site-packages -p /usr/bin/python3 /opt/alfa_cr6/venv
```

create virtualenv for alfa40
```
    admin@raspberrypi:~ $ virtualenv -p /usr/bin/python3 /opt/alfa/venv
```

<a name="p8"></a>
##### 8. Set up RT hwclock - ([back to top](#top))

For Low Accuracy RTC, Follow: [http://wiki.seeedstudio.com/Pi_RTC-DS1307/](http://wiki.seeedstudio.com/Pi_RTC-DS1307/)

For High Accuracy RTC, Follow: [http://wiki.seeedstudio.com/High_Accuracy_Pi_RTC-DS3231/](http://wiki.seeedstudio.com/High_Accuracy_Pi_RTC-DS3231/) 

**NOTE**: <span style="color:#660000; background:#FFFFBB"> only one driver can be installed, not both (LoAc DS1307 **or** HiAc DS3231), in the current ISO the second one (HiAc DS3231) is installed.</span>


Guide for lazy people who do not want to read the wiki about HiAc DS3231

Step 1. Driver Installation

```
admin@raspberrypi:~ $ git clone https://github.com/Seeed-Studio/pi-hats.git
admin@raspberrypi:~ $ cd pi-hats
admin@raspberrypi:~ $ sudo ./tools/install.sh -u rtc_ds3231
```

Step 2. Power off Raspberry Pi

```
admin@raspberrypi:~ $ sudo shutdown -h now
```

Step 3. Insert the HAT to Raspberry Pi

Step 4. Power up Raspberry Pi

Step 5. Check driver installation
```
admin@raspberrypi:~ $ ./pi-hats/tools/install.sh -l
rtc_ds1307    : not installed
rtc_ds3231    : installed
adc_ads1115   : not installed

admin@raspberrypi:~ $ sudo hwclock -r
2020-11-17 09:08:18.903180+01:00

admin@raspberrypi:~ $ sudo date
Tue 17 Nov 2020 09:08:55 AM CET

```

known issue: [hwclock and system time not synced](doc/issues_setup_platform_RBPi_alfaCR6.md#issue-2)

<a name="p9"></a>
##### 9. Set up DYMO 450 labeler in CUPS Server - ([back to top](#top))

add "pi" user to group lpadmin
```
admin@raspberrypi:~ $ sudo usermod -aG lpadmin pi
```

then:

follow [note_driver_CUPS_labeler_CR6.md](./note_driver_CUPS_labeler_CR6.md#configure-dymo-labelwriter-450-turbo) for more details


<a name="p10"></a>
##### 10. install the 'alfa_CR6' package - ([back to top](#top))

see [alfa_CR6 REAME-md](../README.md) for more details

build the wheel on host

```
    host$ cd ${PROJECT_ROOT}               
    host$ python3 make.py -b
```
install on target (set it with param -t user@ip):
```
    host$ cd ${PROJECT_ROOT}               
    host$ python3 make.py -t admin@192.168.15.185 -M -C
    host$ python3 make.py -t admin@192.168.15.185 -I
    host$ python3 make.py -t admin@192.168.15.185 -S
```


<a name="p11"></a>
##### 11. install the 'alfa40' package - ([back to top](#top))

  * clone the git repo: [alfa-sw/devices branch alfa40](https://github.com/alfa-sw/devices/tree/alfa40) on a host (development PC)

  * setup the ./make_defaults.py :
    ```
      {
          'fast':                0,
          'quiet':                True,
          'dist_dir':             "./__tmp__/",
          'patched_redis_path':   '',
          'target_py_venv_path':  '/opt/alfa/venv',
          'target_platform':        'RBpi',
          'target_credentials':     'admin@192.168.x.x',
      }
    ```
  * install the package on target (RPBi) via:
    ```
        host:~ $ python3 ./make.py -bI
    ```

  * let the supervisord use '/opt/alfa/conf/supervisor.conf' as its conf file:
    ```
        admin@raspberrypi:~ $ sudo mv /etc/supervisor/supervisord.conf /etc/supervisor/supervisord.conf-ORIG
        admin@raspberrypi:~ $ sudo ln -s /opt/alfa/conf/supervisord.conf /etc/supervisor/supervisord.conf
    ```

  * upload credentials.gmail for alfa_email_client (necessary for enable vpn remotely via email) via flask admin interface

  **NOTE**

  * known issue [juice4halt manager](#issue-juice4halt-manager)

  * known issue [credentials.gmail](#issue-juice4halt-manager)

<a name="p12"></a>
##### 12. install D2XX Direct Drivers - FTDI Chip - ([back to top](#top))

This drivers are necessary to use the FTDI USB to RS232 UART Serial Converter PCB


```
admin@raspberrypi:~ $ wget https://www.ftdichip.com/Drivers/D2XX/Linux/libftd2xx-arm-v8-1.4.8.gz
```
Download driver from the site

```
admin@raspberrypi:~ $ tar xfvz libftd2xx-arm-v8-1.4.8.gz
```
This unpacks the archive, creating the following directory structure:

    build
        libftd2xx        (re-linkable objects)
        libusb           (re-linkable objects)
        libftd2xx.a      (static library)
        libftd2xx.so.1.4.8   (dynamic library)
        libftd2xx.txt    (platform-specific information)
    examples
    libusb               (source code)
    ftd2xx.h
    WinTypes.h

```
admin@raspberrypi:~ $ cd release/build/
```
```
admin@raspberrypi:~ $ sudo -s
```

Promotes you to super-user, with installation privileges.  If you're
already root, then step 3 (and step 7) is not necessary.

```
root@raspberrypi: cp libftd2xx.* /usr/local/lib
```
Copies the libraries to a central location.

```
root@raspberrypi: chmod 0755 /usr/local/lib/libftd2xx.so.1.4.8
```
Allows non-root access to the shared object.

```
root@raspberrypi: ln -sf /usr/local/lib/libftd2xx.so.1.4.8 /usr/local/lib/libftd2xx.so
```
Creates a symbolic link to the 1.4.8 version of the shared object.

```
root@raspberrypi: exit
```
Ends your super-user session.

```
admin@raspberrypi:~ $ cd && rm libftd2xx-arm-v8-1.4.8.gz && rm -rf release/
```
Remove unnecessary files and folders

<a name="p13"></a>
##### 13. re-create the ISO image *alfaberry cr6* - ([back to top](#top))

```
    host:~ $ sudo pv -s 15G "/dev/sdf" | dd of=/mnt/sshdir/SRVCLIENTI/mnt/dati/RASPBERRY/2020-11-19-raspios-bullseye-testing-arm64-alfa-cr6-FULL.img
```

<a name="p14"></a>
##### 14. known issues - ([back to top](#top))

it was preferred to report the issues (with their analysis and fix hypothesis) in a separate file. The following is a summary TOC of known issues.

1. [redis-cli config rewrite](doc/issues_setup_platform_RBPi_alfaCR6.md#issue-1)
1. [hwclock and system time not synced](doc/issues_setup_platform_RBPi_alfaCR6.md#issue-2)
1. [juice4halt manager (supervisor)](doc/issues_setup_platform_RBPi_alfaCR6.md#issue-3)
1. [launch alfa_CR6 with user "admin" error](doc/issues_setup_platform_RBPi_alfaCR6.md#issue-4)
1. [A stop job is running for Session c2 (or c3) of user pi](doc/issues_setup_platform_RBPi_alfaCR6.md#issue-5)
1. [email connection issue](doc/issues_setup_platform_RBPi_alfaCR6.md#issue-6)
1. [installation gcc-8-base errors](doc/issues_setup_platform_RBPi_alfaCR6.md#issue-7)
______________________________
[back to top](#top)

