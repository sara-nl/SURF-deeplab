# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Converts image data to TFRecords file format with Example protos.

The image data set is expected to reside in JPEG files located in the
following directory structure.

  data_dir/label_0/image0.jpeg
  data_dir/label_0/image1.jpg
  ...
  data_dir/label_1/weird-image.jpeg
  data_dir/label_1/my-image.jpeg
  ...

where the sub-directory is the unique label associated with these images.

This tf script converts the training and evaluation data into
a sharded data set consisting of TFRecord files

  train_directory/train-00000-of-01024
  train_directory/train-00001-of-01024
  ...
  train_directory/train-00127-of-01024

and

  validation_directory/validation-00000-of-00128
  validation_directory/validation-00001-of-00128
  ...
  validation_directory/validation-00127-of-00128

where we have selected 1024 and 128 shards for each data set. Each record
within the TFRecord file is a serialized Example proto. The Example proto
contains the following fields:

  image/encoded: string containing JPEG encoded image in RGB colorspace
  image/height: integer, image height in pixels
  image/width: integer, image width in pixels
  image/colorspace: string, specifying the colorspace, always 'RGB'
  image/channels: integer, specifying the number of channels, always 3
  image/format: string, specifying the format, always'JPEG'

  image/filename: string containing the basename of the image file
            e.g. 'n01440764_10026.JPEG' or 'ILSVRC2012_val_00000293.JPEG'
  image/class/label: integer specifying the index in a classification layer.
    The label ranges from [0, num_labels] where 0 is unused and left as
    the background class.
  image/class/text: string specifying the human-readable version of the label
    e.g. 'dog'

If you data set involves bounding boxes, please look at build_imagenet_data.py.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from datetime import datetime
import os
import random
import sys
import threading
import re
import numpy as np
import tensorflow as tf
import utils as utils
import pdb

tf.app.flags.DEFINE_string('output_directory', 'Processed/patch-based-classification_704_Normalized/tf-records/',
                           'Output data directory')

tf.app.flags.DEFINE_integer('train_shards', 150,  # N_TRAIN_SAMPLES / N_SAMPLES_PER_TRAIN_SHARD
                            'Number of shards in training TFRecord files.')
tf.app.flags.DEFINE_integer('validation_shards', 20,  # N_VALIDATION_SAMPLES / N_SAMPLES_PER_VALIDATION_SHARD
                            'Number of shards in validation TFRecord files.')

tf.app.flags.DEFINE_integer('num_train_threads', 6,
                            'Number of threads to preprocess the images.')

tf.app.flags.DEFINE_integer('num_val_threads', 5,
                            'Number of threads to preprocess the images.')

tf.app.flags.DEFINE_boolean('augmentation', False,
                            'Flag for data augmentation.')

tf.app.flags.DEFINE_integer('image_size', 704,
                            'Flag for image size.')

FLAGS = tf.app.flags.FLAGS


def _int64_feature(value):
    """Wrapper for inserting int64 features into Example proto."""
    if not isinstance(value, list):
        value = [value]
    return tf.train.Feature(int64_list=tf.train.Int64List(value=value))


def _bytes_feature(value):
    """Wrapper for inserting bytes features into Example proto."""
    return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))


def _convert_to_example(filename, image_buffer, label, height, width, mask_buffer):
    """Build an Example proto for an example.

    Args:
      filename: string, path to an image file, e.g., '/path/to/example.JPG'
      image_buffer: string, JPEG encoding of RGB image
      label: integer, identifier for the ground truth for the network
      height: integer, image height in pixels
      width: integer, image width in pixels
    Returns:
      Example proto
    """

    colorspace = 'RGB'
    channels = 3
    image_format = 'JPEG'

    example = tf.train.Example(features=tf.train.Features(feature={
        'image/height': _int64_feature(height),
        'image/width': _int64_feature(width),
        'image/colorspace': _bytes_feature(tf.compat.as_bytes(colorspace)),
        'image/channels': _int64_feature(channels),
        'image/class/label': _int64_feature(label),
        'image/format': _bytes_feature(tf.compat.as_bytes(image_format)),
        'image/filename': _bytes_feature(tf.compat.as_bytes(os.path.basename(filename))),
        'image/encoded': _bytes_feature(tf.compat.as_bytes(image_buffer)),
        'image/segmentation/class/encoded': _bytes_feature(tf.compat.as_bytes(mask_buffer))}))
    return example


