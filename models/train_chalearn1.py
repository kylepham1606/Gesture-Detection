import tensorflow as tf
import sys
import os
import numpy as np
import c3D_main as conv3d1
import c3D2 as conv3d2
import c3D3 as conv3d3
import time
import pickle
import random
import argparse
from tensorflow.python.client import device_lib
from AdamWOptimizer import create_optimizer


def train_neural_network(x_inpuT,
                         y_inpuT,
                         data_path,
                         val_data_path,
                         save_loss_path,
                         save_model_path,
                         batch_size,
                         val_batch_size,
                         learning_rate,
                         weight_decay,
                         epochs,
                         which_model,
                         num_val_videos,
                         random_clips,
                         win_size,
                         ignore_factor):
    with tf.name_scope("cross_entropy"):

        prediction = 0
        if which_model == 1:
            prediction = conv3d1.inference(x_inpuT)
        elif which_model == 2:
            prediction = conv3d2.inference(x_inpuT)
        elif which_model == 3:
            prediction = conv3d3.inference(x_inpuT)

        cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=prediction, labels=y_inpuT))

    update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)
    with tf.control_dependencies(update_ops):

        # myAdamW = extend_with_decoupled_weight_decay(tf.train.AdamOptimizer)
        # # Create a MyAdamW object
        # optimizer = myAdamW(weight_decay=weight_decay, learning_rate=learning_rate).minimize(cost)
        # optimizer = tf.contrib.opt.AdamWOptimizer(weight_decay, learning_rate).minimize(cost)

        # optimizer = 0
        if weight_decay is not None:
            print("weight decay applied.")
            optimizer = create_optimizer(cost, learning_rate, weight_decay)
        else:
            optimizer = tf.train.AdamOptimizer(learning_rate).minimize(cost)

    with tf.name_scope("accuracy"):
        correct = tf.equal(tf.argmax(prediction, 1), tf.argmax(y_inpuT, 1))
        accuracy = tf.reduce_mean(tf.cast(correct, 'float'))

    saver = tf.train.Saver()

    gpu_options = tf.GPUOptions(allow_growth=True)
    with tf.Session(config=tf.ConfigProto(gpu_options=gpu_options)) as sess:

        print("session starts!")

        sess.run(tf.global_variables_initializer())

        start_time = time.time()
        epoch_loss_list = []
        val_loss_list = []

        pkl_files_list = os.listdir(data_path)
        val_pkl_files_list = os.listdir(val_data_path)

        for epoch in range(epochs):

            print("Epoch {} started!".format(epoch + 1))
            epoch_start_time = time.time()

            epoch_loss = 0
            train_acc = 0

            num_batch_completed = 0

            # mini batch
            batch_start_time = time.time()

            mini_batch_x = []
            mini_batch_y = []
            batch_filled = 0

            random.seed(7)
            print("Random seed fixed for training.")

            for pkl_file in pkl_files_list:

                with open(os.path.join(data_path, pkl_file), 'rb') as f:
                    frames_and_label = pickle.load(f)

                cut_frame_array = frames_and_label[0]
                label = frames_and_label[1]

                num_frames = cut_frame_array.shape[0]
                num_clips_per_video = random_clips
                window_size = win_size

                num_clip_index = 0

                if epoch + 1 == 1:
                    print(num_frames, int(win_size * ignore_factor))

                if num_frames <= int(win_size * ignore_factor):
                    continue

                while num_clip_index < num_clips_per_video:
                    start_frame = random.randint(0, num_frames - window_size)
                    end_frame = start_frame + window_size

                    mini_batch_x.append(cut_frame_array[start_frame: end_frame, :, :, :])
                    basic_line = [0] * num_classes
                    basic_line[int(label) - 1] = 1
                    basic_label = basic_line

                    mini_batch_y.append(basic_label)

                    batch_filled += 1
                    num_clip_index += 1

                if batch_filled == batch_size:
                    num_batch_completed += 1

                    mini_batch_x = np.array(mini_batch_x)
                    mini_batch_x = mini_batch_x / 255.0
                    mini_batch_y = np.array(mini_batch_y)

                    perm = np.random.permutation(batch_size)
                    mini_batch_x = mini_batch_x[perm]
                    mini_batch_y = mini_batch_y[perm]

                    _optimizer, _cost, _prediction, _accuracy = sess.run([optimizer, cost, prediction, accuracy],
                                                                         feed_dict={x_inpuT: mini_batch_x,
                                                                                    y_inpuT: mini_batch_y})
                    epoch_loss += _cost
                    train_acc += _accuracy
                    batch_end_time = time.time()

                    log1 = "\rEpoch: {}, " \
                           "batches completed: {}, " \
                           "time taken: {:.5f}, " \
                           "loss: {:.6f}, " \
                           "accuracy: {:.4f} \n". \
                        format(
                        epoch + 1,
                        num_batch_completed,
                        batch_end_time - batch_start_time,
                        epoch_loss / (batch_size * num_batch_completed),
                        _accuracy)

                    print(log1)
                    sys.stdout.flush()

                    batch_start_time = time.time()

                    mini_batch_x = []
                    mini_batch_y = []
                    batch_filled = 0

            # validation loss
            num_itr = int(num_val_videos / val_batch_size)
            val_loss = 0
            val_acc = 0

            val_batch_x = []
            val_batch_y = []

            val_batch_filled = 0
            val_num_batch_completed = 0

            random.seed(23)
            print("Random seed fixed for validation.")

            for val_pkl_file in val_pkl_files_list:

                with open(os.path.join(val_data_path, val_pkl_file), 'rb') as f:
                    frames_and_label = pickle.load(f)

                cut_frame_array = frames_and_label[0]
                label = frames_and_label[1]

                num_frames = cut_frame_array.shape[0]
                window_size = win_size

                if num_frames <= win_size:
                    continue

                start_frame = random.randint(0, num_frames - window_size)
                end_frame = start_frame + window_size
                val_batch_x.append(cut_frame_array[start_frame: end_frame, :, :, :])

                basic_line = [0] * num_classes
                basic_line[int(label) - 1] = 1
                basic_label = basic_line

                val_batch_y.append(basic_label)

                val_batch_filled += 1

                if val_batch_filled == val_batch_size:
                    val_num_batch_completed += 1

                    val_batch_x = np.array(val_batch_x)
                    val_batch_x = val_batch_x / 255.0
                    val_batch_y = np.array(val_batch_y)

                    val_cost, val_batch_accuracy = sess.run([cost, accuracy],
                                                            feed_dict={x_inpuT: val_batch_x, y_inpuT: val_batch_y})

                    val_acc += val_batch_accuracy
                    val_loss += val_cost

                    val_batch_x = []
                    val_batch_y = []

                    val_batch_filled = 0

                    if val_num_batch_completed == num_itr:
                        print("Required number of validation batches completed.")
                        break

            epoch_loss = epoch_loss / (batch_size * num_batch_completed)
            train_acc = train_acc / num_batch_completed

            val_loss /= (num_val_videos)
            val_acc = val_acc * batch_size / num_val_videos

            epoch_end_time = time.time()

            log3 = "Epoch {} done; " \
                   "Time Taken: {:.4f}s; " \
                   "Train_loss: {:.6f}; " \
                   "Val_loss: {:.6f}; " \
                   "Train_acc: {:.4f}; " \
                   "Val_acc: {:.4f}; " \
                   "Train batches: {}; " \
                   "Val batches: {};\n". \
                format(epoch + 1, epoch_end_time - epoch_start_time, epoch_loss, val_loss, train_acc, val_acc,
                       num_batch_completed, val_num_batch_completed)

            print(log3)

            if save_loss_path is not None:
                file1 = open(save_loss_path, "a")
                file1.write(log3)
                file1.close()

            epoch_loss_list.append(epoch_loss)
            val_loss_list.append(val_loss)

            if save_model_path is not None:
                saver.save(sess, save_model_path)

        end_time = time.time()
        print('Time elapse: ', str(end_time - start_time))
        print(epoch_loss_list)

        if save_loss_path is not None:
            file1 = open(save_loss_path, "a")
            file1.write("Train Loss List: {} \n".format(str(epoch_loss_list)))
            file1.write("Val Loss List: {} \n".format(str(val_loss_list)))
            file1.close()


