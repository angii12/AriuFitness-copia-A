"""Orchestratore generico per creare un modello binario per qualsiasi esercizio.

Presuppone che i singoli video siano gia stati processati con main.py e
training_dataset.py e che rep_review.csv contenga le decisioni del medico.

Esegue:
1) train/validation multi-negative per REP intera
2) controllo leakage
3) augmentation SOLO train
4) training TwoBranchLSTM
"""
import argparse
import subprocess
import sys
from pathlib import Path


def run(command):
    print("\n$", " ".join(map(str, command)))
    subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser(description="Pipeline generica di training per un esercizio target.")
    parser.add_argument("--target", required=True)
    parser.add_argument("--train-positive", type=Path, required=True)
    parser.add_argument("--val-positive", type=Path, required=True)
    parser.add_argument("--train-negative", action="append", required=True, metavar="NOME=PERCORSO")
    parser.add_argument("--val-negative", action="append", required=True, metavar="NOME=PERCORSO")
    parser.add_argument("--negative-reps-per-exercise", type=int, default=5)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--dropout", type=float, default=0.3)
    parser.add_argument("--hidden1", type=int, default=64)
    parser.add_argument("--hidden2", type=int, default=32)
    parser.add_argument("--dense", type=int, default=64)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    target = args.target.strip().lower()
    if not target:
        raise ValueError("--target non può essere vuoto")

    src_dir = Path(__file__).resolve().parent
    output_root = args.output_root or Path(f"output/binary_{target}_multinegative")

    prepare_cmd = [
        sys.executable,
        str(src_dir / "prepare_multinegative_dataset.py"),
        "--target", target,
        "--train-positive", str(args.train_positive),
        "--val-positive", str(args.val_positive),
        "--negative-reps-per-exercise", str(args.negative_reps_per_exercise),
        "--output", str(output_root),
        "--seed", str(args.seed),
    ]
    for item in args.train_negative:
        prepare_cmd += ["--train-negative", item]
    for item in args.val_negative:
        prepare_cmd += ["--val-negative", item]
    run(prepare_cmd)

    run([
        sys.executable,
        str(src_dir / "check_dataset_integrity.py"),
        "--root", str(output_root),
    ])

    run([
        sys.executable,
        str(src_dir / "data_augmentation.py"),
        str(output_root / "train"),
        "--output", str(output_root / "train_augmented"),
    ])

    run([
        sys.executable,
        str(src_dir / "train_binary_lstm.py"),
        "--target", target,
        "--train", str(output_root / "train_augmented"),
        "--validation", str(output_root / "validation"),
        "--output", str(output_root / "model"),
        "--epochs", str(args.epochs),
        "--patience", str(args.patience),
        "--batch-size", str(args.batch_size),
        "--learning-rate", str(args.learning_rate),
        "--weight-decay", str(args.weight_decay),
        "--dropout", str(args.dropout),
        "--hidden1", str(args.hidden1),
        "--hidden2", str(args.hidden2),
        "--dense", str(args.dense),
        "--seed", str(args.seed),
    ])

    print("\nPipeline completata.")
    print("Modello:", output_root / "model" / "best_model.pth")
    print("Config:", output_root / "model" / "model_config.json")
    print("Normalizzazione:", output_root / "model" / "normalization_stats.npz")


if __name__ == "__main__":
    main()
