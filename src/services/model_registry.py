import os
import json
from pathlib import Path
import numpy as np
import torch

from rehab_pipeline.models_lstm import TwoBranchLSTM

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = PROJECT_ROOT / "models"

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


class LoadedModelEntry:
    """
    Rappresenta un modello caricato in memoria con le relative statistiche
    di normalizzazione e configurazione.
    """

    def __init__(self, model: torch.nn.Module, stats: dict | None, config: dict, model_type: str = "TwoBranchLSTM"):
        self.model = model
        self.stats = stats
        self.config = config
        self.model_type = model_type

    def normalize(self, keypoints: np.ndarray, angles: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Applica la z-score normalization basata sulle statistiche del dataset di addestramento.
        keypoints shape: (N, 36) o (1, S, 36)
        angles shape: (N, 8) o (1, S, 8)
        """
        if self.stats is None:
            return keypoints.astype(np.float32), angles.astype(np.float32)

        kp_mean = self.stats.get("keypoints_mean")
        kp_std = self.stats.get("keypoints_std")
        ang_mean = self.stats.get("angles_mean")
        ang_std = self.stats.get("angles_std")

        kp_norm = (keypoints - kp_mean) / (kp_std + 1e-8) if (kp_mean is not None and kp_std is not None) else keypoints
        ang_norm = (angles - ang_mean) / (ang_std + 1e-8) if (ang_mean is not None and ang_std is not None) else angles

        return kp_norm.astype(np.float32), ang_norm.astype(np.float32)

    def predict_confidence(self, keypoints: torch.Tensor, angles: torch.Tensor) -> float:
        """
        Esegue l'inferenza e restituisce la confidenza in percentuale (0 - 100%).
        """
        with torch.no_grad():
            logit = self.model(keypoints, angles)
            prob = torch.sigmoid(logit).item()
            return round(prob * 100.0, 2)


class ModelRegistryService:
    """
    Servizio per il registro dei modelli, la loro scoperta dinamica
    e la gestione della cache in memoria (inclusi Ex1 ed Ex6).
    """

    def __init__(self, models_dir: Path = MODELS_DIR):
        self.models_dir = models_dir
        self._cache: dict[str, LoadedModelEntry] = {}

    def get_registered_models(self) -> list[dict]:
        """
        Restituisce l'elenco di tutti i modelli attualmente presenti nel registro.
        """
        registered = []
        production_dir = self.models_dir / "production_models"
        if production_dir.exists():
            for ex_dir in sorted(production_dir.iterdir()):
                if ex_dir.is_dir():
                    config_file = ex_dir / "model_config.json"
                    metrics_file = ex_dir / "best_metrics.json"
                    config = json.loads(config_file.read_text(encoding="utf-8")) if config_file.exists() else {}
                    metrics = json.loads(metrics_file.read_text(encoding="utf-8")) if metrics_file.exists() else {}
                    registered.append({
                        "exercise_id": ex_dir.name,
                        "model_uri": str(ex_dir / "best_model.pth"),
                        "normalization_stats_uri": str(ex_dir / "normalization_stats.npz"),
                        "status": "active",
                        "metrics": metrics,
                        "config": config,
                        "version": 1
                    })
        return registered

    def load_model(self, exercise_id: str) -> LoadedModelEntry | None:
        """
        Carica in memoria il modello specificato da exercise_id (es. 'ex1', 'ex6').
        Usa la cache in-memory per evitare di rileggere il disco.
        """
        exercise_id = str(exercise_id).strip().lower()
        if exercise_id in self._cache:
            return self._cache[exercise_id]

        ex_dir = self.models_dir / "production_models" / exercise_id
        if not ex_dir.exists():
            ex_dir = self.models_dir / exercise_id

        weights_path = ex_dir / "best_model.pth"
        if not weights_path.exists():
            weights_path = ex_dir / f"LSTM_Binario_{exercise_id}.pth"

        if not weights_path.exists():
            print(f"⚠️ Modello non trovato per exercise_id: '{exercise_id}' in {ex_dir}")
            return None

        config_path = ex_dir / "model_config.json"
        config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {
            "keypoint_features": 36,
            "angle_features": 8,
            "hidden_size_1": 64,
            "hidden_size_2": 32,
            "dense_size": 64,
            "dropout": 0.3
        }

        stats_path = ex_dir / "normalization_stats.npz"
        stats = None
        if stats_path.exists():
            npz = np.load(stats_path)
            stats = {
                "keypoints_mean": npz["keypoints_mean"],
                "keypoints_std": npz["keypoints_std"],
                "angles_mean": npz["angles_mean"],
                "angles_std": npz["angles_std"]
            }

        model = TwoBranchLSTM(
            keypoint_input_size=config.get("keypoint_features", 36),
            angle_input_size=config.get("angle_features", 8),
            hidden_size_1=config.get("hidden_size_1", 64),
            hidden_size_2=config.get("hidden_size_2", 32),
            dense_size=config.get("dense_size", 64),
            dropout=config.get("dropout", 0.3)
        ).to(device)

        model.load_state_dict(torch.load(weights_path, map_location=device))
        model.eval()

        entry = LoadedModelEntry(model=model, stats=stats, config=config, model_type="TwoBranchLSTM")
        self._cache[exercise_id] = entry
        print(f"[OK] Modello '{exercise_id}' registrato e caricato con successo.")
        return entry

    def load_model_by_row(self, model_id: str, row: dict) -> LoadedModelEntry | None:
        """
        Carica in memoria il modello specificato dal record DB (exercise_models).
        Usa la cache in-memory per evitare di rileggere il disco.
        """
        model_id = str(model_id).strip()
        if model_id in self._cache:
            return self._cache[model_id]

        model_uri = row.get("model_uri")
        stats_uri = row.get("normalization_stats_uri")
        config = row.get("config") or {
            "keypoint_features": 36,
            "angle_features": 8,
            "hidden_size_1": 64,
            "hidden_size_2": 32,
            "dense_size": 64,
            "dropout": 0.3
        }

        if not model_uri:
            print(f"⚠️ model_uri mancante per model_id: '{model_id}'")
            return None

        # Resolve paths relative to PROJECT_ROOT
        weights_path = PROJECT_ROOT / model_uri
        
        if not weights_path.exists():
            print(f"⚠️ Modello non trovato per model_id '{model_id}' in {weights_path}")
            return None

        stats = None
        if stats_uri:
            stats_path = PROJECT_ROOT / stats_uri
            if stats_path.exists():
                npz = np.load(stats_path)
                stats = {
                    "keypoints_mean": npz["keypoints_mean"],
                    "keypoints_std": npz["keypoints_std"],
                    "angles_mean": npz["angles_mean"],
                    "angles_std": npz["angles_std"]
                }

        model = TwoBranchLSTM(
            keypoint_input_size=config.get("keypoint_features", 36),
            angle_input_size=config.get("angle_features", 8),
            hidden_size_1=config.get("hidden_size_1", 64),
            hidden_size_2=config.get("hidden_size_2", 32),
            dense_size=config.get("dense_size", 64),
            dropout=config.get("dropout", 0.3)
        ).to(device)

        model.load_state_dict(torch.load(weights_path, map_location=device))
        model.eval()

        entry = LoadedModelEntry(model=model, stats=stats, config=config, model_type="TwoBranchLSTM")
        self._cache[model_id] = entry
        print(f"[OK] Modello {model_id} caricato con successo da {weights_path}.")
        return entry

# Singleton service instance
model_registry = ModelRegistryService()
