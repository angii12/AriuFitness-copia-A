import argparse
import json
import random
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from models_lstm import TwoBranchLSTM


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_dataset(path):
    path = Path(path)

    kp = np.load(
        path / "keypoints.npy"
    ).astype(np.float32)

    ang = np.load(
        path / "angles.npy"
    ).astype(np.float32)

    y = np.load(
        path / "labels.npy"
    ).astype(np.float32)

    if not (
        len(kp) == len(ang) == len(y)
    ):
        raise ValueError(
            f"Dataset incoerente in {path}"
        )

    if (
        kp.ndim != 3
        or kp.shape[1:] != (8, 36)
    ):
        raise ValueError(
            f"Shape keypoints non valida: "
            f"{kp.shape}; attesa (N, 8, 36)"
        )

    if (
        ang.ndim != 3
        or ang.shape[1:] != (8, 8)
    ):
        raise ValueError(
            f"Shape angles non valida: "
            f"{ang.shape}; attesa (N, 8, 8)"
        )

    if (
        not np.isfinite(kp).all()
        or not np.isfinite(ang).all()
    ):
        raise ValueError(
            f"NaN/inf trovati in {path}"
        )

    unique = set(
        np.unique(y).tolist()
    )

    if not unique.issubset(
        {0.0, 1.0}
    ):
        raise ValueError(
            f"Label binarie attese 0/1, "
            f"trovate: {sorted(unique)}"
        )

    return kp, ang, y


def fit_normalizer(kp, ang):
    kp_mean = kp.mean(
        axis=(0, 1),
        keepdims=True,
    )

    kp_std = kp.std(
        axis=(0, 1),
        keepdims=True,
    )

    ang_mean = ang.mean(
        axis=(0, 1),
        keepdims=True,
    )

    ang_std = ang.std(
        axis=(0, 1),
        keepdims=True,
    )

    kp_std = np.where(
        kp_std < 1e-6,
        1.0,
        kp_std,
    )

    ang_std = np.where(
        ang_std < 1e-6,
        1.0,
        ang_std,
    )

    return (
        kp_mean,
        kp_std,
        ang_mean,
        ang_std,
    )


def apply_normalizer(
    kp,
    ang,
    stats,
):
    (
        kp_mean,
        kp_std,
        ang_mean,
        ang_std,
    ) = stats

    return (
        (kp - kp_mean) / kp_std,
        (ang - ang_mean) / ang_std,
    )


def make_loader(
    kp,
    ang,
    y,
    batch_size,
    shuffle,
):
    dataset = TensorDataset(
        torch.from_numpy(
            kp.astype(np.float32)
        ),
        torch.from_numpy(
            ang.astype(np.float32)
        ),
        torch.from_numpy(
            y.astype(np.float32)
        ),
    )

    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
    )


def metrics_from_logits(
    logits,
    targets,
    threshold=0.5,
):
    probs = torch.sigmoid(logits)

    pred = (
        probs >= threshold
    ).long()

    true = targets.long()

    tp = int(
        (
            (pred == 1)
            & (true == 1)
        ).sum().item()
    )

    tn = int(
        (
            (pred == 0)
            & (true == 0)
        ).sum().item()
    )

    fp = int(
        (
            (pred == 1)
            & (true == 0)
        ).sum().item()
    )

    fn = int(
        (
            (pred == 0)
            & (true == 1)
        ).sum().item()
    )

    total = max(
        1,
        tp + tn + fp + fn,
    )

    precision = (
        tp / max(1, tp + fp)
    )

    recall = (
        tp / max(1, tp + fn)
    )

    f1 = (
        2
        * precision
        * recall
        / max(
            1e-12,
            precision + recall,
        )
    )

    return {
        "accuracy":
            (tp + tn) / total,

        "precision":
            precision,

        "recall":
            recall,

        "f1":
            f1,

        "tp":
            tp,

        "tn":
            tn,

        "fp":
            fp,

        "fn":
            fn,
    }


