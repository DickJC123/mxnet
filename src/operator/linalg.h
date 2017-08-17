/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

/*!
 * \file linalg.h
 * \brief Unified tensor interface for advanced linear algebra functions
 * (specifically BLAS3/LAPACK) from within mxnet.
 */
#ifndef MXNET_OPERATOR_LINALG_H_
#define MXNET_OPERATOR_LINALG_H_

#include <mshadow/tensor.h>
#include <mxnet/op_attr_types.h>

#include "./c_lapack_api.h"
using namespace mshadow;

// The purpose of this header is to expose the interfaces of the advanced
// linear algebra functions without clutter by the implementations. In contrast
// to the implementations in linalg_inline.h, no macros are used to generate
// similar functions that just differ by name/type in order to improve readability.
//
// Guidelines for extensions:
// For any type of computation the following should be provided at minimum:
//   - 1 templated function supporting cpu/gpu float/double in non-batch mode
//   - 1 templated function supporting cpu/gpu float/double in batch mode
// Naming conventions:
//   - linalg_<func>()
//   - linalg_batch_<func>()
// Signatures of CPU/GPU versions should be equivalent whenever possible including
// that a stream is supplied to the cpu-versions as (optional) last argument.
// The batched versions all work on tensors with one more dimension as the
// non-batched ones and the first/highest dimension iterates over the elements
// within the batch.

//////////////////////////////// GEMM ////////////////////////////////////////////

// CPU/GPU-versions of BLAS3 function "gemm". Please refer to the BLAS3-documentation
// for further information about the function and its parameters.
// Note that this is C = gemm(A,B,C), so C is input and output parameter.
template<typename xpu, typename DType>
void linalg_gemm(const Tensor<xpu, 2, DType>& A, const Tensor<xpu, 2, DType>& B,
                 const Tensor<xpu, 2, DType>& C, DType alpha, DType beta,
                 bool tA, bool tB, Stream<xpu> *s = 0);

template<typename xpu, typename DType>
void linalg_batch_gemm(const Tensor<xpu, 3, DType>& A, const Tensor<xpu, 3, DType>& B,
                       const Tensor<xpu, 3, DType>& C, DType alpha, DType beta,
                       bool tA, bool tB, Stream<xpu> *s = 0);

// Class designed to wrap Tensor objects to mark whether they should be transposed.
// Generally, users should create these objects by calling Transpose() functions below.
template <typename T>
class TransposeTensor {
 public:
  explicit TransposeTensor(const T &self) : self_(self) {}
  const T &tensor() const { return self_; }
 private:
  const T &self_;
};

// Signatures for Transpose() for the two anticipated Tensor argument types.
template<typename xpu, typename DType>
inline TransposeTensor<Tensor<xpu, 2, DType>> Transpose(const Tensor<xpu, 2, DType> &self) {
  return TransposeTensor<Tensor<xpu, 2, DType>>(self);
}
template<typename xpu, typename DType>
inline TransposeTensor<Tensor<xpu, 3, DType>> Transpose(const Tensor<xpu, 3, DType> &self) {
  return TransposeTensor<Tensor<xpu, 3, DType>>(self);
}

// 4 flavors of the linalg_gemm interface based on desire to transpose A and/or B.
template<typename xpu, typename DType>
inline void linalg_gemm(const Tensor<xpu, 2, DType>& A,
                        const Tensor<xpu, 2, DType>& B,
                        const Tensor<xpu, 2, DType>& C,
                        Stream<xpu> *s = 0,
                        mxnet::OpReqType req = mxnet::kWriteTo);
template<typename xpu, typename DType>
inline void linalg_gemm(const TransposeTensor<Tensor<xpu, 2, DType>>& A,
                        const Tensor<xpu, 2, DType>& B,
                        const Tensor<xpu, 2, DType>& C,
                        Stream<xpu> *s = 0,
                        mxnet::OpReqType req = mxnet::kWriteTo);
template<typename xpu, typename DType>
inline void linalg_gemm(const Tensor<xpu, 2, DType>& A,
                        const TransposeTensor<Tensor<xpu, 2, DType>>& B,
                        const Tensor<xpu, 2, DType>& C,
                        Stream<xpu> *s = 0,
                        mxnet::OpReqType req = mxnet::kWriteTo);
template<typename xpu, typename DType>
inline void linalg_gemm(const TransposeTensor<Tensor<xpu, 2, DType>>& A,
                        const TransposeTensor<Tensor<xpu, 2, DType>>& B,
                        const Tensor<xpu, 2, DType>& C,
                        Stream<xpu> *s = 0,
                        mxnet::OpReqType req = mxnet::kWriteTo);

//////////////////////////////// TRSM ////////////////////////////////////////////

// CPU/GPU-versions of BLAS3 function "trsm". Please refer to the BLAS3-documentation
// for further information about the function and its parameters.
// Note that this is B = trsm(A,B), so B is input and output parameter.
template<typename xpu, typename DType>
void linalg_trsm(const Tensor<xpu, 2, DType>& A, const Tensor<xpu, 2, DType>& B,
                 DType alpha, bool rightside, bool lower, bool transpose, Stream<xpu> *s = 0);

template<typename xpu, typename DType>
inline void linalg_batch_trsm(const Tensor<xpu, 3, DType>& A, const Tensor<xpu, 3, DType>& B,
                   DType alpha, bool rightside, bool lower, bool transpose, Stream<xpu> *s = 0);

//////////////////////////////// TRMM ////////////////////////////////////////////

// CPU/GPU-versions of BLAS3 function "trmm". Please refer to the BLAS3-documentation
// for further information about the function and its parameters.
// Note that this is B = trmm(A,B), so B is input and output parameter.

template<typename xpu, typename DType>
void linalg_trmm(const Tensor<xpu, 2, DType>& A, const Tensor<xpu, 2, DType>& B,
                 DType alpha, bool rightside, bool lower, bool transpose, Stream<xpu> *s = 0);

template<typename xpu, typename DType>
void linalg_batch_trmm(const Tensor<xpu, 3, DType>& A, const Tensor<xpu, 3, DType>& B,
                    DType alpha, bool rightside, bool lower, bool transpose, Stream<xpu> *s = 0);

//////////////////////////////// POTRF ////////////////////////////////////////////

// CPU/GPU-versions of LAPACK function "potrf". Please refer to the LAPACK-documentation
// for further information about the function and its parameters.
// Note that this is A = potrf(A), so A is input and output parameter.

template<typename xpu, typename DType>
void linalg_potrf(const Tensor<xpu, 2, DType>& A, bool lower, Stream<xpu> *s = 0);

template<typename xpu, typename DType>
void linalg_batch_potrf(const Tensor<xpu, 3, DType>& A, bool lower, Stream<xpu> *s = 0);

//////////////////////////////// POTRI ////////////////////////////////////////////

// CPU/GPU-versions of LAPACK function "potri". Please refer to the LAPACK-documentation
// for further information about the function and its parameters.
// Note that this is A = potri(A), so A is input and output parameter.

template<typename xpu, typename DType>
void linalg_potri(const Tensor<xpu, 2, DType>& A, bool lower, Stream<xpu> *s = 0);

template<typename xpu, typename DType>
void linalg_batch_potri(const Tensor<xpu, 3, DType>& A, bool lower, Stream<xpu> *s = 0);

#include "linalg_impl.h"

#endif  // MXNET_OPERATOR_LINALG_H_