class ImageCoder(object):
    """Helper class that provides tf image coding utilities."""

    def __init__(self):
        # Create a single Session to run all image coding calls.
        self._sess = tf.Session()

        # Initializes function that converts PNG to JPEG data.
        self._png_data = tf.placeholder(dtype=tf.string)
        image = tf.image.decode_png(self._png_data, channels=3)
        self._png_to_jpeg = tf.image.encode_jpeg(image, format='rgb', quality=100)

        # Initializes function that decodes RGB JPEG data.
        self._decode_jpeg_data = tf.placeholder(dtype=tf.string)
        self._decode_jpeg = tf.image.decode_jpeg(self._decode_jpeg_data, channels=3)

        self._decode_png_data = tf.placeholder(dtype=tf.string)
        self._decode_png = tf.image.decode_png(self._decode_png_data, channels=3)

    def png_to_jpeg(self, image_data):
        return self._sess.run(self._png_to_jpeg,
                              feed_dict={self._png_data: image_data})

    def decode_jpeg(self, image_data):
        image = self._sess.run(self._decode_jpeg,
                               feed_dict={self._decode_jpeg_data: image_data})
        assert len(image.shape) == 3
        assert image.shape[2] == 3
        return image

    def decode_png(self, image_data):
        image = self._sess.run(self._decode_png,
                               feed_dict={self._decode_png_data: image_data})
        assert len(image.shape) == 3
        assert image.shape[2] == 3
        return image


def _is_png(filename):
    """Determine if a file contains a PNG format image.

    Args:
      filename: string, path of the image file.

    Returns:
      boolean indicating if the image is a PNG.
    """
    return '.png' in filename


def _process_image(filename, coder):
    """Process a single image file.

    Args:
      filename: string, path to an image file e.g., '/path/to/example.JPG'.
      coder: instance of ImageCoder to provide tf image coding utils.
    Returns:
      image_buffer: string, JPEG encoding of RGB image.
      height: integer, image height in pixels.
      width: integer, image width in pixels.
    """
    # Read the image file.
    with tf.gfile.FastGFile(filename, 'rb') as f:
        image_data = f.read()

    # Convert any PNG to JPEG's for consistency.
    # if _is_png(filename):
    #     print('Converting PNG to JPEG for %s' % filename)
    #     image_data = coder.png_to_jpeg(image_data)

    
    image = coder.decode_png(image_data)
    # Check that image converted to RGB
    if len(image.shape) == 3:
        height = image.shape[0]
        width = image.shape[1]
        assert image.shape[2] == 3
    else:
        height = image.shape[0]
        width  = image.shape[1]

    return image_data, height, width


def _process_image_files_batch(coder, thread_index, ranges, name, file_names, labels, num_shards):
    """Processes and saves list of images as TFRecord in 1 thread.

    Args:
      coder: instance of ImageCoder to provide tf image coding utils.
      thread_index: integer:, unique batch to run index is within [0, len(ranges)).
      ranges: list of pairs of integers specifying ranges of each batches to
        analyze in parallel.
      name: string, unique identifier specifying the data set
      file_names: list of strings; each string is a path to an image file
      labels: list of integer; each integer identifies the ground truth
      num_shards: integer number of shards for this data set.
    """
    # Each thread produces N shards where N = int(num_shards / num_threads).
    # For instance, if num_shards = 128, and the num_threads = 2, then the first
    # thread would produce shards [0, 64).
    num_threads = len(ranges)
    assert not num_shards % num_threads
    num_shards_per_thread = int(num_shards / num_threads)

    shard_ranges = np.linspace(ranges[thread_index][0],
                               ranges[thread_index][1],
                               num_shards_per_thread + 1).astype(int)
    num_files_in_thread = ranges[thread_index][1] - ranges[thread_index][0]

    counter = 0
    for s in range(num_shards_per_thread):
        # Generate a sharded version of the file name, e.g. 'train-00002-of-00010'
        shard = thread_index * num_shards_per_thread + s
        output_filename = '%s-%.5d-of-%.5d' % (name, shard, num_shards)
        output_file = os.path.join(FLAGS.output_directory, output_filename)
        writer = tf.python_io.TFRecordWriter(output_file)

        shard_counter = 0
        files_in_shard = np.arange(shard_ranges[s], shard_ranges[s + 1], dtype=int)
        for i in files_in_shard:
            filename = file_names[i]
            label = labels[i]

            if filename.find('tumor') > -1 and filename.find('mask')== -1: # find('') outputs -1 if nothing found.
                mask_filename = filename.replace('tumor','mask_tumor')

            elif filename.find('tumor') == -1 and filename.find('mask') == -1:
                mask_filename = filename.replace('normal','mask_normal')
           
            filename = file_names[i]

            try:
                image_buffer, height, width = _process_image(filename, coder)
            except Exception as e:
                print(filename)
                print(e,"but skipping")

                continue

            try:
                mask_buffer, mask_height, mask_width = _process_image(mask_filename, coder)
                example = _convert_to_example(filename, image_buffer, label, height, width, mask_buffer)
                writer.write(example.SerializeToString())
                shard_counter += 1
                counter += 1

                if not counter % 1000:
                    print('%s [thread %d]: Processed %d of %d images in thread batch.' %
                          (datetime.now(), thread_index, counter, num_files_in_thread))
                sys.stdout.flush()

            except Exception as e:
                print(mask_filename)
                print(e," but skipping...")
                continue



        writer.close()
        print('%s [thread %d]: Wrote %d images to %s' %
              (datetime.now(), thread_index, shard_counter, output_file))
        sys.stdout.flush()
        shard_counter = 0
    print('%s [thread %d]: Wrote %d images to %d shards.' %
          (datetime.now(), thread_index, counter, num_files_in_thread))
    sys.stdout.flush()