def evaluate(
    model,
    loader,
    criterion,
    device,
):
    model.eval()

    losses = []
    all_logits = []
    all_targets = []

    with torch.no_grad():

        for kp, ang, y in loader:

            kp = kp.to(device)
            ang = ang.to(device)
            y = y.to(device)

            logits = model(
                kp,
                ang,
            )

            loss = criterion(
                logits,
                y,
            )

            losses.append(
                float(loss.item())
                * len(y)
            )

            all_logits.append(
                logits.cpu()
            )

            all_targets.append(
                y.cpu()
            )

    logits = torch.cat(
        all_logits
    )

    targets = torch.cat(
        all_targets
    )

    metrics = metrics_from_logits(
        logits,
        targets,
    )

    metrics["loss"] = (
        sum(losses)
        / max(1, len(targets))
    )

    return metrics


def is_better_model(
    current_metrics,
    best_f1,
    best_loss,
    tolerance=1e-6,
):
    """
    Criterio di selezione:

    1. preferisci F1 più alto;
    2. se F1 è praticamente uguale,
       preferisci validation loss più bassa.
    """

    current_f1 = (
        current_metrics["f1"]
    )

    current_loss = (
        current_metrics["loss"]
    )

    # F1 chiaramente migliore
    if (
        current_f1
        > best_f1 + tolerance
    ):
        return True

    # F1 equivalente:
    # scegli loss più bassa
    same_f1 = (
        abs(
            current_f1
            - best_f1
        )
        <= tolerance
    )

    if (
        same_f1
        and current_loss
        < best_loss - tolerance
    ):
        return True

    return False


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Training LSTM binario "
            "a due rami."
        )
    )

    parser.add_argument(
        "--target",
        required=True,
        help="Nome/ID dell'esercizio target, es. ex1 o squat.",
    )

    parser.add_argument(
        "--train",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--validation",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Default: output/binary_<target>_multinegative/model",
    )

    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
    )

    parser.add_argument(
        "--learning-rate",
        type=float,
        default=1e-3,
    )

    parser.add_argument(
        "--weight-decay",
        type=float,
        default=1e-4,
    )

    parser.add_argument(
        "--dropout",
        type=float,
        default=0.3,
    )

    parser.add_argument(
        "--hidden1",
        type=int,
        default=64,
    )

    parser.add_argument(
        "--hidden2",
        type=int,
        default=32,
    )

    parser.add_argument(
        "--dense",
        type=int,
        default=64,
    )

    parser.add_argument(
        "--patience",
        type=int,
        default=12,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    args = parser.parse_args()

    target = args.target.strip().lower()
    if not target:
        raise ValueError("--target non può essere vuoto")
    if args.output is None:
        args.output = Path(f"output/binary_{target}_multinegative/model")

    set_seed(
        args.seed
    )

    args.output.mkdir(
        parents=True,
        exist_ok=True,
    )

    train_kp, train_ang, train_y = (
        load_dataset(
            args.train
        )
    )

    val_kp, val_ang, val_y = (
        load_dataset(
            args.validation
        )
    )

    # ---------------------------------
    # Normalizzazione:
    # statistiche calcolate SOLO
    # sul training set.
    # ---------------------------------

    stats = fit_normalizer(
        train_kp,
        train_ang,
    )

    (
        train_kp,
        train_ang,
    ) = apply_normalizer(
        train_kp,
        train_ang,
        stats,
    )

    (
        val_kp,
        val_ang,
    ) = apply_normalizer(
        val_kp,
        val_ang,
        stats,
    )

    (
        kp_mean,
        kp_std,
        ang_mean,
        ang_std,
    ) = stats

    np.savez(
        args.output
        / "normalization_stats.npz",

        keypoints_mean=kp_mean,
        keypoints_std=kp_std,

        angles_mean=ang_mean,
        angles_std=ang_std,
    )

    train_loader = make_loader(
        train_kp,
        train_ang,
        train_y,
        args.batch_size,
        True,
    )

    val_loader = make_loader(
        val_kp,
        val_ang,
        val_y,
        args.batch_size,
        False,
    )

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    model = TwoBranchLSTM(
        hidden_size_1=args.hidden1,
        hidden_size_2=args.hidden2,
        dense_size=args.dense,
        dropout=args.dropout,
    ).to(device)

    criterion = (
        nn.BCEWithLogitsLoss()
    )

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )

    # ---------------------------------
    # Best model
    # ---------------------------------

    best_f1 = -1.0

    best_loss = float(
        "inf"
    )

    best_epoch = 0

    epochs_without_improvement = 0

    history = []

    print(
        f"Device: {device}"
    )

    print(
        f"Train: {len(train_y)} esempi | "
        f"Validation: {len(val_y)} esempi"
    )

    for epoch in range(
        1,
        args.epochs + 1,
    ):

        model.train()

        train_loss_sum = 0.0

        train_logits = []
        train_targets = []

        for kp, ang, y in train_loader:

            kp = kp.to(device)
            ang = ang.to(device)
            y = y.to(device)

            optimizer.zero_grad()

            logits = model(
                kp,
                ang,
            )

            loss = criterion(
                logits,
                y,
            )

            loss.backward()

            optimizer.step()

            train_loss_sum += (
                float(loss.item())
                * len(y)
            )

            train_logits.append(
                logits.detach().cpu()
            )

            train_targets.append(
                y.detach().cpu()
            )

        train_metrics = (
            metrics_from_logits(
                torch.cat(
                    train_logits
                ),
                torch.cat(
                    train_targets
                ),
            )
        )

        train_metrics["loss"] = (
            train_loss_sum
            / len(train_y)
        )

        val_metrics = evaluate(
            model,
            val_loader,
            criterion,
            device,
        )

        history.append(
            {
                "epoch": epoch,
                "train":
                    train_metrics,
                "validation":
                    val_metrics,
            }
        )

        print(
            f"Epoch {epoch:03d} | "
            f"train loss="
            f"{train_metrics['loss']:.4f} "
            f"f1="
            f"{train_metrics['f1']:.3f} | "
            f"val loss="
            f"{val_metrics['loss']:.4f} "
            f"acc="
            f"{val_metrics['accuracy']:.3f} "
            f"prec="
            f"{val_metrics['precision']:.3f} "
            f"rec="
            f"{val_metrics['recall']:.3f} "
            f"f1="
            f"{val_metrics['f1']:.3f}"
        )

        improved = is_better_model(
            val_metrics,
            best_f1,
            best_loss,
        )

        if improved:

            best_f1 = (
                val_metrics["f1"]
            )

            best_loss = (
                val_metrics["loss"]
            )

            best_epoch = epoch

            epochs_without_improvement = 0

            torch.save(
                model.state_dict(),
                args.output
                / "best_model.pth",
            )

            (
                args.output
                / "best_metrics.json"
            ).write_text(
                json.dumps(
                    {
                        "epoch":
                            epoch,

                        **val_metrics,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            print(
                "  -> nuovo best model "
                f"(F1={best_f1:.4f}, "
                f"loss={best_loss:.6f})"
            )

        else:

            epochs_without_improvement += 1

            if (
                epochs_without_improvement
                >= args.patience
            ):

                print(
                    "Early stopping alla "
                    f"epoch {epoch}; "
                    "migliore epoch: "
                    f"{best_epoch}"
                )

                break

    config = {
        "model":
            "TwoBranchLSTM",

        "problem_type":
            "binary",

        "target_exercise":
            target,

        "positive_label":
            1,

        "negative_label":
            0,

        "sequence_length":
            8,

        "keypoint_features":
            36,

        "angle_features":
            8,

        "hidden_size_1":
            args.hidden1,

        "hidden_size_2":
            args.hidden2,

        "dense_size":
            args.dense,

        "dropout":
            args.dropout,

        "loss":
            "BCEWithLogitsLoss",

        "optimizer":
            "Adam",

        "learning_rate":
            args.learning_rate,

        "weight_decay":
            args.weight_decay,

        "batch_size":
            args.batch_size,

        "seed":
            args.seed,

        "best_epoch":
            best_epoch,

        "best_validation_f1":
            best_f1,

        "best_validation_loss":
            best_loss,

        "best_model_selection":
            (
                "highest validation F1; "
                "if tied, lowest "
                "validation loss"
            ),

        "train_dir":
            str(args.train),

        "validation_dir":
            str(args.validation),

        "normalization":
            (
                "z-score fitted "
                "only on train"
            ),

        "decision_threshold":
            0.5,
    }

    (
        args.output
        / "model_config.json"
    ).write_text(
        json.dumps(
            config,
            indent=2,
        ),
        encoding="utf-8",
    )

    (
        args.output
        / "training_history.json"
    ).write_text(
        json.dumps(
            history,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "Modello migliore salvato in: "
        f"{args.output / 'best_model.pth'}"
    )

    print(
        "Migliore validation: "
        f"F1={best_f1:.3f}, "
        f"loss={best_loss:.6f} "
        f"(epoch {best_epoch})"
    )


if __name__ == "__main__":
    main()