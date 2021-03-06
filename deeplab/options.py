import tensorflow as tf
import argparse


class StoreDictKeyPair(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        self._nargs = nargs
        super(StoreDictKeyPair, self).__init__(option_strings, dest, nargs=nargs, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        my_dict = {}
        print(f"values: {values}")
        for kv in values:
            k, v = kv.split(":")
            my_dict[str(k)] = int(v)
        setattr(namespace, self.dest, my_dict)

         
def get_options():
    """ Argument parsing options"""

    parser = argparse.ArgumentParser(description='Multi - GPU TensorFlow model',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    # == Memory time consumption ==
    parser.add_argument('--image_size', type=int, default=1024, help='Image size to use')
    parser.add_argument('--batch_size', type=int, default=2, help='Batch size to use')
    parser.add_argument('--epochs', type=int, default=20, help='Amount of epochs')
    parser.add_argument('--steps_per_epoch', type=int, default=50000,
                        help='Number of steps for training. A single step is defined as one image. So a batch of 2 consists of 2 steps')

    parser.add_argument('--val_split', type=float, default=0.15, help='Part of images that is used as validation dataset, validating on all images')
    parser.add_argument('--verbosity', type=str, default='info', choices=['info','debug'],help='Verbosity of training')


    # == GPU and multi worker options ==
    parser.add_argument('--no_cuda', action='store_true', help='Use CUDA or not')
    parser.add_argument('--horovod', action='store_true', help='Distributed training via horovod', default=True)
    parser.add_argument('--fp16_allreduce', action='store_true',
                        help='Reduce to FP16 precision for gradient all reduce')
    parser.add_argument('--mixed_precision', action='store_true',
                        help='Enable "mixed_float16" policy for keras layers.')

    # Optimizer and learning rate scheduling options
    parser.add_argument('--optimizer', type=str, default='Adam', choices=['Adam', 'SGD'])
    parser.add_argument('--base_lr', type=float, default=0.001, help='Learning rate for constant learning')
    parser.add_argument('--nesterov', action='store_true', help='Use nesterov momentum for SGD')
    parser.add_argument('--momentum', type=float, default=0.9, help='Momentum term for SGD')
    parser.add_argument('--epsilon', type=float, default=1e-7, help='Epsilon for Adam')

    parser.add_argument('--lr_scheduler', type=str, default='constant', choices=['constant', 'cosine', 'cyclic'])
    parser.add_argument('--verbose', type=str, default='info', help='Verbosity of the Sampler', choices=['info', 'debug'])
    parser.add_argument('--warmup_learning_rate', type=float, default=0.00001, help='Staring point for the warmup phase'
                                                                                    'of the cosine scheduler')
    parser.add_argument('--step_size', type=int, default=5000, help='Step_size for the cyclic learning rate')
    parser.add_argument('--gamma', type=float, default=0.99998, help='Decay parameter for the cyclic learning rate')
    parser.add_argument('--min_lr', type=float, default=0.0, help='Minimum learning rate for the cyclic learning rate')
    parser.add_argument('--max_lr', type=float, default=0.001, help='Maximum learning rate for the cyclic learning rate')

    # == Dataset and path options ==
    parser.add_argument('--hard_mining', action='store_true', help='Use hard mining or not')
    parser.add_argument('--slide_path', type=str,
                        help='Folder of where the training data whole slide images are located', default=None)
    parser.add_argument('--label_path', type=str,
                        help='Folder of where the training data whole slide images labels are located', default=None)
    parser.add_argument('--valid_slide_path', type=str,
                        help='Folder of where the validation data whole slide images are located', default=None)
    parser.add_argument('--valid_label_path', type=str,
                        help='Folder of where the validation data whole slide images labels are located', default=None)
    parser.add_argument('--weights_path', type=str, help='Folder where the pre - trained weights is located',
                        default=None)
    parser.add_argument('--test_path', type=str,
                        help='Folder of where the training data whole slide images are located', default=None)
    parser.add_argument('--slide_format', type=str, help='In which format the whole slide images are saved.',
                        default='tif',choices=['tif','xml'])
    parser.add_argument('--label_format', type=str, help='In which format the labels are saved.', default='xml',choices=['tif','xml'])
    parser.add_argument('--evaluate', action='store_true',
                        help='Only evaluate slides present in valid_slide_{path,label}')
    parser.add_argument('--model_dir', type=str, help='Model dir for saved_model', default=None)

    # == Options for SURF Sampler ==
    parser.add_argument('--bb_downsample', type=int,
                        help='Level to use for the bounding box construction as downsampling level of whole slide image',
                        default=7)
    parser.add_argument('--batch_tumor_ratio', type=float, help='The ratio of the batch that contains tumor', default=1)


    # == Log options ==
    parser.add_argument('--log_dir', type=str, help='Folder of where the logs are saved', default=None)
    parser.add_argument('--log_every', type=int, default=2, help='Log every X steps during training')
    parser.add_argument('--validate_every', type=int, default=2048, help='Run the validation dataset every X steps')
    parser.add_argument('--debug', action='store_true', help='If running in debug mode, only uses 100 images')

    # == Redundant ==
    parser.add_argument('--pos_pixel_weight', type=int, default=1)
    parser.add_argument('--neg_pixel_weight', type=int, default=1)

    opts = parser.parse_args()

    opts.cuda = not opts.no_cuda
    opts.tf_version = f'{tf.__version__}'

    return opts
