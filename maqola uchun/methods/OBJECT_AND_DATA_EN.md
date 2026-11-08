# Object and data

**What is compressed.** 3D neuron object-ID segmentation maps (dense label volumes in which every voxel carries the ID
of the neurite it belongs to). They are not electron-microscopy intensity images; no RGB or medical intensity data is
used. Every encoding is lossless: the decoded volume equals the input voxel by voxel, and object IDs and boundaries
are preserved exactly.

**Codec.** Crackle (seung-lab, pinned commit 14b39b1): crack-code boundaries plus a label section. CAPE chooses the
records of the PINS label section; the stream is decoded by the unmodified upstream decoder.

**Datasets** (Table T01):
- j0126 zebra finch Area X, SBEM (Januszewski et al. 2018): 33 dense manual ground-truth volumes, uint64; the NEW
  primary test (never used before the final run).
- SNEMI3D (Kasthuri et al. 2015 / SNEMI3D challenge): 32 crops + the full training volume and 4 subvolumes, uint16;
  previously seen (the v3 holdout), so secondary.
- Janelia hemibrain v1.2 (Scheffer et al. 2020), FIB-SEM 8 nm: 4 pre-registered 512x512x256 cutouts, uint64,
  proofread automated segmentation; descriptive.
- Development only: CREMI A/B/C and the Crackle repository samples.

**Not applied to.** Intensity images, RGB, medical images, streaming/partial decoding (not implemented), GPU codecs.
