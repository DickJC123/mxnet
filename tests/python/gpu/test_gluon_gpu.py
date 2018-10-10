# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

from __future__ import print_function
import sys
import os
import tempfile
import time
import multiprocessing as mp
import unittest
import mxnet as mx
import numpy as np
import unittest
import math
from nose.tools import assert_raises
from mxnet.test_utils import check_consistency, set_default_context, assert_almost_equal
from mxnet.base import MXNetError
from mxnet import autograd
from numpy.testing import assert_allclose


curr_path = os.path.dirname(os.path.abspath(os.path.expanduser(__file__)))
sys.path.insert(0, os.path.join(curr_path, '../unittest'))
from common import setup_module, with_seed, teardown, assert_raises_cudnn_disabled
from test_gluon import *
from test_loss import *
from test_gluon_rnn import *

set_default_context(mx.gpu(0))

def check_rnn_layer(layer):
    layer.collect_params().initialize(ctx=[mx.cpu(0), mx.gpu(0)])
    with mx.gpu(0):
        x = mx.nd.ones((10, 16, 30))
        states = layer.begin_state(16)
        go, gs = layer(x, states)

    with mx.cpu(0):
        x = mx.nd.ones((10, 16, 30))
        states = layer.begin_state(16)
        co, cs = layer(x, states)

    # atol of 1e-6 required, as exposed by seed 2124685726
    assert_almost_equal(go.asnumpy(), co.asnumpy(), rtol=1e-2, atol=1e-6)
    for g, c in zip(gs, cs):
        assert_almost_equal(g.asnumpy(), c.asnumpy(), rtol=1e-2, atol=1e-6)

@with_seed()
def check_rnn_layer_w_rand_inputs(layer):
    layer.collect_params().initialize(ctx=[mx.cpu(0), mx.gpu(0)])
    x = mx.nd.uniform(shape=(10, 16, 30))
    with mx.gpu(0):
        x = x.copyto(mx.gpu(0))
        states = layer.begin_state(16)
        go, gs = layer(x, states)

    with mx.cpu(0):
        x = x.copyto(mx.cpu(0))
        states = layer.begin_state(16)
        co, cs = layer(x, states)

    assert_almost_equal(go.asnumpy(), co.asnumpy(), rtol=1e-2, atol=1e-6)
    for g, c in zip(gs, cs):
        assert_almost_equal(g.asnumpy(), c.asnumpy(), rtol=1e-2, atol=1e-6)


@with_seed()
@assert_raises_cudnn_disabled()
def test_rnn_layer():
    check_rnn_layer(gluon.rnn.RNN(100, num_layers=3))
    check_rnn_layer(gluon.rnn.RNN(100, activation='tanh', num_layers=3))
    check_rnn_layer(gluon.rnn.LSTM(100, num_layers=3))
    check_rnn_layer(gluon.rnn.GRU(100, num_layers=3))

    check_rnn_layer(gluon.rnn.LSTM(100, num_layers=3, bidirectional=True))
    check_rnn_layer_w_rand_inputs(gluon.rnn.LSTM(100, num_layers=3, bidirectional=True))


@with_seed()
def test_gluon_ctc_consistency():
    loss = mx.gluon.loss.CTCLoss()
    data = mx.nd.arange(0, 4, repeat=40, ctx=mx.gpu(0)).reshape((2,20,4)).flip(axis=0)
    cpu_label = mx.nd.array([[2,1,-1,-1],[3,2,2,-1]], ctx=mx.cpu(0))
    gpu_label = mx.nd.array([[2,1,-1,-1],[3,2,2,-1]], ctx=mx.gpu(0))

    cpu_data = data.copy().as_in_context(mx.cpu(0))
    cpu_data.attach_grad()
    with mx.autograd.record():
        l_cpu = loss(cpu_data, cpu_label)
        l_cpu.backward()

    gpu_data = data.copyto(mx.gpu(0))
    gpu_data.attach_grad()
    with mx.autograd.record():
        l_gpu = loss(gpu_data, gpu_label)
        l_gpu.backward()

    assert_almost_equal(cpu_data.grad.asnumpy(), gpu_data.grad.asnumpy(), atol=1e-3, rtol=1e-3)


