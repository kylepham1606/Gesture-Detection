import tensorflow as tf
import numpy as np
from tensorflow.python.client import device_lib
import os


def getKernel(name, shape):
    kernel = tf.get_variable(name, shape, tf.float32, tf.contrib.layers.xavier_initializer(uniform=True,
                                                                                           seed=None,
                                                                                           dtype=tf.float32))

    return kernel


def _bias_variable(name, shape):
    return tf.get_variable(name, shape, tf.float32, tf.constant_initializer(0.1, dtype=tf.float32))


# block 1

def conv3DBlock(prev_layer, layer_name, in_filters, out_filters):
    with tf.variable_scope(layer_name):
        kernel_shape = 3
        kernel_name = "weights"
        conv_stride = [1, 1, 1, 1, 1]

        kernel = getKernel(kernel_name, [kernel_shape, kernel_shape, kernel_shape, in_filters, out_filters])
        prev_layer = tf.nn.conv3d(prev_layer, kernel, strides=conv_stride, padding="SAME")
        prev_layer = tf.layers.batch_normalization(prev_layer, training=True)
        biases = _bias_variable('biases', [out_filters])
        prev_layer = tf.nn.bias_add(prev_layer, biases)
        prev_layer = tf.nn.relu(prev_layer)

    return prev_layer


def maxPool3DBlock(prev_layer, ksize, pool_stride):
    prev_layer = tf.nn.max_pool3d(prev_layer, ksize, pool_stride, padding="VALID")

    return prev_layer


def inference(video):
    os.environ['CUDA_VISIBLE_DEVICES'] = "1"
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = "2"
    print(device_lib.list_local_devices())

    num_classes = 249

    prev_layer = video
    in_filters = 3

    # block 1
    out_filters = 32
    layer_name = "conv1a"
    prev_layer = conv3DBlock(prev_layer, layer_name, in_filters, out_filters)
    prev_layer = maxPool3DBlock(prev_layer, [1, 1, 2, 2, 1], [1, 1, 2, 2, 1])
    in_filters = out_filters
    print(prev_layer.get_shape())

    # block 2
    out_filters = 64
    layer_name = "conv2a"
    prev_layer = conv3DBlock(prev_layer, layer_name, in_filters, out_filters)
    prev_layer = maxPool3DBlock(prev_layer, [1, 2, 2, 2, 1], [1, 2, 2, 2, 1])
    in_filters = out_filters
    print(prev_layer.get_shape())

    # block 3
    out_filters = 128
    layer_name = "conv3a"
    prev_layer = conv3DBlock(prev_layer, layer_name, in_filters, out_filters)
    prev_layer = maxPool3DBlock(prev_layer, [1, 2, 2, 2, 1], [1, 2, 2, 2, 1])
    in_filters = out_filters
    print(prev_layer.get_shape())

    # block 4
    out_filters = 256
    layer_name = "conv4a"
    prev_layer = conv3DBlock(prev_layer, layer_name, in_filters, out_filters)
    prev_layer = maxPool3DBlock(prev_layer, [1, 2, 2, 2, 1], [1, 2, 2, 2, 1])
    in_filters = out_filters
    print(prev_layer.get_shape())

    with tf.variable_scope('Global_Avg_Pool'):
        pool_stride = [1, 1, 1, 1, 1]
        ksize = [1, prev_layer.get_shape().as_list()[1], prev_layer.get_shape().as_list()[2],
                 prev_layer.get_shape().as_list()[3], 1]
        prev_layer = tf.nn.avg_pool3d(prev_layer, ksize, pool_stride, padding='VALID')
        print(prev_layer.get_shape())

    with tf.variable_scope('fc1'):
        dim = np.prod(prev_layer.get_shape().as_list()[1:])
        prev_layer_flat = tf.reshape(prev_layer, [-1, dim])
        weights = getKernel('weights', [dim, 256])
        biases = _bias_variable('biases', [256])
        prev_layer = tf.nn.relu(tf.matmul(prev_layer_flat, weights) + biases)
        print(prev_layer.get_shape())

    with tf.variable_scope('Softmax_Layer'):
        dim = np.prod(prev_layer.get_shape().as_list()[1:])
        prev_layer_flat = tf.reshape(prev_layer, [-1, dim])
        weights = getKernel('weights', [dim, num_classes])
        biases = _bias_variable('biases', [num_classes])
        softmax_linear = tf.add(tf.matmul(prev_layer_flat, weights), biases)
        print(softmax_linear.get_shape())

    return softmax_linear
