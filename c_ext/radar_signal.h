/*
 * radar_signal.h — Header for signal processing utilities.
 */

#ifndef RADAR_SIGNAL_H
#define RADAR_SIGNAL_H

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Exponential Moving Average smoothing.
 * alpha: 0.0 (max smooth) → 1.0 (no smoothing)
 */
void ema_smooth(const double *data, int len, double alpha, double *out);

/*
 * Weighted Moving Average smoothing.
 * window: number of samples for the averaging window.
 */
void wma_smooth(const double *data, int len, int window, double *out);

/*
 * Compute magnitude from 3D components.
 * out[i] = sqrt(x[i]^2 + y[i]^2 + z[i]^2)
 */
void compute_magnitude(const double *x, const double *y, const double *z,
                       int len, double *out);

#ifdef __cplusplus
}
#endif

#endif /* RADAR_SIGNAL_H */