@with_seed()
def test_global_norm_clip_multi_device():
    for check_isfinite in [True, False]:
        x1 = mx.nd.ones((3,3), ctx=mx.gpu(0))
        x2 = mx.nd.ones((4,4), ctx=mx.cpu(0))
        norm = gluon.utils.clip_global_norm([x1, x2], 1.0, check_isfinite=check_isfinite)
        if check_isfinite:
            assert norm == 5.0
        else:
            assert norm.asscalar() == 5.0
        assert_almost_equal(x1.asnumpy(), np.ones((3, 3)) / 5)
        assert_almost_equal(x2.asnumpy(), np.ones((4, 4)) / 5)


def _check_batchnorm_result(input, num_devices=1, cuda=False):
    from mxnet.gluon.utils import split_and_load
    def _find_bn(module):
        if isinstance(module, (mx.gluon.nn.BatchNorm, mx.gluon.contrib.nn.SyncBatchNorm)):
            return module
        elif isinstance(module.module, (mx.gluon.nn.BatchNorm, mx.gluon.contrib.nn.SyncBatchNorm)):
            return module.module

        raise RuntimeError('BN not found')

    def _syncParameters(bn1, bn2, ctx):
        ctx = input.context
        bn2.gamma.set_data(bn1.gamma.data(ctx))
        bn2.beta.set_data(bn1.beta.data(ctx))
        bn2.running_mean.set_data(bn1.running_mean.data(ctx))
        bn2.running_var.set_data(bn1.running_var.data(ctx))

    input1 = input.copy()
    input2 = input.copy()

    if cuda:
        input1 = input.as_in_context(mx.gpu(0))
        ctx_list = [mx.gpu(i) for i in range(num_devices)]
    else:
        ctx_list = [mx.cpu(0) for _ in range(num_devices)]

    nch = input.shape[1]
    bn1 = mx.gluon.nn.BatchNorm(in_channels=nch)
    bn2 = mx.gluon.contrib.nn.SyncBatchNorm(in_channels=nch, num_devices=num_devices)

    bn1.initialize(ctx=ctx_list[0])
    bn2.initialize(ctx=ctx_list)

    # using the same values for gamma and beta
    #_syncParameters(_find_bn(bn1), _find_bn(bn2), ctx_list[0])

    input1.attach_grad()
    inputs2 = split_and_load(input2, ctx_list, batch_axis=0)
    for xi in inputs2:
        xi.attach_grad()

    with mx.autograd.record():
        output1 = bn1(input1)
        output2  = [bn2(xi) for xi in inputs2]
        loss1 = (output1 ** 2).sum()
        loss2 = [(output ** 2).sum() for output in output2]
        mx.autograd.backward(loss1)
        mx.autograd.backward(loss2)

    output2 = mx.nd.concat(*[output.as_in_context(input.context) for output in output2], dim=0)
    # assert forwarding
    assert_almost_equal(input1.asnumpy(), input2.asnumpy(), atol=1e-3, rtol=1e-3)
    assert_almost_equal(output1.asnumpy(), output2.asnumpy(), atol=1e-3, rtol=1e-3)
    assert_almost_equal(_find_bn(bn1).running_mean.data(ctx_list[0]).asnumpy(),
                        _find_bn(bn2).running_mean.data(ctx_list[0]).asnumpy(),
                        atol=1e-3, rtol=1e-3)
    assert_almost_equal(_find_bn(bn1).running_var.data(ctx_list[0]).asnumpy(),
                        _find_bn(bn2).running_var.data(ctx_list[0]).asnumpy(),
                        atol=1e-3, rtol=1e-3)
    input2grad = mx.nd.concat(*[output.grad.as_in_context(input.context) for output in inputs2], dim=0)
    assert_almost_equal(input1.grad.asnumpy(), input2grad.asnumpy(), atol=1e-3, rtol=1e-3)

