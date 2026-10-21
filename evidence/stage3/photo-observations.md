# Connection photographs — technical observations

The three preserved original photographs were directly inspected on 18 October 2026 through JPEG format-conversion work copies. The original HEIC hashes below match the retained historical checksum list. This is an authored technical transcription, not raw command output or a new test. The photographs remain private because their screens contain network/device identifiers. No network names, addresses, connection UUIDs or password fields are transcribed here.

- IMG_0201: `nmcli dev` shows wld0 as wifi, initially disconnected. Radio-on, rescan and list commands are visible. The list contains 2.4 GHz and 5 GHz channel entries, including WPA2 networks. The displayed RATE column is not a measured throughput result.
- IMG_0202: a first `nmcli --ask dev wifi connect` attempt ends with `Timeout 90 sec expired`. A subsequent attempt reports `Device 'wld0' successfully activated`. The state table shows `wld0 wifi connected`. `ip addr show wld0` shows UP/LOWER_UP, dynamic IPv4 /24, global dynamic IPv6 /64 and link-local IPv6. `ip route` shows a default route on wld0 with `proto dhcp`. `getent hosts google.com` returns an IPv6 answer. `ping` cannot run because the command is not installed. The reason for the first timeout is not established.
- IMG_0203: the DNF transfer summary shows 143.5 MiB and the package transaction ends with `Complete!`. Firefox is installed and open to its New Tab page. The image does not contain a separately captured curl/TLS result or prove an arbitrary external web page was opened. DNF download figures are not a Wi-Fi throughput benchmark.

The sequence supports scanning, successful connection, address configuration, a DHCP default route, DNS resolution and actual package downloads over the established connection. It does not establish 6 GHz operation, roaming, suspend/resume reliability, or a ping result. The exact association channel is not determined here. A Wi-Fi link RATE shown in a scan is not sustained data throughput.

## Private original hashes

- `IMG_0201.HEIC`: `2e27b50ec5f040ae91a06b2d2feced5b28acf321922d97eda2a2087ecd4c8e93`
- `IMG_0202.HEIC`: `4d5b96c4ed2a19e621f838f405e3cb046bb5e7d6e0d0904359d7a0c0467daf46`
- `IMG_0203.HEIC`: `e185e399c811f02ff8cfddd995fdc362b80fa407267a8beda2bde776db3f4e5c`
