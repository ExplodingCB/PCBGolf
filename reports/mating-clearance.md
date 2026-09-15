# Mating connector clearance

## Finding

The first 45×37 mm layout's OBD-C socket row had 11.3–11.7 mm spacing along the plug's wide axis. **This does not accommodate every compliant full-featured USB-C plug.** USB-IF Table B-1 specifies maximum overmold width **12.35 mm** and height **6.5 mm**. [Official compliance document, printed page49](https://www.usb.org/sites/default/files/USB%20Type-C_Compliance%20Document_Rev_2_1b_June_2021.pdf).

Comma describes OBD-C as a fully connected USB-C 3.1 Gen2 or 3.2 Gen2 cable. Its public hardware documentation does not provide an exact proprietary overmold drawing. [Comma hardware harness documentation](https://github.com/commaai/hardware/blob/master/harness/README.md).

## Corrected candidate

`reports/placement-45x37-mating.json` rotates all four OBD-C sockets by90° and places them at X=3.25,10.75,18.25,25.75 mm, Y=4.75 mm. Their **narrow-axis pitch is7.5 mm**. This provides1.0 mm between maximum-width USB-IF compliant overmolds in that direction.

The mechanical check deliberately enlarges the USB-IF cross section to **12.5×7.0 mm**, giving **0.5 mm interplug separation**. The rightmost envelope ends atX=29.25 mm; the actual tall barrel-jack model begins atX=29.6 mm, giving0.35 mm clearance. The cable bodies may overhang short components because the plug overmolds begin above the vertical USB sockets, roughly8.8 mm above the board. The audit starts them at8.6 mm to include an extra0.2 mm vertically.

J4 moves to the clear upper-right corner at(38,4), and the bottom MCU shifts toY=20.7 mm so all connector drill envelopes clear it. The board remains45×37 mm. The PNG shows elevated cable envelopes as dashed yellow rectangles. They are usability checks and are excluded from PCBA volume scoring.

## Scope

These calculations check simultaneous insertion geometry using conservative straight-plug envelopes and nominal component models. They do not establish insertion force, latch retention, cable bend space, or compatibility with unusually oversized/right-angle custom cable housings. A representative physical mating test remains part of final validation. The optional DNP J4 header requires its own mating-body model if populated.
