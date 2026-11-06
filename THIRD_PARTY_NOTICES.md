# Third-party notices

CAPE-Pins compiles parts of the pinned upstream Crackle sources into its native modules and
calls other codecs as libraries or external processes. Vendor source trees are fetched by
`scripts/fetch_sources.py` at the commits in `sources.lock.json`; they are **not** included in
the release ZIPs. Datasets are never redistributed.

## Compiled into `cape/_cape_native` and `cape/_crackle_vendor`

| Component | Files | License | Notes |
|---|---|---|---|
| Crackle (William Silversmith, Seung Lab) | `vendor/crackle/src/*.hpp` @ 14b39b196a14b3b1ba7d1cd34f350c324308000f | BSD-3-Clause | unmodified; our glue: `cpp/bridge/crackle_vendor_bindings.cpp`, `cpp/src/upstream_bridge.cpp` |
| reduced cc3d (William Silversmith) | `vendor/crackle/src/cc3d.hpp` | **LGPL-3.0** | template code from a header; LGPLv3 section 3 applies: this notice + the LGPL/GPL texts (https://www.gnu.org/licenses/lgpl-3.0.html, https://www.gnu.org/licenses/gpl-3.0.html) accompany the binaries; the unmodified source is obtainable from the pinned commit |
| robin_hood hashing (Martin Ankerl) | `vendor/crackle/src/robin_hood.hpp` | MIT | |
| fastcrc CRC32C | `vendor/crackle/third_party/fastcrc/*.h` | MIT | |
| ThreadPool (Jakob Progsch, Václav Zeman) | `vendor/crackle/src/threadpool.hpp` | zlib | |
| pybind11 | headers | BSD-3-Clause | |

Crackle BSD-3-Clause license text (vendor/crackle/LICENSE):

```
BSD 3-Clause License

Copyright (c) 2022,2023 William Silversmith
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

## Used as installed Python packages (pinned with hashes in `requirements.lock`)

crackle-codec 0.53.0 (BSD-3-Clause), compresso (seung-lab), compressed-segmentation (seung-lab),
zstandard, blosc2 / c-blosc2 (BSD-3-Clause), OR-Tools (Apache-2.0), numpy, scipy, pandas,
matplotlib, h5py, tifffile, PyYAML, jsonschema, psutil, pytest, hypothesis, scikit-build-core,
cmake, ninja — each under its own license as distributed on PyPI.

## External process only (not linked, not redistributed)

| Component | License | Use |
|---|---|---|
| Volcanite (Max Piochowiak) | GPL-3.0 | CSGV / CSGV-R comparator, called as a separate executable when built |

## Original works cited (not used as code)

Compresso original implementation (VCG/compresso, MIT) is cited as the method's source; the
measured implementation is the PyPI `compresso` package.