if __name__ == '__main__':

    np.random.seed(0)
    parser = argparse.ArgumentParser()

    parser.add_argument('-bs', action='store', dest='batch_size', type=int)
    parser.add_argument('-vbs', action='store', dest='val_batch_size', type=int)
    parser.add_argument('-lr', action='store', dest='learning_rate', type=float)
    parser.add_argument('-wd', action='store', dest='weight_decay', type=float, const=None)
    parser.add_argument('-e', action='store', dest='epochs', type=int)
    parser.add_argument('-nvv', action='store', dest='num_val_videos', type=int)
    parser.add_argument('-rc', action='store', dest='random_clips', type=int)
    parser.add_argument('-ws', action='store', dest='win_size', type=int)
    parser.add_argument('-slp', action='store', dest='save_loss_path', const=None)
    parser.add_argument('-smp', action='store', dest='save_model_path', const=None)
    parser.add_argument('-mn', action='store', dest='model_num', type=int)
    parser.add_argument('-vd', action='store', dest='visible_devices')
    parser.add_argument('-nd', action='store', dest='num_device', type=int)
    parser.add_argument('-if', action='store', dest='ign_fact', type=float, const=None)

    results = parser.parse_args()

    arg_batch_size = results.batch_size
    arg_val_batch_size = results.val_batch_size
    arg_lr = results.learning_rate
    arg_wd = results.weight_decay
    arg_epochs = results.epochs
    arg_num_val_videos = results.num_val_videos
    arg_random_clips = results.random_clips
    arg_win_size = results.win_size
    arg_save_loss_path = results.save_loss_path
    arg_save_model_path = results.save_model_path
    arg_model_num = results.model_num
    arg_visible_devices = results.visible_devices
    arg_num_device = results.num_device
    arg_ign_fact = results.ign_fact

    data_path = "/home/axp798/axp798gallinahome/data/chalearn/train_64/"
    val_data_path = "/home/axp798/axp798gallinahome/data/chalearn/valid_64/"

    ar_save_loss_path = None
    if arg_save_loss_path is not None:
        ar_save_loss_path = "/home/axp798/axp798gallinahome/Gesture-Detection/models/loss_chalearn/{}".format(
            arg_save_loss_path)

    ar_save_model_path = None
    if arg_save_model_path is not None:
        path = '/home/axp798/axp798gallinahome/Gesture-Detection/models/{}/'.format(arg_save_model_path)
        if not os.path.exists(path):
            os.mkdir(path)
        ar_save_model_path = path + "model"

    if ar_save_loss_path is not None:
        file1 = open(ar_save_loss_path, "w")
        file1.write("Params: {} \n".format(results))
        file1.write("Losses: \n")
        file1.close()

    depth = 16
    height = 64
    width = 64
    num_classes = 249

    os.environ['CUDA_VISIBLE_DEVICES'] = "{}".format(arg_visible_devices)
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = "2"
    print(device_lib.list_local_devices())

    choose_device = "/device:GPU:{}".format(arg_num_device)

    with tf.device(choose_device):
        x_inpuT = tf.placeholder(tf.float32, shape=[arg_batch_size, depth, height, width, 3])
        y_inpuT = tf.placeholder(tf.float32, shape=[arg_batch_size, num_classes])

    train_neural_network(x_inpuT, y_inpuT, data_path, val_data_path,
                         save_loss_path=ar_save_loss_path,
                         save_model_path=ar_save_model_path,
                         batch_size=arg_batch_size,
                         learning_rate=arg_lr,
                         weight_decay=arg_wd,
                         epochs=arg_epochs,
                         val_batch_size=arg_val_batch_size,
                         which_model=arg_model_num,
                         num_val_videos=arg_num_val_videos,
                         random_clips=arg_random_clips,
                         win_size=arg_win_size,
                         ignore_factor=arg_ign_fact)
