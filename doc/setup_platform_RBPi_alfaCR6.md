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
  1. [re-create the ISO image *alfaberry*](#p13)

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

  * Connect RBPi to the WEB via WiFi

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

TODO 
(Luca Vitali)


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
    pi@target $ sudo apt update
    pi@target $ sudo apt install -y supervisor openvpn virtualenv python3 python3-pyqt5 python3-pyqt5.qtwebengine python3-evdev cups printer-driver-dymo redis sqlite3
``` 

disable the save-on-disk-feature of redis (limit flash mem write access):
```
    pi@target $ redis-cli config set save ""
    pi@target $ redis-cli config rewrite
```

add user "admin" to the groups input, lpadmin (for printer), video:
```
    admin@raspberrypi:~ $ sudo usermod -aG input,lpadmin,video admin
```

change group and permissions to dev "/dev/uinput"
```
    admin@raspberrypi:~ $ sudo chgrp input /dev/uinput && sudo chmod 770 /dev/uinput
```

<a name="p6"></a>
##### 6. allow graphical application programs to user admin  - ([back to top](#top))

**NOTE**

it is necessary study how to add persistence to the permission
**SKIP THIS STEP**


add a Server Interpreted entry of type "localuser" with a value of "admin"

```
admin@raspberrypi:~ $  xhost +si:localuser:admin
```

to verify if user admin was correctly added:

```
admin@raspberrypi:~ $  xhost
access control enabled, only authorized clients can connect
SI:localuser:admin
SI:localuser:pi
```

for more details:

[man xhost](http://manpages.ubuntu.com/manpages/xenial/man1/xhost.1.html)

[xsecurity man page](http://manpages.ubuntu.com/manpages/xenial/man7/Xsecurity.7.html)


<a name="p7"></a>
##### 7. create a virtualenv - ([back to top](#top))

create virtualenv for alfa_CR6
```
    admin@raspberrypi:~ $ virtualenv --system-site-packages -p /usr/bin/python3 /opt/alfa_cr6/venv
```

create virtualenv for alfa40
```
    pi@raspberrypi:~ $ virtualenv -p /usr/bin/python3 /opt/alfa/venv
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

<a name="p9"></a>
##### 89. Set up DYMO 450 labeler in CUPS Server - ([back to top](#top))

see [note_driver_CUPS_labeler_CR6.md](./note_driver_CUPS_labeler_CR6.md#configure-dymo-labelwriter-450-turbo) for more details


<a name="p10"></a>
##### 10. install the 'alfa_CR6' package - ([back to top](#top))

see [alfa_CR6 REAME-md](../README.md) for more details

build the wheel on host

```
    host$ cd ${PROJECT_ROOT}               
    host$ . /opt/alfa_cr6/venv/bin/activate
    host$ python setup.py bdist_wheel 
```
install on target:

NOTE:

[VERSION_NUMBER] is the version number written into file `${PROJECT_ROOT}/__version__`.


```
    host$ scp admin@host:${PROJECT_ROOT}/dist/alfa_CR6-[VERSION_NUMBER]-py3-none-any.whl user@target:${DEPLOY_PATH}
    host$ scp user@host:${PROJECT_ROOT}/conf/app_settings.py user@target:/opt/alfa_cr6/conf/app_settings.py
    target$ . /opt/alfa_cr6/venv/bin/activate                                                                       
    target$ pip install ${DEPLOY_PATH}/alfa_CR6-[VERSION_NUMBER]-py3-none-any.whl 
```

create a shell executable file on Desktop for "pi" user
```
    admin@raspberrypi:~ $ sudo su pi
    pi@raspberrypi:~ $ echo $'. /opt/alfa_cr6/venv/bin/activate\nalfa_CR6 > /opt/alfa_cr6/log/cr6.log'|tee -a /home/pi/Desktop/CR6.sh
    pi@raspberrypi:~ $ chmod +x /home/pi/Desktop/CR6.sh

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

  * upload credentials.gmail for alfa_email_client (necessary for enable vpn remotly via email) via flask admin interface


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
admin@raspberrypi cd && rm libftd2xx-arm-v8-1.4.8.gz && rm -rf release/
```
Remove unnecessary files and folders

<a name="p13"></a>
##### 13. re-create the ISO image *alfaberry* - ([back to top](#top))

TODO: create platform iso to SVRCLIENTI

```
    host:~ $ sudo pv -s 15G "/dev/sdf" | dd of=/mnt/sshdir/SRVCLIENTI/mnt/dati/RASPBERRY/2020-02-02-raspbian-buster-lite-alfa-FULL.img
```

There is also a shrinked version (i.e. same content but smaller, without extra, empty space) to be used as next start point:
```
alfa@srvclienti:/mnt/dati/RASPBERRY$ ls -l
total 20392704
-rwxrwxrwx 1 alfa alfa  2248146944 Sep 26 02:24 2019-09-26-raspbian-buster-lite.img
-rw-rw-r-- 1 alfa alfa   454279954 Jan 28 14:53 2019-09-26-raspbian-buster-lite.zip
-rwxrwxrwx 1 alfa alfa 15931539456 Feb  4 14:47 2020-02-02-raspbian-buster-lite-alfa-FULL.img
-rwxrwxr-x 1 alfa alfa  2248146944 Feb  4 14:56 2020-02-02-raspbian-buster-lite-alfa.img
alfa@srvclienti:/mnt/dati/RASPBERRY$ 
```
TRICK: The shrinked version (the one with dimension of 2G) have been created this way:

    1. build the large versione as described above (2020-02-02-raspbian-buster-lite-alfa-FULL.img).
    2. create a copy of the original raspbian buster lite (2019-09-26-raspbian-buster-lite.img)
    3. mount both the rootfilesystem partitions on the host ([see e.g.](https://www.shellhacks.com/mount-iso-image-linux/)) 
    4. copy files from the larger to the smaller:
        sudo cp -a /mnt/loop0/* /mnt/loop1/ 
    5. remember the ssh file in the boot partition 

write it to the ssd-card
```
    sudo dcfldd bs=4M if=2020-02-02-raspbian-buster-lite-alfa.img  of=/dev/sdf
```
or
```
    sudo dd bs=4M if=2020-02-02-raspbian-buster-lite-alfa.img  of=/dev/sdf conv=fsync
```
and you have a cloned system (remember to re-create a unique machine-id, if necessary) 

______________________________
[back to top](#top)

