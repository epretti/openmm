#ifndef OPENMM_REFERENCELCPOIXN_H_
#define OPENMM_REFERENCELCPOIXN_H_

/* -------------------------------------------------------------------------- *
 *                                   OpenMM                                   *
 * -------------------------------------------------------------------------- *
 * This is part of the OpenMM molecular simulation toolkit.                   *
 * See https://openmm.org/development.                                        *
 *                                                                            *
 * Portions copyright (c) 2025 Stanford University and the Authors.           *
 * Authors: Evan Pretti                                                       *
 * Contributors:                                                              *
 *                                                                            *
 * Permission is hereby granted, free of charge, to any person obtaining a    *
 * copy of this software and associated documentation files (the "Software"), *
 * to deal in the Software without restriction, including without limitation  *
 * the rights to use, copy, modify, merge, publish, distribute, sublicense,   *
 * and/or sell copies of the Software, and to permit persons to whom the      *
 * Software is furnished to do so, subject to the following conditions:       *
 *                                                                            *
 * The above copyright notice and this permission notice shall be included in *
 * all copies or substantial portions of the Software.                        *
 *                                                                            *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR *
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,   *
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL    *
 * THE AUTHORS, CONTRIBUTORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,    *
 * DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR      *
 * OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE  *
 * USE OR OTHER DEALINGS IN THE SOFTWARE.                                     *
 * -------------------------------------------------------------------------- */

#include <array>
#include <vector>
#include "openmm/Vec3.h"

namespace OpenMM {

/**
 * Performs energy and force calculations for the reference LCPOForce kernel.
 */
class ReferenceLCPOIxn {
public:
    ReferenceLCPOIxn(const std::vector<int>& indices, const std::vector<int>& particles, const std::vector<std::array<double, 4> >& parameters, double cutoff, bool usePeriodic);
    double execute(const Vec3* boxVectors, const std::vector<Vec3>& posData, std::vector<Vec3>& forceData, bool includeForces, bool includeEnergy);

private:
    static const int RadiusIndex = 0;
    static const int P2Index = 1;
    static const int P3Index = 2;
    static const int P4Index = 3;

    int numParticles;
    int numActiveParticles;
    const std::vector<int>& indices;
    const std::vector<int>& particles;
    const std::vector<std::array<double, 4> >& parameters;
    double cutoff;
    bool usePeriodic;
};

} // namespace OpenMM

#endif // OPENMM_REFERENCELCPOIXN_H_
