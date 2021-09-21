import click
import pathlib
import gc
import os
from domadapter.datamodules.mnli_dm import DataModuleSourceTarget
from domadapter.models.domain_task_adapter import DomainTaskAdaptor
from pytorch_lightning import Trainer
from pytorch_lightning.loggers import WandbLogger
from pytorch_lightning.callbacks import ModelCheckpoint, EarlyStopping
from pytorch_lightning import seed_everything
import json
from domadapter.console import console
from rich.prompt import Confirm


@click.command()
@click.option("--dataset-cache-dir", type=str, help="Cache directory for dataset.")
@click.option(
    "--source-target", type=str, help="Source and target domain in source_target format"
)
@click.option("--pretrained-model-name", type=str, help="PLM to be used from HF")
@click.option(
    "--padding", type=str, help="Add padding while tokenizing upto max length"
)
@click.option("--max-seq-length", type=str, help="seq length for tokenizer")
@click.option("--num-classes", type=int, help="Number of classes for task adapter classification head")
@click.option("--bsz", type=int, help="batch size")
@click.option("--train-proportion", type=float, help="Train on small proportion")
@click.option("--dev-proportion", type=float, help="Validate on small proportion")
@click.option("--test-proportion", type=float, help="Test on small proportion")
@click.option("--exp-dir", type=str, help="Experiment directory to store artefacts")
@click.option("--seed", type=str, help="Seed for reproducibility")
@click.option("--lr", type=float, help="Learning rate for the entire model")
@click.option("--epochs", type=int, help="Number of epochs to run the training")
@click.option("--gpu", type=int, default=None, help="GPU to run the program on")
@click.option("--log-freq", type=int, help="Log wandb after how many steps")
def train_domain_adapter(
    bsz,
    dataset_cache_dir,
    pretrained_model_name,
    train_proportion,
    dev_proportion,
    test_proportion,
    num_classes,
    max_seq_length,
    padding,
    source_target,
    exp_dir,
    seed,
    log_freq,
    lr,
    epochs,
    gpu,
):
    dataset_cache_dir = pathlib.Path(dataset_cache_dir)
    exp_dir = pathlib.Path(exp_dir)
    exp_dir = exp_dir.joinpath(source_target)

    # Ask to delete if experiment exists
    if not exp_dir.is_dir():
        print(f"Directory doesn't exist for {exp_dir}. Halting the pipeline...")
        exit(0)

    seed_everything(seed)

    hyperparams = {
        "bsz": bsz,
        "train_proportion": train_proportion,
        "dev_proportion": dev_proportion,
        "test_proportion": test_proportion,
        "source_target": source_target,
        "num_classes": int(num_classes),
        "dataset_cache_dir": str(dataset_cache_dir),
        "exp_dir": str(exp_dir),
        "seed": seed,
        "learning_rate": lr,
        "epochs": int(epochs),
        "gpu": gpu,
        "pretrained_model_name": str(pretrained_model_name),
        "max_seq_length": int(max_seq_length),
        "padding": str(padding),
    }

    ###########################################################################
    # Setup the dataset
    ###########################################################################
    dm = DataModuleSourceTarget(hyperparams)
    dm.prepare_data()

    model = DomainTaskAdaptor(hyperparams)

    ###########################################################################
    # SETUP THE LOGGERS and Checkpointers
    ###########################################################################
    logger = WandbLogger(
        save_dir=str(exp_dir),
        project=f"MNLI_{pretrained_model_name}",
        job_type="domain task adapter",
        group=source_target,
    )

    logger.watch(model, log="gradients", log_freq=log_freq)

    checkpoints_dir = exp_dir.joinpath("task_adapter")
    checkpoint_callback = ModelCheckpoint(
        dirpath=str(checkpoints_dir),
        save_top_k=1,
        mode="min",
        monitor="source_val/loss",
    )
    early_stop_callback = EarlyStopping(
        monitor="source_val/loss", patience=2, verbose=False, mode="min"
    )

    callbacks = [checkpoint_callback, early_stop_callback]

    trainer = Trainer(
        limit_train_batches=train_proportion,
        limit_val_batches=dev_proportion,
        limit_test_batches=test_proportion,
        callbacks=callbacks,
        terminate_on_nan=True,
        log_every_n_steps=log_freq,
        gpus=str(gpu),
        max_epochs=epochs,
        logger=logger,
    )

    dm.setup("fit")
    train_loader = dm.train_dataloader()
    val_loader = dm.val_dataloader()
    trainer.fit(model, train_loader, val_loader)

    dm.setup("test")
    test_loader = dm.test_dataloader()
    trainer.test(model, test_loader)

    best_ckpt_path = checkpoint_callback.best_model_path
    model = DomainTaskAdaptor.load_from_checkpoint(best_ckpt_path)

    model.save_adapter(
        str(checkpoints_dir), f"task_adapter_{source_target}"
    )  # save adapter after loading model
    os.remove(best_ckpt_path)  # remove saved model

    hparams_file = exp_dir.joinpath("hparams_task_adapter.json")

    with open(hparams_file, "w") as fp:
        json.dump(hyperparams, fp)

    del model
    gc.collect()


if __name__ == "__main__":
    train_domain_adapter()