#ifndef __OPENMM_OPENCLSORT_H__
#define __OPENMM_OPENCLSORT_H__

/* -------------------------------------------------------------------------- *
 *                                   OpenMM                                   *
 * -------------------------------------------------------------------------- *
 * This is part of the OpenMM molecular simulation toolkit originating from   *
 * Simbios, the NIH National Center for Physics-Based Simulation of           *
 * Biological Structures at Stanford, funded under the NIH Roadmap for        *
 * Medical Research, grant U54 GM072970. See https://simtk.org.               *
 *                                                                            *
 * Portions copyright (c) 2010-2025 Stanford University and the Authors.      *
 * Authors: Peter Eastman                                                     *
 * Contributors:                                                              *
 *                                                                            *
 * This program is free software: you can redistribute it and/or modify       *
 * it under the terms of the GNU Lesser General Public License as published   *
 * by the Free Software Foundation, either version 3 of the License, or       *
 * (at your option) any later version.                                        *
 *                                                                            *
 * This program is distributed in the hope that it will be useful,            *
 * but WITHOUT ANY WARRANTY; without even the implied warranty of             *
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the              *
 * GNU Lesser General Public License for more details.                        *
 *                                                                            *
 * You should have received a copy of the GNU Lesser General Public License   *
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.      *
 * -------------------------------------------------------------------------- */

#include "OpenCLArray.h"
#include "OpenCLContext.h"
#include "openmm/common/ComputeSort.h"
#include "openmm/common/windowsExportCommon.h"

namespace OpenMM {

/**
 * This class sorts arrays of values.  It supports any type of values, not just scalars,
 * so long as an appropriate sorting key can be defined by which to sort them.
 * 
 * The sorting behavior is specified by a "trait" class that defines the type of data to
 * sort and the key for sorting it.  Here is an example of a trait class for
 * sorting floats:
 * 
 * class FloatTrait : public ComputeSortImpl::SortTrait {
 *     int getDataSize() const {return 4;}
 *     int getKeySize() const {return 4;}
 *     const char* getDataType() const {return "float";}
 *     const char* getKeyType() const {return "float";}
 *     const char* getMinKey() const {return "-MAXFLOAT";}
 *     const char* getMaxKey() const {return "MAXFLOAT";}
 *     const char* getMaxValue() const {return "MAXFLOAT";}
 *     const char* getSortKey() const {return "value";}
 * };
 *
 * The algorithm used is a bucket sort, followed by a bitonic sort within each bucket
 * (in local memory when possible, in global memory otherwise).  This is similar to
 * the algorithm described in
 *
 * Shifu Chen, Jing Qin, Yongming Xie, Junping Zhao, and Pheng-Ann Heng.  "An Efficient
 * Sorting Algorithm with CUDA"  Journal of the Chinese Institute of Engineers, 32(7),
 * pp. 915-921 (2009)
 *
 * but with many modifications and simplifications.  In particular, this algorithm
 * involves much less communication between host and device, which is critical to get
 * good performance with the array sizes we typically work with (10,000 to 100,000
 * elements).
 */
    
class OPENMM_EXPORT_COMMON OpenCLSort : public ComputeSortImpl {
public:
    /**
     * Create an OpenCLSort object for sorting data of a particular type.
     *
     * @param context    the context in which to perform calculations
     * @param trait      a SortTrait defining the type of data to sort.  It should have been allocated
     *                   on the heap with the "new" operator.  This object takes over ownership of it,
     *                   and deletes it when the OpenCLSort is deleted.
     * @param length     the length of the arrays this object will be used to sort
     * @param uniform    whether the input data is expected to follow a uniform or nonuniform
     *                   distribution.  This argument is used only as a hint.  It allows parts
     *                   of the algorithm to be tuned for faster performance on the expected
     *                   distribution.
     */
    OpenCLSort(OpenCLContext& context, ComputeSortImpl::SortTrait* trait, unsigned int length, bool uniform=true);
    ~OpenCLSort();
    /**
     * Sort an array.
     */
    void sort(ArrayInterface& data);
private:
    OpenCLContext& context;
    ComputeSortImpl::SortTrait* trait;
    OpenCLArray dataRange;
    OpenCLArray bucketOfElement;
    OpenCLArray offsetInBucket;
    OpenCLArray bucketOffset;
    OpenCLArray buckets;
    cl::Kernel shortListKernel, shortList2Kernel, computeRangeKernel, assignElementsKernel, computeBucketPositionsKernel, copyToBucketsKernel, sortBucketsKernel;
    unsigned int dataLength, rangeKernelSize, positionsKernelSize, sortKernelSize;
    bool isShortList, useShortList2, uniform;
};

} // namespace OpenMM

#endif // __OPENMM_OPENCLSORT_H__
