#pragma once

// PCBGolf STM32H725VGH6, four physical ports. See firmware/pcbgolf/pinmap.json.
// Deliberately distinct from Jungle v2 so a stock Jungle updater rejects it.
#define HW_TYPE_PCBGOLF_BGA100 0x80U
#define PCBGOLF_PORT_COUNT 4U
#define PCBGOLF_PORT_MASK 0x0FU
#define PCBGOLF_ADC(a, c) {.adc = (a), .channel = (c), .sample_time = SAMPLETIME_810_CYCLES, .oversampling = OVERSAMPLING_1}

uint8_t harness_orientation = HARNESS_ORIENTATION_NONE;
uint8_t can_mode = CAN_MODE_NORMAL;
uint8_t ignition = 0U;
uint8_t panda_power_bitmask = 0U;

gpio_t power_pins[] = {{GPIOA, 0}, {GPIOA, 1}, {GPIOA, 4}, {GPIOA, 5}};
gpio_t sbu1_ignition_pins[] = {{GPIOD, 0}, {GPIOD, 5}, {GPIOE, 6}, {GPIOD, 14}};
gpio_t sbu1_relay_pins[] = {{GPIOD, 1}, {GPIOD, 6}, {GPIOD, 11}, {GPIOD, 15}};
gpio_t sbu2_ignition_pins[] = {{GPIOD, 3}, {GPIOD, 8}, {GPIOD, 9}, {GPIOE, 0}};
gpio_t sbu2_relay_pins[] = {{GPIOD, 4}, {GPIOD, 10}, {GPIOE, 7}, {GPIOE, 1}};
gpio_t can_enable_pins[] = {{GPIOB, 7}, {GPIOB, 3}, {GPIOD, 7}, {GPIOB, 4}};

const adc_signal_t imon_channels[] = {
  PCBGOLF_ADC(ADC1, 4), PCBGOLF_ADC(ADC1, 5),
  PCBGOLF_ADC(ADC1, 9), PCBGOLF_ADC(ADC1, 3),
};
const adc_signal_t sbu1_channels[] = {
  PCBGOLF_ADC(ADC3, 0), PCBGOLF_ADC(ADC1, 7),
  PCBGOLF_ADC(ADC3, 10), PCBGOLF_ADC(ADC1, 8),
};
const adc_signal_t sbu2_channels[] = {
  PCBGOLF_ADC(ADC3, 1), PCBGOLF_ADC(ADC1, 14),
  PCBGOLF_ADC(ADC3, 11), PCBGOLF_ADC(ADC1, 15),
};

void pcbgolf_set_harness_orientation(uint8_t orientation) {
  if (orientation <= HARNESS_ORIENTATION_2) {
    // Break before make, including changes between the two orientations.
    gpio_set_all_output(sbu1_ignition_pins, PCBGOLF_PORT_COUNT, false);
    gpio_set_all_output(sbu2_ignition_pins, PCBGOLF_PORT_COUNT, false);
    gpio_set_all_output(sbu1_relay_pins, PCBGOLF_PORT_COUNT, false);
    gpio_set_all_output(sbu2_relay_pins, PCBGOLF_PORT_COUNT, false);
    if (orientation == HARNESS_ORIENTATION_1) {
      gpio_set_all_output(sbu1_relay_pins, PCBGOLF_PORT_COUNT, true);
      gpio_set_bitmask(sbu2_ignition_pins, PCBGOLF_PORT_COUNT, ignition);
    } else if (orientation == HARNESS_ORIENTATION_2) {
      gpio_set_all_output(sbu2_relay_pins, PCBGOLF_PORT_COUNT, true);
      gpio_set_bitmask(sbu1_ignition_pins, PCBGOLF_PORT_COUNT, ignition);
    } else {
      // NONE leaves all four switch groups off.
    }
    harness_orientation = orientation;
  }
}

void pcbgolf_enable_can_transceiver(uint8_t transceiver, bool enabled) {
  if ((transceiver >= 1U) && (transceiver <= 4U)) {
    gpio_t pin = can_enable_pins[transceiver - 1U];
    set_gpio_output(pin.bank, pin.pin, !enabled); // STBY is active high
  }
}

void pcbgolf_set_can_mode(uint8_t mode) {
  if ((mode != CAN_MODE_NORMAL) && (mode != CAN_MODE_OBD_CAN2)) {
    return;
  }
  pcbgolf_enable_can_transceiver(2U, false);
  pcbgolf_enable_can_transceiver(4U, false);
  const uint8_t pins[] = {5U, 6U, 12U, 13U};
  for (uint8_t i = 0U; i < 4U; i++) {
    set_gpio_pullup(GPIOB, pins[i], PULL_NONE);
    set_gpio_mode(GPIOB, pins[i], MODE_ANALOG);
  }
  uint8_t first = (mode == CAN_MODE_NORMAL) ? 5U : 12U;
  set_gpio_alternate(GPIOB, first, GPIO_AF9_FDCAN2);
  set_gpio_alternate(GPIOB, first + 1U, GPIO_AF9_FDCAN2);
  can_mode = mode;
  pcbgolf_enable_can_transceiver((mode == CAN_MODE_NORMAL) ? 2U : 4U, true);
}

void pcbgolf_set_panda_power(bool enable) {
  panda_power = enable;
  panda_power_bitmask = enable ? PCBGOLF_PORT_MASK : 0U;
  gpio_set_all_output(power_pins, PCBGOLF_PORT_COUNT, enable);
}

