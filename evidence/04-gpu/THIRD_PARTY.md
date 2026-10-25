# Source patch notices

`mesa-103-apple9-compression.patch` is the retained J713 change against GravityLinux Mesa
26.3.0~devel-103. Context lines come from Mesa's Asahi Gallium driver, licensed MIT.
The original file notices are retained below. The patch does not transfer authorship of those files.

```text
agx_pipe.c
/*
 * Copyright 2010 Red Hat Inc.
 * Copyright 2014-2017 Broadcom
 * Copyright 2019-2020 Collabora, Ltd.
 * Copyright 2006 VMware, Inc.
 * SPDX-License-Identifier: MIT
 */

agx_blit.c
/*
 * Copyright 2021 Alyssa Rosenzweig
 * Copyright 2020-2021 Collabora, Ltd.
 * Copyright 2019 Sonny Jiang <sonnyj608@gmail.com>
 * Copyright 2019 Advanced Micro Devices, Inc.
 * Copyright 2014 Broadcom
 * SPDX-License-Identifier: MIT
 */
```

The accompanying `LICENSE.Mesa.MIT` reproduces the permission/disclaimer text from this repository's MIT
license; the above upstream copyright holders apply to their source context.
`bootloader-gpu1.patch` contains only the GPU file diff against retained Gravity m1n1 950e6b7.
Its upstream source license is MIT, with the Asahi Linux Contributors notice retained in
[the m1n1 license](../02-input/LICENSE.m1n1.MIT). It does not include Apple firmware.
