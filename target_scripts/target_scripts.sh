#!/bin/bash

echo 'STEP 1'
echo 'fix REDIS issue : (error) ERR Rewriting config file: Permission denied'
echo 'redis.conf -> disable save the db on disk'
sudo sed -i -e 's/save 900 1/ /g' -e 's/save 300 10/ /g' -e 's/save 60 10000/ /g' /etc/redis/redis.conf
echo '***'
echo 'STEP 2'
echo 'fix "A stop job is running for Session c3 of user pi"'
echo 'create specific service to kill the process pcmanfm that hangs for 90 seconds on reboot/shutdown'
sudo nano /etc/systemd/system/run_on_shutdown_reboot.service
echo '
[Unit]
Description=Kill PCManFM 1.3.1 process before shutdown or reboot
DefaultDependencies=no
Before=reboot.target shutdown.target halt.target
# If your script requires any mounted directories, add them below: 
#RequiresMountsFor=/home

[Service]
Type=oneshot
ExecStart=pkill -9 pcmanfm

[Install]
WantedBy=reboot.target halt.target shutdown.target
' | sudo tee /etc/systemd/system/run_on_shutdown_reboot.service > /dev/null
sudo systemctl enable run_on_shutdown_reboot.service

echo '***'
echo 'REBOOTING'
sudo reboot