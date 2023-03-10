#!/usr/bin/env bash
# Train domain adapter for 5 domains "fiction" "travel" "slate" "government" "telephone"
# divergences to choose from coral, cmd, mkmmd
# ABLATION: Use different Reduction Factors
TRAIN_PROP=1.0
DEV_PROP=1.0
EXP_DIR=${OUTPUT_DIR}
SEED=(1000)
BSZ=32
DIVERGENCE=mkmmd
EPOCHS=10
DATA_MODULE=sa
MAX_SEQ_LENGTH=128
REDUCTION_FACTOR=(2 4 8 16 32 64 128)
SKIP_LAYERS="None"
PADDING=max_length
LR=1e-05
GPU=0
PYTHON_FILE=${PROJECT_ROOT}/"domadapter/orchestration/ablations/train_domain_adapter.py"
DOMAINS=("camera_photo_baby")

for domain in "${DOMAINS[@]}"; do
    for red in "${REDUCTION_FACTOR[@]}"; do
        for seed in "${SEED[@]}"; do
            python ${PYTHON_FILE} \
                --dataset-cache-dir ${DATASET_CACHE_DIR} \
                --source-target "${domain}" \
                --pretrained-model-name "bert-base-uncased" \
                --seed ${seed} \
                --divergence ${DIVERGENCE} \
                --train-proportion ${TRAIN_PROP} \
                --data-module ${DATA_MODULE} \
                --reduction-factor ${red} \
                --skip-layers ${SKIP_LAYERS} \
                --dev-proportion ${DEV_PROP} \
                --gpu ${GPU} \
                --max-seq-length ${MAX_SEQ_LENGTH} \
                --padding ${PADDING} \
                --lr ${LR} \
                --log-freq 5 \
                --epochs ${EPOCHS} \
                --bsz ${BSZ} \
                --exp-dir ${EXP_DIR}
        done
    done
done
