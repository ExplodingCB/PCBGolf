# STM32H725VGH6 supply check

The TFBGA100 package keeps the direct-SMPS circuit. Its USB supply is E8/VDD33USB; there is no VDD50USB ball. Preserve E8 on +3V3. Table 8 confirms the package terminals, and Table 12 requires 3.0–3.6 V for an active USB transceiver. [ST DS13311 Rev 5](https://www.st.com/resource/en/datasheet/stm32h725ag.pdf)

AN5419 permits external 3.3 V at VDD33USB. Tie VDD50USB to it only on packages where that pin exists; its absence requires no new 5 V connection. Keep the internal USB regulator disabled and configure USB supply readiness according to the reference manual. Provide 1 µF and 100 nF locally at E8. [ST AN5419 Rev 3, Table 2 and §2.1.4](https://www.st.com/resource/en/application_note/an5419-getting-started-with-stm32h723733-stm32h725735-and-stm32h730-value-line-hardware-development-stmicroelectronics.pdf)

For direct SMPS, preserve VDDSMPS→+3V3, VSSSMPS→GND, VLXSMPS→L4 switch side, and VFBSMPS/all VCAP/all VDDLDO→the L4 output net currently named VDDLDO. Firmware must select direct SMPS and disable the LDO. The connection applies to LQFP/BGA packages. Place the inductor, input/output capacitors and feedback close to the balls; reconnect every supply ball. [ST AN5419, Figure 5 and §2.1.6](https://www.st.com/resource/en/application_note/an5419-getting-started-with-stm32h723733-stm32h725735-and-stm32h730-value-line-hardware-development-stmicroelectronics.pdf)

The remap changes the supply-pin count. Existing total capacitance is not a substitute for a placement check: redistribute the available 100 nF capacitors beside each connected VDD/VCAP ball, retain output bulk, and verify effective capacitance under bias. L3 is the analog-supply ferrite; L4 is the MCU switching inductor. This is a schematic review, not a completed layout or boot test.