def _process_image_files(name, file_names, labels, num_shards, num_threads):
    """Process and save list of images as TFRecord of Example protos.

    Args:
      name: string, unique identifier specifying the data set
      filenames: list of strings; each string is a path to an image file
      texts: list of strings; each string is human readable, e.g. 'dog'
      labels: list of integer; each integer identifies the ground truth
      num_shards: integer number of shards for this data set.
    """
    assert len(file_names) == len(labels)

    # Break all images into batches with a [ranges[i][0], ranges[i][1]].
    spacing = np.linspace(0, len(file_names), num_threads + 1).astype(np.int)
    ranges = []
    for i in range(len(spacing) - 1):
        ranges.append([spacing[i], spacing[i + 1]])
    # Launch a thread for each batch.
    print('Launching %d threads for spacings: %s' % (num_threads, ranges))
    sys.stdout.flush()

    # Create a mechanism for monitoring when all threads are finished.
    coord = tf.train.Coordinator()

    # Create a generic tf-based utility for converting all image codings.
    coder = ImageCoder()


    threads = []
    for thread_index in range(len(ranges)):
        args = (coder, thread_index, ranges, name, file_names, labels, num_shards)
        t = threading.Thread(target=_process_image_files_batch, args=args)
        t.start()
        threads.append(t)

    # Wait for all the threads to terminate.
    coord.join(threads)
    print('%s: Finished writing all %d images in data set.' %
          (datetime.now(), len(file_names)))
    sys.stdout.flush()


def _find_image_files(data_dir, image_size):
    """Build a list of all images files and labels in the data set.

    Args:
      data_dir: string, path to the root directory of images.

        Assumes that the image data set resides in JPEG files located in
        the following directory structure.

          data_dir/dog/another-image.JPEG
          data_dir/dog/my-image.jpg

        where 'dog' is the label associated with these images.

        The list of valid labels are held in this file. Assumes that the file
        contains entries as such:
          dog
          cat
          flower
        where each line corresponds to a label. We map each label contained in
        the file to an integer starting with the integer 0 corresponding to the
        label contained in the first line.

    Returns:
      filenames: list of strings; each string is a path to an image file.
      texts: list of strings; each string is the class, e.g. 'dog'
      labels: list of integer; each integer identifies the ground truth.
    """
    print('Determining list of input files and labels from %s.' % data_dir)
    unique_labels = ['label-0','label-1']

    labels = []
    file_names = []

    # Leave label index 0 empty as a background class.
    label_index = 0

    # Maybe you dont want to write all the images to tf-records
    # max_images = 100000

    # Construct the list of JPEG files and labels.
    for label in unique_labels:
        # for x in range(max_images):
            jpeg_file_path = '%s/%s/*%s*' % (data_dir, label, image_size) #(data_dir, label, x)
            matching_files = tf.gfile.Glob(jpeg_file_path)
            matching_files = [x for x in matching_files if 'mask' not in x]
            matching_files = [x for x in matching_files if os.path.getsize(x) > 750000]
            # matching_files = matching_files[:max_images]
            labels.extend([label_index] * len(matching_files))
            file_names.extend(matching_files)




            print('Finished finding files in %d of %d classes.' % (label_index, len(labels)))
            label_index += 1

    # Shuffle the ordering of all image files in order to guarantee
    # random ordering of the images with respect to label in the
    # saved TFRecord files. Make the randomization repeatable.
    shuffled_index = list(range(len(file_names)))
    random.seed(12345)
    random.shuffle(shuffled_index)

    file_names = [file_names[i] for i in shuffled_index]
    labels = [labels[i] for i in shuffled_index]

    print('Found %d PNG files across %d labels inside %s.' %
          (len(file_names), len(unique_labels), data_dir))
    return file_names, labels


def _process_dataset(name, directory, num_shards, num_threads, image_size):
    """Process a complete data set and save it as a TFRecord.

    Args:
      name: string, unique identifier specifying the data set.
      directory: string, root path to the data set.
      num_shards: integer number of shards for this data set.
    """
    file_names, labels = _find_image_files(directory, image_size)
    _process_image_files(name, file_names, labels, num_shards, num_threads)


def main(unused_argv):
    assert not FLAGS.train_shards % FLAGS.num_train_threads, (
        'Please make the num_threads commensurate with FLAGS.train_shards')
    assert not FLAGS.validation_shards % FLAGS.num_val_threads, (
        'Please make the num_threads commensurate with '
        'FLAGS.validation_shards')
    print('Saving results to %s' % FLAGS.output_directory)

    # Run it!

    _process_dataset('validation', 'Processed/patch-based-classification_704_Normalized/raw-data/validation',
                      FLAGS.validation_shards, FLAGS.num_val_threads, FLAGS.image_size)
    _process_dataset('train','Processed/patch-based-classification_704_Normalized/raw-data/train', FLAGS.train_shards, FLAGS.num_train_threads, FLAGS.image_size)


if __name__ == '__main__':
    tf.app.run()
