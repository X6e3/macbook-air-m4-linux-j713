# Screen photographs, 18 October 2026

Text of four photographs of the J713 screen, each showing the output of
`sudo dmesg | grep -i -E 'AFE reset|multi-touch|HINT'` right after a boot. The photographs are kept private;
their SHA-256 values are in the manifest. Times are the photographs' own. Each block starts at
`Starting interface multi-touch`; the five lines before it register the device at about 1.2 s and are the
same in all four photographs.

## IMG_0181, 21:26:05: N2, first boot after macOS

N2 logs the AFE reset line before the start and then releases it.

```text
[    4.317390] dockchannel-hid 394b28000.input: Starting interface multi-touch
[    4.321144] dockchannel-hid 394b28000.input: AFE reset GPIO before start: raw 1 (released)
[    4.347875] dockchannel-hid 394b28000.input: AFE reset GPIO released: raw 1
[    4.349171] dockchannel-hid 394b28000.input: Sending firmware for multi-touch
[    4.350727] dockchannel-hid 394b28000.input: Resetting multi-touch
[    4.562187] rtkit-helper 394600000.mtp: RTKit: syslog message: afe_bl_trp_hbpp.c:175: AFE Chip Boot Failure for HBPP[0]: No HINT_L
[    6.563275] dockchannel-hid 394b28000.input: iface multi-touch not ready, resetting again (attempt 2/3)
[    6.669315] rtkit-helper 394600000.mtp: RTKit: syslog message: afe_bl_trp_hbpp.c:175: AFE Chip Boot Failure for HBPP[0]: No HINT_L
[    8.675280] dockchannel-hid 394b28000.input: iface multi-touch not ready, resetting again (attempt 3/3)
[    8.781018] rtkit-helper 394600000.mtp: RTKit: syslog message: afe_bl_trp_hbpp.c:175: AFE Chip Boot Failure for HBPP[0]: No HINT_L
[   10.787285] dockchannel-hid 394b28000.input: iface multi-touch start timed out
[   10.818967] dockchannel-hid 394b28000.input: Interface multi-touch is already starting
[   10.845549] dockchannel-hid 394b28000.input: Interface multi-touch is already starting
[   13.188195] dockchannel-hid 394b28000.input: Interface multi-touch is already starting
```

## IMG_0182, 21:26:48: N2, Linux reboot

```text
[    4.297052] dockchannel-hid 394b28000.input: Starting interface multi-touch
[    4.301088] dockchannel-hid 394b28000.input: AFE reset GPIO before start: raw 1 (released)
[    4.327631] dockchannel-hid 394b28000.input: AFE reset GPIO released: raw 1
[    4.327960] dockchannel-hid 394b28000.input: Sending firmware for multi-touch
[    4.328583] dockchannel-hid 394b28000.input: Resetting multi-touch
[    4.563136] dockchannel-hid 394b28000.input: Interface multi-touch is now ready
```

## IMG_0183, 22:11:56: N3, first boot after macOS

N3 drives the line low for 50 ms and high for 50 ms before sending the firmware.

```text
[    4.333778] dockchannel-hid 394b28000.input: Starting interface multi-touch
[    4.336987] dockchannel-hid 394b28000.input: AFE reset GPIO before start: raw 1
[    4.460768] dockchannel-hid 394b28000.input: Sending firmware for multi-touch
[    4.462120] dockchannel-hid 394b28000.input: Resetting multi-touch
[    4.696308] dockchannel-hid 394b28000.input: Interface multi-touch is now ready
```

## IMG_0184, 22:32:30: N4, first boot after macOS

```text
[    4.307780] dockchannel-hid 394b28000.input: Starting interface multi-touch
[    4.313719] dockchannel-hid 394b28000.input: AFE reset GPIO before start: raw 1
[    4.425280] dockchannel-hid 394b28000.input: Sending firmware for multi-touch
[    4.426671] dockchannel-hid 394b28000.input: Resetting multi-touch
[    4.661978] dockchannel-hid 394b28000.input: Interface multi-touch is now ready
```
