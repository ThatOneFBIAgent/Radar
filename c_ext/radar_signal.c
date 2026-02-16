/*
 * radar_signal.c — Signal processing utilities for Radar.
 *
 * Provides Exponential Moving Average (EMA) smoothing for
 * weather data streams, used for smooth visual transitions
 * on gauge displays.
 *
 * Build with: python c_ext/build_c.py
 */

#include "radar_signal.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>

/*
 * Exponential Moving Average (EMA) smoothing.
 *
 * Smooths an array of doubles using the EMA formula:
 *   out[0] = data[0]
 *   out[i] = alpha * data[i] + (1 - alpha) * out[i-1]
 *
 * @param data   Input data array
 * @param len    Length of the array
 * @param alpha  Smoothing factor (0.0 → max smooth, 1.0 → no smoothing)
 * @param out    Output array (must be pre-allocated, same length as data)
 */
void ema_smooth(const double* data, int len, double alpha, double* out) {
    if (len <= 0 || data == NULL || out == NULL) {
        return;
    }

    /* Clamp alpha to valid range */
    if (alpha < 0.0) alpha = 0.0;
    if (alpha > 1.0) alpha = 1.0;

    out[0] = data[0];
    for (int i = 1; i < len; i++) {
        out[i] = alpha * data[i] + (1.0 - alpha) * out[i - 1];
    }
}

/*
 * Weighted Moving Average (WMA) smoothing.
 *
 * @param data      Input data array
 * @param len       Length of the array
 * @param window    Window size for averaging
 * @param out       Output array (pre-allocated)
 */
void wma_smooth(const double* data, int len, int window, double* out) {
    if (len <= 0 || window <= 0 || data == NULL || out == NULL) {
        return;
    }

    if (window > len) window = len;

    double weight_sum = (double)(window * (window + 1)) / 2.0;

    for (int i = 0; i < len; i++) {
        double weighted = 0.0;
        double w_total = 0.0;
        int start = (i - window + 1 > 0) ? i - window + 1 : 0;

        for (int j = start; j <= i; j++) {
            double w = (double)(j - start + 1);
            weighted += data[j] * w;
            w_total += w;
        }

        out[i] = weighted / w_total;
    }
}

/*
 * Compute magnitude from 3D seismic components.
 *
 * Given arrays of X, Y, Z acceleration values, compute the
 * magnitude: sqrt(x^2 + y^2 + z^2) for each sample.
 *
 * @param x, y, z   Component arrays
 * @param len       Length of arrays
 * @param out       Output magnitude array (pre-allocated)
 */
void compute_magnitude(
    const double* x, const double* y, const double* z,
    int len, double* out
) {
    if (len <= 0 || x == NULL || y == NULL || z == NULL || out == NULL) {
        return;
    }

    for (int i = 0; i < len; i++) {
        out[i] = sqrt(x[i] * x[i] + y[i] * y[i] + z[i] * z[i]);
    }
}
