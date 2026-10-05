# Heron-2 Survey Drone User Manual

The Heron-2 is a quadcopter built by Tidewater Robotics for coastal mapping and inspection work. This manual covers specifications, flight limits, battery care, error codes and maintenance.

## Specifications

The Heron-2 weighs 1.9 kg with the battery installed and can carry a payload of up to 600 g. Its maximum horizontal speed is 18 m/s in Sport mode and 12 m/s in Survey mode. The standard camera is a 24 megapixel sensor with a mechanical shutter. Positioning uses dual-band GNSS with an optional RTK module that improves horizontal accuracy to 2 cm.

## Flight Limits

Do not take off when the sustained wind speed is above 11 m/s. The drone will refuse to arm if its own wind estimate is above 14 m/s. The operating temperature range is -10 °C to 40 °C. The maximum operating altitude is 4,000 m above sea level, and the default height limit above the take-off point is 120 m. The Heron-2 has an IP54 rating: it tolerates light rain and spray but must not be flown in heavy rain or landed on water.

## Battery

### Flight Time

A fully charged TB-48 battery gives about 42 minutes of flight in calm conditions without a payload. With the maximum payload, expect about 31 minutes. The drone starts an automatic return to home when the battery reaches 20 percent and lands in place at 8 percent.

### Charging

The TB-48 charges from empty to full in 70 minutes with the supplied 100 W charger. Charge batteries only between 5 °C and 40 °C. Do not charge a battery that is still warm from a flight; wait at least 15 minutes after landing.

### Storage

For storage longer than ten days, keep batteries at 50 to 60 percent charge. A battery left fully charged discharges itself to 60 percent after five days to protect the cells. Replace a battery after 300 charge cycles or when its reported health falls below 80 percent.

## Pre-flight Checklist

1. Check that all four propellers are undamaged and locked.
2. Confirm at least 12 satellites are locked before take-off.
3. Calibrate the compass if you have travelled more than 50 km since the last flight.
4. Verify that the return-to-home altitude is higher than the tallest obstacle nearby.
5. Check that the memory card has at least 8 GB free.

## Error Codes

The status screen shows an error code when the drone refuses to arm or aborts a mission.

- E-104: Compass interference. Move away from metal structures and recalibrate.
- E-210: Motor 3 over-temperature. Land and let the motors cool for ten minutes.
- E-417: Geofence database out of date. Connect the controller to the internet and sync.
- E-530: Gimbal lock engaged. Remove the gimbal clamp before powering on.
- E-622: Battery cell imbalance greater than 0.3 V. Do not fly; retire the battery.

## Maintenance

Replace propellers every 200 flight hours or immediately after any impact. Inspect the motor bearings every 100 flight hours. The airframe is under warranty for 24 months and batteries for 12 months. Firmware updates are published in the release notes; install them with the Tidewater Ground app over USB-C.
