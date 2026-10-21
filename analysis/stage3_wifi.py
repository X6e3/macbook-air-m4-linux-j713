#!/usr/bin/env python3
"""Verify Wi-Fi evidence and derive stage boundaries from archived records only."""
import argparse
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
EV=ROOT/'evidence/stage3'
OUT=ROOT/'data/stage3/wifi_summary.json'


def derive():
    manifest=json.loads((EV/'manifest.json').read_text())
    for entry in manifest['files']:
        data=(EV/entry['file']).read_bytes()
        if hashlib.sha256(data).hexdigest()!=entry['published_sha256']:
            raise ValueError(f"Checksum mismatch: {entry['file']}")
        if len(data.splitlines())!=entry['line_count']:
            raise ValueError(f"Line count mismatch: {entry['file']}")

    def events(file,pattern,required=False):
        result=[]
        for line_no,line in enumerate((EV/file).read_text().splitlines(),1):
            match=re.search(pattern,line)
            if match:
                time=re.match(r'(?:(\d+):)?\[\s*([\d.]+)\]',line)
                row=dict(line=line_no,groups=list(match.groups()))
                if time:
                    row['seconds']=time[2]
                    if time[1]:row['original_journal_line']=int(time[1])
                result.append(row)
        if required and not result:raise ValueError(f'Missing expected stage boundary: {file}: {pattern}')
        return result

    first={
        'pcie_link':events('pcie-firstboot.txt',r'Link up on /soc/pcie@1cb0000000/pci@0,0',True),
        'wifi_pci':events('pcie-firstboot.txt',r'pci 0000:01:00.0: \[14e4:4434\]',True),
        'wifi_firmware_missing':events('pcie-firstboot.txt',r'Direct firmware load for brcm/brcmfmac4388c0-pcie.bin failed with error (-?\d+)',True),
        'run_init':events('pcie-firstboot.txt',r'Run /init as init process',True),
        'root_mount':events('pcie-firstboot.txt',r'EXT4-fs .*mounted filesystem',True),
    }
    first['firmware_request_precedes_init_and_root']=Decimal(first['wifi_firmware_missing'][0]['seconds'])<Decimal(first['run_init'][0]['seconds'])<Decimal(first['root_mount'][0]['seconds'])
    if not first['firmware_request_precedes_init_and_root']:raise ValueError('Firmware timing boundary contradicts the account')
    bin_only=dict(request=events('bin-only-kernel.txt',r'using brcm/brcmfmac4388c0-pcie',True),
                  initialization_failure=events('bin-only-kernel.txt',r'FW failed to initialize',True),
                  runtime_outcome=events('bin-only-runtime.txt',r'after (\d+)s: driver=(\S+) wlan=(\S+)',True))
    fwset=dict(firmware=events('fwset-kernel.txt',r'brcmf_c_preinit_dcmds: Firmware:.*FWID ([\w-]+)',True),
               interface=events('fwset-kernel.txt',r'wld0: renamed from wlan0',True),
               join_preference_errors=events('fwset-kernel.txt',r'Set join_pref error \((-?\d+)\)'),
               runtime_outcome=events('fwset-runtime.txt',r'after (\d+)s: driver=(\S+) wlan=(\S+)',True))
    normal=dict(firmware=events('normalboot-wifi-order.txt',r'brcmf_c_preinit_dcmds: Firmware:.*FWID ([\w-]+)',True),
                interface=events('normalboot-wifi-order.txt',r'wld0: renamed from wlan0',True),
                regulatory_missing=events('normalboot-wifi-order.txt',r'Direct firmware load for regulatory.db failed with error (-?\d+)'),
                checks=events('normalboot-report.txt',r'OK\s+(no brcm firmware ENOENT|no FW failed to initialize|no .Set join_pref error.|wireless interface present \(wld0\))',True))
    macos=events('macos-firmware-selection.txt',r'FirmwareVersion.*FWID ([\w-]+)',True)
    ids=[macos[0]['groups'][0],fwset['firmware'][0]['groups'][0],normal['firmware'][0]['groups'][0]]
    if len(set(ids))!=1:raise ValueError('macOS and Linux FWID evidence disagree')
    return dict(schema=1,scope='Historical observations; no new hardware test',first_boot=first,bin_only=bin_only,
                complete_firmware_environment=fwset,normal_boot=normal,matching_macos_and_linux_fwid=ids[0],
                connection_evidence='Direct inspection of three retained private photos, transcribed in photo-observations.md; original pixels are not published',
                limits=['No successful ping captured; command missing','No dedicated curl/TLS result captured',
                        'No throughput, 6 GHz, roaming or suspend/resume claim','Missing regulatory.db is a separate failure from missing Broadcom firmware'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');args=p.parse_args()
    result=derive()
    if args.check:
        if json.loads(OUT.read_text())!=result:raise ValueError('Saved Wi-Fi summary is stale; run make wifi')
        n=len(json.loads((EV/'manifest.json').read_text())['files'])
        print(f'Wi-Fi: {n} evidence hashes, line counts, firmware timing/FWID and saved summary match')
    else:
        OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2)+'\n')
        print('Wrote data/stage3/wifi_summary.json')


if __name__=='__main__':main()
