#pragma once
#include <math.h>

class SecondOrderLADRC {
public:
  struct Params {
    float b0;      // System acceleration gain
    float wc;      // Controller bandwidth
    float wo;      // Observer bandwidth
    float ts;      // Sample period
    float out_min; // Minimum actuator output limit
    float out_max; // Maximum actuator output limit
  };

  SecondOrderLADRC() = default;

  void init(const Params &p, float initial_position = 0.0f) {
    params = p;
    reset(initial_position);
    updateGains();
  }

  void reset(float initial_position = 0.0f) {
    z1 = initial_position;
    z2 = 0.0f;
    z3 = 0.0f;
    u_last = 0.0f;
  }

  void updateGains() {
    // Discrete pole-placement for Current LESO (Herbst, 2013)
    float z_eso = expf(-params.wo * params.ts);
    float one_m_z = 1.0f - z_eso;

    l1 = 1.0f - (z_eso * z_eso * z_eso);
    l2 = (1.5f / params.ts) * one_m_z * one_m_z * (1.0f + z_eso);
    l3 = (1.0f / (params.ts * params.ts)) * one_m_z * one_m_z * one_m_z;

    // Critically damped PD gains
    kp = params.wc * params.wc;
    kd = 2.0f * params.wc;
  }

  // Call strictly at fixed intervals of params.ts
  float update(float y_meas, float target_pos, float target_vel = 0.0f) {
    const float h = params.ts;
    const float h2_2 = 0.5f * h * h;

    // Predict (prior state before measurement)
    float b0_u = params.b0 * u_last;
    float z1_hat = z1 + h * z2 + h2_2 * (z3 + b0_u);
    float z2_hat = z2 + h * (z3 + b0_u);
    float z3_hat = z3;

    // Correct (posterior update using current measurement)
    float err = y_meas - z1_hat;
    z1 = z1_hat + l1 * err;
    z2 = z2_hat + l2 * err;
    z3 = z3_hat + l3 * err;

    // State feedback control law
    float u0 = kp * (target_pos - z1) + kd * (target_vel - z2);

    // Disturbance rejection & plant normalization
    float u = (u0 - z3) / params.b0;

    // Saturation & anti-windup
    if (u < params.out_min) {
      u_last = params.out_min;
    } else if (u > params.out_max) {
      u_last = params.out_max;
    } else {
      u_last = u;
    }

    return u_last;
  }

  // State telemetry
  float getEstimatedPosition() const { return z1; }
  float getEstimatedVelocity() const { return z2; }
  float getEstimatedDisturbance() const { return z3; }

private:
  Params params{};
  float l1 = 0.0f, l2 = 0.0f, l3 = 0.0f;
  float kp = 0.0f, kd = 0.0f;
  float z1 = 0.0f; // Position
  float z2 = 0.0f; // Velocity
  float z3 = 0.0f; // Total disturbance (gravity, friction, dynamics)
  float u_last = 0.0f;
};