O12b measurement tests (27 Oct 2026). TEST ONLY.
Image: J713BUILD share/o12b/boot-6boot-o12b-root2-6a3fb110.bin (6boot P3.2 user stage 2, kernel 7.1.13-x6e3-o12b
16158df0 = published j713-linux head + o12b-measurement.patch, K1 DTB 5fd2368f, P2T initramfs).

Order:
 1. macOS:  sudo bash /Volumes/J713BUILD/share/o12b/o12b-esp.sh install     (restore puts the previous image back)
 2. Linux:  grep -o 'x6e3\.v=[^ ]*' /proc/cmdline   ->  x6e3.v=6boot-o12b-root2
 3. Linux:  sudo bash /mnt/x63r/j713-diag/o12b/o-mca.sh map
            Silence plays, no sound. If the machine hangs on a chunk: hold the power button, boot O12b again and
            run the same command; that chunk becomes the end of the readable window on its side and the map
            finishes. Ends with the repeat period of each 4 KiB page.
            (27 Oct, first run: 0x0000-0x8bff read, 0x8c00 hung. The next run finishes at once.)
 4. macOS:  sudo bash /Volumes/J713BUILD/share/o12b/o12b-esp.sh loud        (27 Oct: O12b with the -10 dB ceiling,
            boot-6boot-o12b-10db-root2-dd3c19ee.bin, one byte different; restore still goes back to 6boot-K1)
    Linux:  sudo bash /mnt/x63r/j713-diag/o12b/o-mca.sh ab
            About 11 trials, two sounds each (the "Front Left" / "Front Right" voice, played with aplay); answer only whether you heard it. Starts with a side check
            (ear close to each edge). If a trial hangs the machine: power
            button, boot O12b, run ab again; it carries on in the same order and records that trial as hung.
            rwmap is not part of the run: writing into the running unit's registers hung the machine (27 Oct).
 5. Linux:  sudo -v; bash /mnt/x63r/j713-diag/o12b/o-gpu.sh observe          read only, about 5 minutes
 6. Linux:  sudo -v; bash /mnt/x63r/j713-diag/o12b/o-gpu.sh dose             about 60 minutes; watch the first phases
 7. macOS:  sudo bash /Volumes/J713BUILD/share/o12b/o12b-esp.sh restore

Safety:
 - o-mca: the -30 dB ceiling and amplifier protection stay on; both amplifiers are bound again before each trial;
   a trial whose amplifier faults plays no more tones. rwmap leaves the registers below the driver's groups alone
   and puts every word back.
 - o-gpu dose: the GPU thermal zone is off during the run and back on at the end or on Ctrl+C; the load pauses at
   SoC 90 C and resumes at 75 C; it stops at SoC 95 C or TVS1 70 C and gives every word back.