@with_seed()
def test_sync_batchnorm():
    def get_num_devices():
        for i in range(100):
            try:
                mx.nd.zeros((1,), ctx=mx.gpu(i))
            except:
                return i
    # no need to use SyncBN with 1 gpu
    if get_num_devices() < 2:
        return
    ndev = 2
    # check with unsync version
    for i in range(10):
        _check_batchnorm_result(mx.nd.random.uniform(shape=(4, 1, 4, 4)),
                                num_devices=ndev, cuda=True)


@with_seed()
def test_symbol_block_fp16():
    # Test case to verify if initializing the SymbolBlock from a model with params
    # other than fp32 param dtype.

    # 1. Load a resnet model, cast it to fp16 and export
    tmp = tempfile.mkdtemp()
    tmpfile = os.path.join(tmp, 'resnet34_fp16')
    ctx = mx.gpu(0)

    net_fp32 = mx.gluon.model_zoo.vision.resnet34_v2(pretrained=True, ctx=ctx, root=tmp)
    net_fp32.cast('float16')
    net_fp32.hybridize()
    data = mx.nd.zeros((1,3,224,224), dtype='float16', ctx=ctx)
    net_fp32.forward(data)
    net_fp32.export(tmpfile, 0)

    # 2. Load the saved model and verify if all the params are loaded correctly.
    # and choose one of the param to verify the type if fp16.
    sm = mx.sym.load(tmpfile + '-symbol.json')
    inputs = mx.sym.var('data', dtype='float16')
    net_fp16 = mx.gluon.SymbolBlock(sm, inputs)
    net_fp16.collect_params().load(tmpfile + '-0000.params', ctx=ctx)
    # 3. Get a conv layer's weight parameter name. Conv layer's weight param is
    # expected to be of dtype casted, fp16.
    for param_name in net_fp16.params.keys():
        if 'conv' in param_name and 'weight' in param_name:
            break
    assert np.dtype(net_fp16.params[param_name].dtype) == np.dtype(np.float16)


@with_seed()
def test_large_models():
    ctx = default_context()
    # Create model
    net = gluon.nn.HybridSequential()

    largest_num_features = 256
    with net.name_scope():
        net.add(nn.Conv2D(128, 3))
        net.add(nn.LeakyReLU(0.1))
        net.add(nn.Conv2D(largest_num_features, 3))
        net.add(nn.LeakyReLU(0.1))
        net.add(nn.Conv2D(1, 3))

    net.hybridize()
    net.initialize(mx.init.Normal(sigma=0.01), ctx=ctx)
    mx.nd.waitall()

    # The idea is to create models with large tensors of (say) 20% of the total memory.
    # This in the past has given cudnnFind() trouble when it needed to allocate similar I/O's
    # from the area carved out by the MXNET_GPU_MEM_POOL_RESERVE setting (by default 5%).
    def tensor_size(memory_fraction):
        bytes_per_float = 4
        (free_mem_bytes, total_mem_bytes) = mx.context.gpu_memory_info(ctx.device_id)
        big_tensor_size = total_mem_bytes * memory_fraction
        sz = int(math.sqrt(big_tensor_size / largest_num_features / bytes_per_float))
        return (sz // 100) * 100

    start_size = tensor_size(0.20)
    num_trials = 4
    for i in range(num_trials):
        sz = start_size - 10 * i
        (height, width) = (sz,sz)
        print("Testing model with input = {}x{}".format(height,width))
        data_in = nd.random_uniform(low=0, high=255, shape=(1, 3, height, width),
                                    ctx=ctx, dtype="float32")
        # Evaluate model
        net(data_in).asnumpy()


if __name__ == '__main__':
    import nose
    nose.runmodule()
