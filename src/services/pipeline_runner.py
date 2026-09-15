import os
import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
REHAB_PIPELINE_DIR = SRC_DIR / "rehab_pipeline"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(REHAB_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(REHAB_PIPELINE_DIR))

# Import Rehab-AI modules mantenendo inalterati gli algoritmi scientifici
from rehab_pipeline.video_features import extract_pose_data_from_video
from rehab_pipeline.hybrid_segmenter import segment_repetitions
from rehab_pipeline.fixed_count_segmenter import segment_fixed_count
from rehab_pipeline.joint_selection import selected_joints_to_angles, normalize_selected_joints
from rehab_pipeline.main import _doctor_validate_segments
from rehab_pipeline.training_dataset import create_review_table, build_dataset
from rehab_pipeline.data_augmentation import augment_dataset
from rehab_pipeline.train_binary_lstm import set_seed, load_dataset as load_lstm_dataset, fit_normalizer, make_loader, metrics_from_logits
from rehab_pipeline.models_lstm import TwoBranchLSTM
from rehab_pipeline.config import MODEL_PATH
import torch
import torch.nn as nn

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


class RehabPipelineRunner:
    """
    Orchestratore / Wrapper per la pipeline scientifica Rehab-AI.
    Mantiene invariati gli algoritmi scientifici di segmentazione e fisiche MediaPipe.
    """

    @staticmethod
    def process_video(
        exercise_id: str,
        video_path: Path,
        output_dir: Path,
        signal_selection_mode: str = "auto",
        doctor_selected_joints: Optional[List[str]] = None,
        expected_reps: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Processa un video con la pipeline Rehab-AI:
        1. Estrazione pose & angoli (MediaPipe).
        2. Segmentazione REP (AUTO o FIXED).
        3. Validazione post-hoc del distretto selezionato se DOCTOR_GUIDED.
        4. Generazione tabella di review per il medico.
        """
        video_path = Path(video_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        signal_selection_mode = str(signal_selection_mode).lower().strip()
        doctor_selected_joints = normalize_selected_joints(doctor_selected_joints or [])

        if signal_selection_mode == "doctor_guided" and not doctor_selected_joints:
            raise ValueError("In modalita' doctor_guided devi selezionare almeno un'articolazione.")

        # 1. Estrazione pose ed angoli
        angles_df, pose_landmarks, fps, total_frames, detection_rate = extract_pose_data_from_video(
            video_path,
            MODEL_PATH
        )
        if angles_df.empty:
            raise RuntimeError(f"MediaPipe non ha rilevato pose nello stream del video: {video_path.name}")

        angles_df.to_csv(output_dir / "angles.csv", index=False)
        np.save(output_dir / "pose_landmarks.npy", pose_landmarks)

        # 2. Segmentazione (AUTO vs FIXED)
        if expected_reps is None:
            rep_mode = "auto"
            all_segments, used_segments, metadata, candidates = segment_repetitions(
                angles_df, fps, guide_angle=None, direction=None, guide_signals=None, expected_reps=None
            )
        else:
            rep_mode = "fixed"
            all_segments, used_segments, metadata, candidates = segment_fixed_count(
                angles_df, fps, expected_reps, guide_angle=None, direction=None, guide_signals=None
            )

        # 3. Validazione post-hoc medico (non modifica i confini start/end dell'AUTO)
        doctor_angles = selected_joints_to_angles(doctor_selected_joints)
        doctor_confirmed = 0
        doctor_unconfirmed = 0

        if signal_selection_mode == "doctor_guided":
            all_segments, doctor_confirmed, doctor_unconfirmed = _doctor_validate_segments(
                all_segments, angles_df, doctor_angles
            )
            used_segments, _, _ = _doctor_validate_segments(
                used_segments, angles_df, doctor_angles
            )

        # 4. Salvataggio csv & tabella di review
        pd.DataFrame(all_segments).to_csv(output_dir / "segments_all.csv", index=False)
        pd.DataFrame(used_segments).to_csv(output_dir / "segments_used.csv", index=False)

        review_df = create_review_table(used_segments)
        review_df.to_csv(output_dir / "rep_review.csv", index=False)

        metadata.update({
            "exercise_id": exercise_id,
            "video": str(video_path),
            "fps": fps,
            "total_frames": total_frames,
            "pose_detection_rate": detection_rate,
            "rep_mode": rep_mode,
            "signal_selection_mode": signal_selection_mode,
            "doctor_selected_joints": doctor_selected_joints,
            "doctor_validation_angles": doctor_angles,
            "doctor_confirmed_reps": doctor_confirmed if signal_selection_mode == "doctor_guided" else None,
            "doctor_unconfirmed_reps": doctor_unconfirmed if signal_selection_mode == "doctor_guided" else None,
        })
        (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        # Formatta lista REP per la risposta API REST con univocità per video
        rep_list = []
        video_id = video_path.stem
        for idx, seg in enumerate(used_segments, start=1):
            rep_list.append({
                "video_source": str(video_path.name),
                "rep_index": idx,
                "rep_uid": f"{video_id}__rep_{idx:03d}",
                "start_frame": int(seg["start_frame"]),
                "end_frame": int(seg["end_frame"]),
                "peak_frame": int(seg["peak_frame"]) if ("peak_frame" in seg and pd.notna(seg["peak_frame"])) else None,
                "start_sec": round(int(seg["start_frame"]) / fps, 2),
                "end_sec": round(int(seg["end_frame"]) / fps, 2),
                "doctor_validation": seg.get("doctor_validation", "not_confirmed"),
                "doctor_supporting_angles": seg.get("doctor_supporting_angles", ""),
            })

        return {
            "exercise_id": exercise_id,
            "video_path": str(video_path),
            "output_dir": str(output_dir),
            "total_frames": total_frames,
            "fps": fps,
            "detection_rate": detection_rate,
            "rep_mode": rep_mode,
            "signal_selection_mode": signal_selection_mode,
            "doctor_selected_joints": doctor_selected_joints,
            "reps": rep_list
        }

    @staticmethod
    def train_model_from_accepted_reps(
        exercise_id: str,
        run_dir: Path,
        accepted_rep_indices: List[int],
        output_model_dir: Path,
        epochs: int = 25,
        batch_size: int = 32,
        seed: int = 42
    ) -> Dict[str, Any]:
        """
        Addestramento Multi-Negative originale Rehab-AI (Target Exercise vs Multi-Negative):
        - Dataset Positivo (Label 1): Finestre estratte dalle sole REP accettate dal medico (singolo o più video) + Augmentation.
        - Dataset Negativo (Label 0): Esercizi negativi registrati + background non-rep.
        - Split per REP (rep_uid): Evita data-leakage mantenendo tutti i varianti/shifts di ciascuna REP nello stesso split.
        """
        run_dir = Path(run_dir)
        output_model_dir = Path(output_model_dir)
        output_model_dir.mkdir(parents=True, exist_ok=True)

        # Rileva se run_dir contiene sotto-cartelle per video multipli
        sub_run_dirs = [d for d in run_dir.iterdir() if d.is_dir() and (d / "rep_review.csv").exists()]
        if not sub_run_dirs and (run_dir / "rep_review.csv").exists():
            sub_run_dirs = [run_dir]

        if not sub_run_dirs:
            raise FileNotFoundError(f"Nessun rep_review.csv trovato in {run_dir} o nelle sue sottocartelle.")

        pos_kp_list, pos_ang_list, pos_meta_list = [], [], []
        accepted_set = set(accepted_rep_indices)

        for s_dir in sub_run_dirs:
            review_csv = s_dir / "rep_review.csv"
            review_df = pd.read_csv(review_csv)
            review_df["review_status"] = review_df["rep"].apply(
                lambda r: "accepted" if int(r) in accepted_set else "rejected"
            )
            review_df.to_csv(review_csv, index=False)

            dataset_dir = s_dir / "training_dataset"
            build_dataset(s_dir, output_dir=dataset_dir, accept_pending=False, exercise_label=1)

            augmented_dir = s_dir / "training_dataset_augmented"
            augment_dataset(dataset_dir, output_dir=augmented_dir)

            kp_p, ang_p, y_p = load_lstm_dataset(augmented_dir)
            p_meta = pd.read_csv(augmented_dir / "windows_metadata.csv")
            pos_kp_list.append(kp_p)
            pos_ang_list.append(ang_p)
            pos_meta_list.append(p_meta)

        kp_pos = np.concatenate(pos_kp_list, axis=0)
        ang_pos = np.concatenate(pos_ang_list, axis=0)
        y_pos = np.ones(len(kp_pos), dtype=np.float32)
        pos_meta = pd.concat(pos_meta_list, ignore_index=True)
        
        rep_uids = pos_meta["rep_uid"].astype(str).unique() if "rep_uid" in pos_meta.columns else np.arange(len(kp_pos))
        
        # Split a livello di rep_uid (80% train / 20% validation)
        set_seed(seed)
        n_reps = len(rep_uids)
        rep_indices = np.arange(n_reps)
        np.random.shuffle(rep_indices)

        val_rep_size = max(1, int(0.2 * n_reps))
        val_rep_uids = set(rep_uids[rep_indices[:val_rep_size]])

        if "rep_uid" in pos_meta.columns:
            val_mask = pos_meta["rep_uid"].astype(str).isin(val_rep_uids).to_numpy()
            train_mask = ~val_mask
        else:
            val_mask = np.zeros(len(kp_pos), dtype=bool)
            val_mask[:val_rep_size] = True
            train_mask = ~val_mask

        kp_train_pos, ang_train_pos, y_train_pos = kp_pos[train_mask], ang_pos[train_mask], y_pos[train_mask]
        kp_val_pos, ang_val_pos, y_val_pos = kp_pos[val_mask], ang_pos[val_mask], y_pos[val_mask]

        # 4. Generazione/Campionamento Campioni Negativi (Label 0: multi-negative)
        neg_kp_list, neg_ang_list = [], []
        prod_models_dir = PROJECT_ROOT / "models" / "production_models"
        
        if prod_models_dir.exists():
            for other_ex_dir in prod_models_dir.iterdir():
                if other_ex_dir.is_dir() and other_ex_dir.name != exercise_id:
                    neg_dataset = other_ex_dir / "training_dataset"
                    if not neg_dataset.exists():
                        neg_dataset = other_ex_dir / "train_augmented"
                    if neg_dataset.exists() and (neg_dataset / "keypoints.npy").exists():
                        try:
                            nkp = np.load(neg_dataset / "keypoints.npy").astype(np.float32)
                            nang = np.load(neg_dataset / "angles.npy").astype(np.float32)
                            neg_kp_list.append(nkp)
                            neg_ang_list.append(nang)
                        except Exception:
                            pass

        # Pool multi-negative dal dataset multi-esercizio Rehab-AI originale
        dataset_train_dir = PROJECT_ROOT / "dataset" / "train"
        if (dataset_train_dir / "keypoints_persona_train.npy").exists():
            try:
                ds_kp = np.load(dataset_train_dir / "keypoints_persona_train.npy").astype(np.float32)
                ds_ang = np.load(dataset_train_dir / "angles_train.npy").astype(np.float32)
                ds_labels = np.load(dataset_train_dir / "labels_train.npy")
                mask_neg = (ds_labels != exercise_id)
                if np.any(mask_neg):
                    neg_kp_list.append(ds_kp[mask_neg])
                    neg_ang_list.append(ds_ang[mask_neg])
            except Exception:
                pass

        if neg_kp_list:
            neg_kp_all = np.concatenate(neg_kp_list, axis=0)
            neg_ang_all = np.concatenate(neg_ang_list, axis=0)
            n_neg = len(neg_kp_all)
            
            # Bilancia numero negativi rispetto ai positivi
            n_pos_train = len(kp_train_pos)
            n_pos_val = len(kp_val_pos)
            
            rng = np.random.default_rng(seed)
            neg_train_idx = rng.choice(n_neg, size=min(n_neg, n_pos_train), replace=False if n_neg >= n_pos_train else True)
            neg_val_idx = rng.choice(n_neg, size=min(n_neg, n_pos_val), replace=False if n_neg >= n_pos_val else True)

            kp_train = np.concatenate([kp_train_pos, neg_kp_all[neg_train_idx]], axis=0)
            ang_train = np.concatenate([ang_train_pos, neg_ang_all[neg_train_idx]], axis=0)
            y_train = np.concatenate([y_train_pos, np.zeros(len(neg_train_idx), dtype=np.float32)], axis=0)

            kp_val = np.concatenate([kp_val_pos, neg_kp_all[neg_val_idx]], axis=0)
            ang_val = np.concatenate([ang_val_pos, neg_ang_all[neg_val_idx]], axis=0)
            y_val = np.concatenate([y_val_pos, np.zeros(len(neg_val_idx), dtype=np.float32)], axis=0)
        else:
            # Fallback se non ci sono ancora altri esercizi negativi registrati
            kp_train, ang_train, y_train = kp_train_pos, ang_train_pos, y_train_pos
            kp_val, ang_val, y_val = kp_val_pos, ang_val_pos, y_val_pos

        # Normalizer z-score calcolato solo sul train set
        kp_mean, kp_std, ang_mean, ang_std = fit_normalizer(kp_train, ang_train)
        
        np.savez(
            output_model_dir / "normalization_stats.npz",
            keypoints_mean=kp_mean,
            keypoints_std=kp_std,
            angles_mean=ang_mean,
            angles_std=ang_std
        )

        kp_train_norm = (kp_train - kp_mean) / (kp_std + 1e-8)
        ang_train_norm = (ang_train - ang_mean) / (ang_std + 1e-8)
        kp_val_norm = (kp_val - kp_mean) / (kp_std + 1e-8)
        ang_val_norm = (ang_val - ang_mean) / (ang_std + 1e-8)

        train_loader = make_loader(kp_train_norm, ang_train_norm, y_train, batch_size, shuffle=True)
        val_loader = make_loader(kp_val_norm, ang_val_norm, y_val, batch_size, shuffle=False)

        # 5. Training TwoBranchLSTM
        model = TwoBranchLSTM(
            keypoint_input_size=36,
            angle_input_size=8,
            hidden_size_1=64,
            hidden_size_2=32,
            dense_size=64,
            dropout=0.3
        ).to(device)

        criterion = nn.BCEWithLogitsLoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-4)

        best_val_f1 = -1.0
        best_val_loss = float('inf')
        best_epoch = 0
        best_metrics_summary = {}

        for epoch in range(1, epochs + 1):
            model.train()
            for x1, x2, targets in train_loader:
                x1, x2, targets = x1.to(device), x2.to(device), targets.to(device)
                optimizer.zero_grad()
                logits = model(x1, x2)
                loss = criterion(logits, targets)
                loss.backward()
                optimizer.step()

            model.eval()
            val_logits, val_targets, val_losses = [], [], []
            with torch.no_grad():
                for x1, x2, targets in val_loader:
                    x1, x2, targets = x1.to(device), x2.to(device), targets.to(device)
                    logits = model(x1, x2)
                    loss = criterion(logits, targets)
                    val_losses.append(loss.item())
                    val_logits.append(logits.cpu())
                    val_targets.append(targets.cpu())

            val_logits_tensor = torch.cat(val_logits)
            val_targets_tensor = torch.cat(val_targets)
            val_metrics = metrics_from_logits(val_logits_tensor, val_targets_tensor)
            mean_val_loss = float(np.mean(val_losses))

            if val_metrics["f1"] > best_val_f1 or (val_metrics["f1"] == best_val_f1 and mean_val_loss < best_val_loss):
                best_val_f1 = val_metrics["f1"]
                best_val_loss = mean_val_loss
                best_epoch = epoch
                torch.save(model.state_dict(), output_model_dir / "best_model.pth")
                best_metrics_summary = {
                    "epoch": best_epoch,
                    "accuracy": float(val_metrics["accuracy"]),
                    "precision": float(val_metrics["precision"]),
                    "recall": float(val_metrics["recall"]),
                    "f1": float(val_metrics["f1"]),
                    "loss": best_val_loss
                }
                (output_model_dir / "best_metrics.json").write_text(json.dumps(best_metrics_summary, indent=2), encoding="utf-8")

        model_config = {
            "model": "TwoBranchLSTM",
            "problem_type": "binary",
            "target_exercise": exercise_id,
            "sequence_length": 8,
            "keypoint_features": 36,
            "angle_features": 8,
            "hidden_size_1": 64,
            "hidden_size_2": 32,
            "dense_size": 64,
            "dropout": 0.3,
            "best_epoch": best_epoch,
            "best_validation_f1": best_val_f1,
            "best_validation_loss": best_val_loss,
            "accepted_reps_count": len(accepted_rep_indices)
        }
        (output_model_dir / "model_config.json").write_text(json.dumps(model_config, indent=2), encoding="utf-8")

        return {
            "exercise_id": exercise_id,
            "model_dir": str(output_model_dir),
            "model_path": str(output_model_dir / "best_model.pth"),
            "stats_path": str(output_model_dir / "normalization_stats.npz"),
            "metrics": best_metrics_summary,
            "config": model_config
        }
