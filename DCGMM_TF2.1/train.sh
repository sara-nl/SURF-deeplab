#!/bin/bash
#SBATCH -N 1
#SBATCH -t 8:00:00
#SBATCH -p gpu_titanrtx

module purge
module use ~/environment-modules-lisa
module load 2020
#module load TensorFlow/2.1.0-foss-2019b-Python-3.7.4-CUDA-10.1.243
module load Python/3.7.4-GCCcore-8.3.0
module load cuDNN/7.6.5.32-CUDA-10.1.243


VIRTENV=tf2-2-0
VIRTENV_ROOT=~/virtualenvs

export PATH=/home/$USER/examode/lib_deps/bin:$PATH
export LD_LIBRARY_PATH=/home/$USER/examode/lib_deps/lib64:$LD_LIBRARY_PATH
export LD_LIBRARY_PATH=/home/$USER/examode/lib_deps/lib:$LD_LIBRARY_PATH
export CPATH=/home/$USER/examode/lib_deps/include:$CPATH

source $VIRTENV_ROOT/$VIRTENV/bin/activate

"""
To train for example:

python3 main.py \
--img_size 256 \
--batch_size 16 \
--epochs 5 \
--num_clusters 4 \
--dataset 17 \
--train_centers 1 \
--val_centers 1 \
--legacy_conversion

For evaluation:

python3 main.py \
--img_size 256 \
--template_path /nfs/managed_datasets/CAMELYON17/training/center_1/patches_positive_256 \
--images_path /nfs/managed_datasets/CAMELYON17/training/center_1/patches_positive_256 \
--load_path ~/examode/deeplab/DCGMM_TF2.1/logs/train_data/256-tr1-val1/checkpoint_4336 \
--legacy_conversion \
--eval_mode \
--save_path saved_images


"""
python3 main.py \
--img_size 256 \
--template_path /nfs/managed_datasets/CAMELYON17/training/center_1/patches_positive_256 \
--images_path /nfs/managed_datasets/CAMELYON17/training/center_1/patches_positive_256 \
--load_path ~/examode/deeplab/DCGMM_TF2.1/logs/train_data/256-tr1-val1/checkpoint_4336 \
--legacy_conversion \
--eval_mode \
--save_path saved_images
