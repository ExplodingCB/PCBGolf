# Experimental PCBGolf firmware

Source checkpoint for STM32H725VGH6 BGA100. Bootstub and application compiled and linked locally; hardware behavior and the complete pin map still require review and bench testing. This is not qualified firmware.

The build uses commaai/panda revision `78cf69904c332c599a297fcc2a09c08d10d429d5` and commaai/opendbc revision `057aee25b5eee7530f0b95b5b508c8c3247b0cd7`. Place the panda checkout at `tools/panda-firmware` and opendbc at `tools/panda-firmware/opendbc-src` relative to the repository root.

Apply `panda-changes.patch` inside the panda checkout, and copy `pcbgolf_bga100.h` to its `board/jungle/boards/` directory. The patch selects the PCBGolf board and overrides the historical TFBGA100 supply heuristic for the H725 SMPS and externally supplied USB rail.

`build.py` records the expected local Arm GNU 12.3.Rel1 Windows toolchain path and builds both images with `PCBGOLF_BGA100`. Generated outputs stay in the ignored `build/` directory. See `../../reports/firmware-build.json` for the saved compile result; it does not establish hardware correctness.