void pcbgolf_set_panda_individual_power(uint8_t port_num, bool enable) {
  if ((port_num >= 1U) && (port_num <= PCBGOLF_PORT_COUNT)) {
    uint8_t bit = 1U << (port_num - 1U);
    panda_power_bitmask = (panda_power_bitmask & ~bit) | (enable ? bit : 0U);
    panda_power = (panda_power_bitmask != 0U);
    gpio_set_bitmask(power_pins, PCBGOLF_PORT_COUNT, panda_power_bitmask);
  }
}

bool pcbgolf_get_button(void) {
  return get_gpio_input(GPIOE, 5); // PE5, external 10k pulldown, shared BOOT0
}

void pcbgolf_set_ignition(bool enable) {
  ignition = enable ? PCBGOLF_PORT_MASK : 0U;
  pcbgolf_set_harness_orientation(harness_orientation);
}

void pcbgolf_set_individual_ignition(uint8_t bitmask) {
  ignition = bitmask & PCBGOLF_PORT_MASK;
  pcbgolf_set_harness_orientation(harness_orientation);
}

float pcbgolf_get_channel_power(uint8_t channel) {
  // Retain the six-slot Jungle health wire layout: absent channels return zero.
  if ((channel < 1U) || (channel > PCBGOLF_PORT_COUNT)) {
    return 0.0f;
  }
  uint16_t millivolts = adc_get_mV(&imon_channels[channel - 1U]);
  // TPS25944 nominal 52.3 uA/A * R70..R73 10k = 523 mV/A.
  // No per-board offset/gain calibration yet; power assumes nominal 12 V input.
  return ((float)millivolts / 523.0f) * 12.0f;
}

uint16_t pcbgolf_get_sbu_mV(uint8_t channel, uint8_t sbu) {
  if ((channel < 1U) || (channel > PCBGOLF_PORT_COUNT)) {
    return 0U;
  }
  if (sbu == SBU1) {
    return adc_get_mV(&sbu1_channels[channel - 1U]);
  }
  if (sbu == SBU2) {
    return adc_get_mV(&sbu2_channels[channel - 1U]);
  }
  return 0U;
}

void pcbgolf_enable_header_pin(uint8_t pin_num, bool enabled) {
  // PCBGolf has no Jungle GPIO header. Never drive unrelated MCU balls.
  UNUSED(pin_num);
  UNUSED(enabled);
}

void pcbgolf_init(void) {
  gpio_usb_init();
  for (uint8_t i = 1U; i <= 4U; i++) {
    pcbgolf_enable_can_transceiver(i, false);
  }
  set_gpio_pullup(GPIOB, 8, PULL_NONE);
  set_gpio_pullup(GPIOB, 9, PULL_NONE);
  set_gpio_alternate(GPIOB, 8, GPIO_AF9_FDCAN1); // CAN0_RX
  set_gpio_alternate(GPIOB, 9, GPIO_AF9_FDCAN1); // CAN0_TX
  set_gpio_pullup(GPIOD, 12, PULL_NONE);
  set_gpio_pullup(GPIOD, 13, PULL_NONE);
  set_gpio_alternate(GPIOD, 12, GPIO_AF5_FDCAN3); // CAN2_RX
  set_gpio_alternate(GPIOD, 13, GPIO_AF5_FDCAN3); // CAN2_TX
  pcbgolf_set_can_mode(CAN_MODE_NORMAL);
  pcbgolf_enable_can_transceiver(1U, true);
  pcbgolf_enable_can_transceiver(3U, true);
  pcbgolf_set_harness_orientation(HARNESS_ORIENTATION_NONE);
  pcbgolf_set_panda_power(true); // preserve Jungle startup behavior
  set_gpio_mode(GPIOE, 5, MODE_INPUT);
  set_gpio_pullup(GPIOE, 5, PULL_NONE);

  adc_init(ADC1);
  adc_init(ADC3);
  // Direct PC2_C/PC3_C inputs: isolate the digital-pad analog switches.
  register_set_bits(&SYSCFG->PMCR, SYSCFG_PMCR_PC2SO | SYSCFG_PMCR_PC3SO);
  gpio_t analog_pins[] = {
    {GPIOC, 4}, {GPIOB, 1}, {GPIOB, 0}, {GPIOA, 6}, // IMON
    {GPIOC, 2}, {GPIOC, 3}, {GPIOA, 7}, {GPIOA, 2}, // SBU1/2 CH1/2
    {GPIOC, 0}, {GPIOC, 1}, {GPIOC, 5}, {GPIOA, 3}, // SBU1/2 CH3/4
  };
  for (uint8_t i = 0U; i < sizeof(analog_pins) / sizeof(gpio_t); i++) {
    set_gpio_pullup(analog_pins[i].bank, analog_pins[i].pin, PULL_NONE);
    set_gpio_mode(analog_pins[i].bank, analog_pins[i].pin, MODE_ANALOG);
  }
}

board board_pcbgolf = {
  .init = &pcbgolf_init,
  .led_GPIO = {GPIOE, GPIOE, GPIOE},
  .led_pin = {4, 3, 2},
  .get_button = &pcbgolf_get_button,
  .set_panda_power = &pcbgolf_set_panda_power,
  .set_panda_individual_power = &pcbgolf_set_panda_individual_power,
  .set_ignition = &pcbgolf_set_ignition,
  .set_individual_ignition = &pcbgolf_set_individual_ignition,
  .set_harness_orientation = &pcbgolf_set_harness_orientation,
  .set_can_mode = &pcbgolf_set_can_mode,
  .enable_can_transceiver = &pcbgolf_enable_can_transceiver,
  .enable_header_pin = &pcbgolf_enable_header_pin,
  .get_channel_power = &pcbgolf_get_channel_power,
  .get_sbu_mV = &pcbgolf_get_sbu_mV,
  .has_spi = false,
};
