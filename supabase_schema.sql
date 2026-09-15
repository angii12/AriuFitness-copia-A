-- =======================================================
-- SCHEMA SQL DEFINITIVO PER INTEGRAZIONE ARIUFITNESS + REHAB-AI
-- (FASE 3.4 HARDENING RIGIDO TRANSIZIONI + RPC SOLO PAZIENTE)
-- =======================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. TABELLA PROFILI (Aggiornamento non distruttivo + doctor_code)
CREATE TABLE IF NOT EXISTS public.profili (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    nome TEXT,
    cognome TEXT,
    ruolo TEXT NOT NULL DEFAULT 'paziente' CHECK (ruolo IN ('medico', 'paziente')),
    doctor_code TEXT UNIQUE,
    opzione_tutorial TEXT DEFAULT 'sovrapposizione',
    opzione_tts BOOLEAN DEFAULT true,
    tutorial_visti JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.profili ADD COLUMN IF NOT EXISTS ruolo TEXT DEFAULT 'paziente' CHECK (ruolo IN ('medico', 'paziente'));
ALTER TABLE public.profili ADD COLUMN IF NOT EXISTS doctor_code TEXT UNIQUE;
ALTER TABLE public.profili ADD COLUMN IF NOT EXISTS opzione_tutorial TEXT DEFAULT 'sovrapposizione';
ALTER TABLE public.profili ADD COLUMN IF NOT EXISTS opzione_tts BOOLEAN DEFAULT true;
ALTER TABLE public.profili ADD COLUMN IF NOT EXISTS tutorial_visti JSONB DEFAULT '[]'::jsonb;

-- GENERAZIONE AUTOMATICA DEL CODICE MEDICO (Es: DOC-A7K92Q)
CREATE OR REPLACE FUNCTION public.generate_doctor_code()
RETURNS TRIGGER AS $$
DECLARE
  new_code TEXT;
  code_exists BOOLEAN;
BEGIN
  IF NEW.ruolo = 'medico' AND (NEW.doctor_code IS NULL OR NEW.doctor_code = '') THEN
    LOOP
      new_code := 'DOC-' || UPPER(SUBSTRING(MD5(RANDOM()::TEXT || CLOCK_TIMESTAMP()::TEXT) FROM 1 FOR 6));
      SELECT EXISTS (SELECT 1 FROM public.profili WHERE doctor_code = new_code) INTO code_exists;
      EXIT WHEN NOT code_exists;
    END LOOP;
    NEW.doctor_code := new_code;
  ELSIF NEW.ruolo = 'paziente' THEN
    NEW.doctor_code := NULL;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

DROP TRIGGER IF EXISTS trg_generate_doctor_code ON public.profili;
CREATE TRIGGER trg_generate_doctor_code
  BEFORE INSERT OR UPDATE ON public.profili
  FOR EACH ROW
  EXECUTE FUNCTION public.generate_doctor_code();

-- BACKFILL MIGRAZIONE PER MEDICI ESISTENTI SENZA CODICE
DO $$
DECLARE
  rec RECORD;
  n_code TEXT;
  c_exists BOOLEAN;
BEGIN
  FOR rec IN SELECT id FROM public.profili WHERE ruolo = 'medico' AND (doctor_code IS NULL OR doctor_code = '') LOOP
    LOOP
      n_code := 'DOC-' || UPPER(SUBSTRING(MD5(RANDOM()::TEXT || CLOCK_TIMESTAMP()::TEXT) FROM 1 FOR 6));
      SELECT EXISTS (SELECT 1 FROM public.profili WHERE doctor_code = n_code) INTO c_exists;
      EXIT WHEN NOT c_exists;
    END LOOP;
    UPDATE public.profili SET doctor_code = n_code WHERE id = rec.id;
  END LOOP;
END $$;

-- 2. TABELLA ESERCIZI (Aggiornamento non distruttivo)
CREATE TABLE IF NOT EXISTS public.esercizi (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exercise_id TEXT UNIQUE,
    nome TEXT NOT NULL,
    descrizione TEXT,
    categoria TEXT,
    video_tutorial_url TEXT,
    creato_da UUID REFERENCES public.profili(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.esercizi ADD COLUMN IF NOT EXISTS exercise_id TEXT;
ALTER TABLE public.esercizi ADD COLUMN IF NOT EXISTS categoria TEXT;
ALTER TABLE public.esercizi ADD COLUMN IF NOT EXISTS video_tutorial_url TEXT;
ALTER TABLE public.esercizi ADD COLUMN IF NOT EXISTS creato_da UUID REFERENCES public.profili(id) ON DELETE SET NULL;

-- 3. TABELLA EXERCISE_PROFILES (Nuova entità)
CREATE TABLE IF NOT EXISTS public.exercise_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exercise_id TEXT REFERENCES public.esercizi(exercise_id) ON DELETE CASCADE UNIQUE NOT NULL,
    signal_selection_mode TEXT NOT NULL CHECK (signal_selection_mode IN ('auto', 'doctor_guided')),
    doctor_selected_joints JSONB DEFAULT '[]'::jsonb,
    guide_signals JSONB DEFAULT '[]'::jsonb,
    rep_mode TEXT DEFAULT 'auto' CHECK (rep_mode IN ('auto', 'fixed')),
    expected_reps INT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 4. TABELLA EXERCISE_MODELS (Nuova entità con vincolo di unicità exercise_id, version)
CREATE TABLE IF NOT EXISTS public.exercise_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exercise_id TEXT REFERENCES public.esercizi(exercise_id) ON DELETE CASCADE NOT NULL,
    model_uri TEXT NOT NULL,
    normalization_stats_uri TEXT,
    version INT NOT NULL DEFAULT 1,
    status TEXT NOT NULL CHECK (status IN ('draft', 'training', 'active', 'archived', 'failed')),
    metrics JSONB DEFAULT '{}'::jsonb,
    segmentation_version TEXT DEFAULT 'legacy_pre_v11',
    config JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT unique_exercise_model_version UNIQUE (exercise_id, version)
);

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'unique_exercise_model_version'
    ) THEN
        ALTER TABLE public.exercise_models ADD CONSTRAINT unique_exercise_model_version UNIQUE (exercise_id, version);
    END IF;
END $$;

-- 5. TABELLA DOCTOR_PATIENTS (Con Indice Parziale per Unico Medico Attivo/Pending per Paziente)
CREATE TABLE IF NOT EXISTS public.doctor_patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id UUID REFERENCES public.profili(id) ON DELETE CASCADE NOT NULL,
    patient_id UUID REFERENCES public.profili(id) ON DELETE CASCADE NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'rejected')),
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.doctor_patients ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'rejected'));

-- Rimuove vincolo rigido globale unico doctor_patient se presente, per consentire re-invio dopo 'rejected'
ALTER TABLE public.doctor_patients DROP CONSTRAINT IF EXISTS unique_doctor_patient;

-- INDICE UNICO PARZIALE: Garantisce che un paziente abbia al massimo UN solo collegamento 'pending' o 'active' alla volta
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_active_pending_patient
  ON public.doctor_patients (patient_id)
  WHERE status IN ('pending', 'active');

-- TRIGGER IMMUTABILITA DOCTOR_ID/PATIENT_ID E RIGIDO CONTROLLO TRANSIZIONI STATUS
CREATE OR REPLACE FUNCTION public.prevent_doctor_patient_id_change()
RETURNS TRIGGER AS $$
BEGIN
  -- 1. Immutabilità doctor_id e patient_id
  IF NEW.doctor_id IS DISTINCT FROM OLD.doctor_id OR NEW.patient_id IS DISTINCT FROM OLD.patient_id THEN
    IF current_setting('role', true) NOT IN ('service_role', 'postgres', 'supabase_admin') THEN
      RAISE EXCEPTION 'Non è consentito modificare doctor_id o patient_id di una relazione esistente.';
    END IF;
  END IF;

  -- 2. Controllo transizioni di stato consentite (UNICHE: pending -> active, pending -> rejected)
  IF NEW.status IS DISTINCT FROM OLD.status THEN
    IF current_setting('role', true) NOT IN ('service_role', 'postgres', 'supabase_admin') THEN
      IF NOT (OLD.status = 'pending' AND NEW.status IN ('active', 'rejected')) THEN
        RAISE EXCEPTION 'Transizione di stato non consentita: da % a %', OLD.status, NEW.status;
      END IF;
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

DROP TRIGGER IF EXISTS trg_prevent_doctor_patient_id_change ON public.doctor_patients;
CREATE TRIGGER trg_prevent_doctor_patient_id_change
  BEFORE UPDATE ON public.doctor_patients
  FOR EACH ROW
  EXECUTE FUNCTION public.prevent_doctor_patient_id_change();

-- HELPER FUNCTION SECURITY DEFINER PER VERIFICA RUOLO MEDICO (Bypassa RLS in modo sicuro)
CREATE OR REPLACE FUNCTION public.check_is_medico(p_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM public.profili
    WHERE id = p_id AND ruolo = 'medico'
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

REVOKE EXECUTE ON FUNCTION public.check_is_medico(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.check_is_medico(UUID) TO authenticated, service_role;

-- 6. TABELLA ASSIGNED_EXERCISES (Nuova entità)
CREATE TABLE IF NOT EXISTS public.assigned_exercises (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES public.profili(id) ON DELETE CASCADE NOT NULL,
    doctor_id UUID REFERENCES public.profili(id) ON DELETE CASCADE NOT NULL,
    exercise_id TEXT REFERENCES public.esercizi(exercise_id) ON DELETE CASCADE NOT NULL,
    model_id UUID REFERENCES public.exercise_models(id) ON DELETE RESTRICT NOT NULL,
    target_reps INT DEFAULT 5,
    notes TEXT,
    assigned_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- =======================================================
-- FASE 4A.1: TRIGGER VALIDAZIONE ASSIGNED_EXERCISES
-- Garantisce:
--   (1) Coerenza exercise_id <-> model_id (stesso esercizio)
--   (2) Modello con status = 'active'
--   (3) Medico autorizzato sull'esercizio (creato_da = doctor o NULL)
--   (4) Immutabilità di doctor_id / patient_id / exercise_id su UPDATE
-- =======================================================
CREATE OR REPLACE FUNCTION public.validate_assigned_exercise()
RETURNS TRIGGER AS $$
DECLARE
  v_model_exercise_id TEXT;
  v_model_status      TEXT;
  v_exercise_owner    UUID;
BEGIN
  -- ── (4) UPDATE: blocca modifica di campi immutabili ─────────────────────
  IF TG_OP = 'UPDATE' THEN
    IF NEW.doctor_id   IS DISTINCT FROM OLD.doctor_id   THEN
      RAISE EXCEPTION 'Non è consentito modificare doctor_id di un''assegnazione esistente.';
    END IF;
    IF NEW.patient_id  IS DISTINCT FROM OLD.patient_id  THEN
      RAISE EXCEPTION 'Non è consentito modificare patient_id di un''assegnazione esistente.';
    END IF;
    IF NEW.exercise_id IS DISTINCT FROM OLD.exercise_id THEN
      RAISE EXCEPTION 'Non è consentito modificare exercise_id di un''assegnazione esistente.';
    END IF;
    -- Aggiorna updated_at automaticamente
    NEW.updated_at := now();
  END IF;

  -- ── (1) Verifica coerenza exercise_id <-> model_id ──────────────────────
  SELECT em.exercise_id, em.status
  INTO   v_model_exercise_id, v_model_status
  FROM   public.exercise_models em
  WHERE  em.id = NEW.model_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'model_id % non trovato in exercise_models.', NEW.model_id;
  END IF;

  IF v_model_exercise_id IS DISTINCT FROM NEW.exercise_id THEN
    RAISE EXCEPTION
      'Incoerenza exercise_id/model_id: il modello appartiene all''esercizio "%" ma l''assegnazione usa "%" .',
      v_model_exercise_id, NEW.exercise_id;
  END IF;

  -- ── (2) Modello deve avere status = 'active' ─────────────────────────────
  IF v_model_status <> 'active' THEN
    RAISE EXCEPTION
      'Il modello selezionato ha status "%" . Solo modelli con status "active" possono essere assegnati.',
      v_model_status;
  END IF;

  -- ── (3) Medico deve essere proprietario/autorizzato sull'esercizio ────────
  --        (creato_da = doctor_id oppure creato_da IS NULL per esercizi di sistema)
  SELECT e.creato_da
  INTO   v_exercise_owner
  FROM   public.esercizi e
  WHERE  e.exercise_id = NEW.exercise_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'exercise_id "%" non trovato in esercizi.', NEW.exercise_id;
  END IF;

  IF v_exercise_owner IS NOT NULL AND v_exercise_owner IS DISTINCT FROM NEW.doctor_id THEN
    RAISE EXCEPTION
      'Il medico non è autorizzato ad assegnare l''esercizio "%": appartiene a un altro medico.',
      NEW.exercise_id;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

DROP TRIGGER IF EXISTS trg_validate_assigned_exercise ON public.assigned_exercises;
CREATE TRIGGER trg_validate_assigned_exercise
  BEFORE INSERT OR UPDATE ON public.assigned_exercises
  FOR EACH ROW
  EXECUTE FUNCTION public.validate_assigned_exercise();


-- 7. TABELLA RIPETIZIONI_GENERATE (Nuova entità per la fase di review REP)
CREATE TABLE IF NOT EXISTS public.ripetizioni_generate (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exercise_id TEXT REFERENCES public.esercizi(exercise_id) ON DELETE CASCADE NOT NULL,
    video_source TEXT,
    rep_index INT NOT NULL,
    start_frame INT NOT NULL,
    end_frame INT NOT NULL,
    peak_frame INT,
    doctor_validation TEXT DEFAULT 'not_confirmed',
    confermata_medico BOOLEAN DEFAULT false,
    accettata_medico BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 8. TABELLA REHAB_SESSIONS (Tracciamento sessioni riabilitative paziente)
CREATE TABLE IF NOT EXISTS public.rehab_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id UUID REFERENCES public.assigned_exercises(id) ON DELETE CASCADE NOT NULL,
    patient_id UUID REFERENCES public.profili(id) ON DELETE CASCADE NOT NULL,
    doctor_id UUID REFERENCES public.profili(id) ON DELETE CASCADE NOT NULL,
    exercise_id TEXT REFERENCES public.esercizi(exercise_id) ON DELETE CASCADE NOT NULL,
    reps_completed INT NOT NULL,
    target_reps INT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completed', 'interrupted')),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- =======================================================
-- RPC SECURE SEARCH FUNCTION FIND_DOCTOR_BY_CODE (SOLO PAZIENTI)
-- =======================================================

CREATE OR REPLACE FUNCTION public.find_doctor_by_code(p_code TEXT)
RETURNS TABLE (
  id UUID,
  nome TEXT,
  cognome TEXT,
  doctor_code TEXT
) AS $$
BEGIN
  -- 1. Controllo sicurezza: chiamante autenticato
  IF auth.role() <> 'authenticated' OR auth.uid() IS NULL THEN
    RAISE EXCEPTION 'Accesso negato. Autenticazione richiesta.';
  END IF;

  -- 2. Controllo sicurezza: il chiamante DEVE essere un PAZIENTE
  IF NOT EXISTS (
    SELECT 1 FROM public.profili p
    WHERE p.id = auth.uid() AND p.ruolo = 'paziente'
  ) THEN
    RAISE EXCEPTION 'Accesso negato. La ricerca del medico tramite codice è riservata ai pazienti.';
  END IF;

  RETURN QUERY
  SELECT p.id, p.nome, p.cognome, p.doctor_code
  FROM public.profili p
  WHERE UPPER(TRIM(p.doctor_code)) = UPPER(TRIM(p_code))
    AND p.ruolo = 'medico'
  LIMIT 1;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

REVOKE EXECUTE ON FUNCTION public.find_doctor_by_code(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.find_doctor_by_code(TEXT) TO authenticated, service_role;

-- =======================================================
-- SEED DATA PER EX1 ED EX6 CON ON CONFLICT (exercise_id, version)
-- =======================================================

INSERT INTO public.esercizi (exercise_id, nome, descrizione, categoria)
VALUES 
    ('ex1', 'Ex1', 'Esercizio Ex1', 'Riabilitazione'),
    ('ex6', 'Ex6', 'Esercizio Ex6', 'Riabilitazione')
ON CONFLICT (exercise_id) DO UPDATE 
SET nome = EXCLUDED.nome, descrizione = EXCLUDED.descrizione;

INSERT INTO public.exercise_profiles (exercise_id, signal_selection_mode, doctor_selected_joints, rep_mode)
VALUES 
    ('ex1', 'auto', '[]'::jsonb, 'auto'),
    ('ex6', 'auto', '[]'::jsonb, 'auto')
ON CONFLICT (exercise_id) DO UPDATE 
SET signal_selection_mode = EXCLUDED.signal_selection_mode, doctor_selected_joints = EXCLUDED.doctor_selected_joints;

INSERT INTO public.exercise_models (
    exercise_id, 
    model_uri, 
    normalization_stats_uri, 
    version, 
    status, 
    metrics, 
    segmentation_version,
    config
)
VALUES 
    (
        'ex1', 
        'models/production_models/ex1/best_model.pth', 
        'models/production_models/ex1/normalization_stats.npz', 
        1, 
        'active', 
        '{
            "validation": {
                "epoch": 1,
                "accuracy": 0.975,
                "precision": 0.9523809523809523,
                "recall": 1.0,
                "f1": 0.975609756097561,
                "loss": 0.08617304224859584
            },
            "test_window_level": {
                "accuracy": 1.0,
                "precision": 1.0,
                "recall": 1.0,
                "specificity": 1.0,
                "f1": 1.0
            },
            "test_rep_level": {
                "accuracy": 1.0,
                "precision": 1.0,
                "recall": 1.0,
                "specificity": 1.0,
                "f1": 1.0
            }
        }'::jsonb, 
        'legacy_pre_v11',
        '{
            "model": "TwoBranchLSTM", 
            "keypoint_features": 36, 
            "angle_features": 8, 
            "sequence_length": 8,
            "hidden_size_1": 64,
            "hidden_size_2": 32,
            "dense_size": 64,
            "dropout": 0.3
        }'::jsonb
    ),
    (
        'ex6', 
        'models/production_models/ex6/best_model.pth', 
        'models/production_models/ex6/normalization_stats.npz', 
        1, 
        'active', 
        '{
            "validation": {
                "epoch": 36,
                "accuracy": 0.975,
                "precision": 0.95,
                "recall": 1.0,
                "f1": 0.9743589743589743,
                "loss": 0.2242216109213504
            },
            "test_window_level": {
                "accuracy": 0.9583333333333334,
                "precision": 0.9230769230769231,
                "recall": 1.0,
                "specificity": 0.9166666666666666,
                "f1": 0.9600000000000001
            },
            "test_rep_level": {
                "accuracy": 0.9583333333333334,
                "precision": 0.9230769230769231,
                "recall": 1.0,
                "specificity": 0.9166666666666666,
                "f1": 0.9600000000000001
            }
        }'::jsonb, 
        'legacy_pre_v11',
        '{
            "model": "TwoBranchLSTM", 
            "keypoint_features": 36, 
            "angle_features": 8, 
            "sequence_length": 8,
            "hidden_size_1": 64,
            "hidden_size_2": 32,
            "dense_size": 64,
            "dropout": 0.3
        }'::jsonb
    )
ON CONFLICT (exercise_id, version) DO UPDATE 
SET 
    model_uri = EXCLUDED.model_uri,
    normalization_stats_uri = EXCLUDED.normalization_stats_uri,
    status = EXCLUDED.status,
    metrics = EXCLUDED.metrics,
    segmentation_version = EXCLUDED.segmentation_version,
    config = EXCLUDED.config;

-- =======================================================
-- FASE 3.4: RLS & POLICIES DEFINITIVE PER DOCTOR_PATIENTS
-- =======================================================

DROP POLICY IF EXISTS "Autenticati leggono esercizi" ON public.esercizi;
DROP POLICY IF EXISTS "Autenticati leggono exercise_profiles" ON public.exercise_profiles;
DROP POLICY IF EXISTS "Autenticati leggono exercise_models" ON public.exercise_models;
DROP POLICY IF EXISTS "Utente legge proprio profilo o medico" ON public.profili;
DROP POLICY IF EXISTS "Utente legge proprio profilo" ON public.profili;
DROP POLICY IF EXISTS "Utente gestisce proprio profilo" ON public.profili;
DROP POLICY IF EXISTS "Utente inserisce proprio profilo" ON public.profili;
DROP POLICY IF EXISTS "Utente aggiorna proprio profilo (senza ruolo)" ON public.profili;
DROP POLICY IF EXISTS "Utente aggiorna proprio profilo" ON public.profili;
DROP POLICY IF EXISTS "Lettura profili autorizzati" ON public.profili;

DROP POLICY IF EXISTS "Lettura esercizi autorizzati" ON public.esercizi;
DROP POLICY IF EXISTS "Medici gestiscono i propri esercizi" ON public.esercizi;

DROP POLICY IF EXISTS "Lettura exercise_models autorizzati" ON public.exercise_models;
DROP POLICY IF EXISTS "Medici gestiscono exercise_models" ON public.exercise_models;
DROP POLICY IF EXISTS "Medici gestiscono i propri exercise_models" ON public.exercise_models;

DROP POLICY IF EXISTS "Lettura exercise_profiles autorizzati" ON public.exercise_profiles;
DROP POLICY IF EXISTS "Medici gestiscono exercise_profiles" ON public.exercise_profiles;
DROP POLICY IF EXISTS "Medici gestiscono i propri exercise_profiles" ON public.exercise_profiles;

DROP POLICY IF EXISTS "Lettura doctor_patients" ON public.doctor_patients;
DROP POLICY IF EXISTS "Medici gestiscono doctor_patients" ON public.doctor_patients;
DROP POLICY IF EXISTS "Paziente inserisce richiesta collegamento" ON public.doctor_patients;
DROP POLICY IF EXISTS "Medico aggiorna stato richiesta" ON public.doctor_patients;

DROP POLICY IF EXISTS "Lettura assigned_exercises" ON public.assigned_exercises;
DROP POLICY IF EXISTS "Medici gestiscono assigned_exercises" ON public.assigned_exercises;
DROP POLICY IF EXISTS "Medico inserisce assigned_exercises" ON public.assigned_exercises;
DROP POLICY IF EXISTS "Medico aggiorna assigned_exercises" ON public.assigned_exercises;
DROP POLICY IF EXISTS "Medico revoca assigned_exercises" ON public.assigned_exercises;

DROP POLICY IF EXISTS "Medici gestiscono ripetizioni_generate" ON public.ripetizioni_generate;
DROP POLICY IF EXISTS "Medici gestiscono ripetizioni_generate dei propri esercizi" ON public.ripetizioni_generate;

DROP POLICY IF EXISTS "Lettura rehab_sessions" ON public.rehab_sessions;
DROP POLICY IF EXISTS "Paziente inserisce le proprie sessioni" ON public.rehab_sessions;

-- Drop trigger/funzione FASE 4A.1 (idempotente)
DROP TRIGGER IF EXISTS trg_validate_assigned_exercise ON public.assigned_exercises;
DROP FUNCTION IF EXISTS public.validate_assigned_exercise();


-- Abilita RLS su tutte le 8 tabelle
ALTER TABLE public.profili ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.esercizi ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.exercise_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.exercise_models ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.doctor_patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assigned_exercises ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ripetizioni_generate ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rehab_sessions ENABLE ROW LEVEL SECURITY;

-- FUNZIONE HELPER IS_MEDICO SICURA
CREATE OR REPLACE FUNCTION public.is_medico()
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM public.profili
    WHERE id = auth.uid() AND ruolo = 'medico'
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

REVOKE EXECUTE ON FUNCTION public.is_medico() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_medico() TO authenticated, service_role;

-- TRIGGER ANTI-PRIVILEGE ESCALATION SU PROFILI (Impedisce modifica 'ruolo')
CREATE OR REPLACE FUNCTION public.prevent_ruolo_change()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.ruolo IS DISTINCT FROM OLD.ruolo THEN
    IF current_setting('role', true) NOT IN ('service_role', 'postgres', 'supabase_admin') THEN
      RAISE EXCEPTION 'Non è consentito modificare autonomamente il proprio ruolo.';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

DROP TRIGGER IF EXISTS trg_prevent_ruolo_change ON public.profili;
CREATE TRIGGER trg_prevent_ruolo_change
  BEFORE UPDATE ON public.profili
  FOR EACH ROW
  EXECUTE FUNCTION public.prevent_ruolo_change();

-- 4. POLICIES DEFINITIVE PER `public.profili`
CREATE POLICY "Lettura profili autorizzati"
  ON public.profili FOR SELECT
  TO authenticated
  USING (
    auth.uid() = id
    OR
    (public.is_medico() AND EXISTS (
      SELECT 1 FROM public.doctor_patients dp
      WHERE dp.doctor_id = auth.uid()
        AND dp.patient_id = public.profili.id
    ))
  );

CREATE POLICY "Utente inserisce proprio profilo"
  ON public.profili FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = id);

CREATE POLICY "Utente aggiorna proprio profilo"
  ON public.profili FOR UPDATE
  TO authenticated
  USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);

-- 5. POLICIES DEFINITIVE PER `public.esercizi`
CREATE POLICY "Lettura esercizi autorizzati"
  ON public.esercizi FOR SELECT
  TO authenticated
  USING (
    (public.is_medico() AND (creato_da = auth.uid() OR creato_da IS NULL))
    OR
    (EXISTS (
      SELECT 1 FROM public.assigned_exercises ae
      WHERE ae.patient_id = auth.uid()
        AND ae.exercise_id = public.esercizi.exercise_id
    ))
  );

CREATE POLICY "Medici gestiscono i propri esercizi"
  ON public.esercizi FOR ALL
  TO authenticated
  USING (public.is_medico() AND (creato_da = auth.uid() OR creato_da IS NULL))
  WITH CHECK (public.is_medico() AND (creato_da = auth.uid() OR creato_da IS NULL));

-- 6. POLICIES DEFINITIVE PER `public.exercise_models`
CREATE POLICY "Lettura exercise_models autorizzati"
  ON public.exercise_models FOR SELECT
  TO authenticated
  USING (
    (public.is_medico() AND EXISTS (
      SELECT 1 FROM public.esercizi e
      WHERE e.exercise_id = public.exercise_models.exercise_id
        AND (e.creato_da = auth.uid() OR e.creato_da IS NULL)
    ))
    OR
    (EXISTS (
      SELECT 1 FROM public.assigned_exercises ae
      WHERE ae.patient_id = auth.uid()
        AND ae.model_id = public.exercise_models.id
    ))
  );

CREATE POLICY "Medici gestiscono i propri exercise_models"
  ON public.exercise_models FOR ALL
  TO authenticated
  USING (
    public.is_medico() AND EXISTS (
      SELECT 1 FROM public.esercizi e
      WHERE e.exercise_id = public.exercise_models.exercise_id
        AND (e.creato_da = auth.uid() OR e.creato_da IS NULL)
    )
  )
  WITH CHECK (
    public.is_medico() AND EXISTS (
      SELECT 1 FROM public.esercizi e
      WHERE e.exercise_id = public.exercise_models.exercise_id
        AND (e.creato_da = auth.uid() OR e.creato_da IS NULL)
    )
  );

-- 7. POLICIES DEFINITIVE PER `public.exercise_profiles`
CREATE POLICY "Lettura exercise_profiles autorizzati"
  ON public.exercise_profiles FOR SELECT
  TO authenticated
  USING (
    (public.is_medico() AND EXISTS (
      SELECT 1 FROM public.esercizi e
      WHERE e.exercise_id = public.exercise_profiles.exercise_id
        AND (e.creato_da = auth.uid() OR e.creato_da IS NULL)
    ))
    OR
    (EXISTS (
      SELECT 1 FROM public.assigned_exercises ae
      WHERE ae.patient_id = auth.uid()
        AND ae.exercise_id = public.exercise_profiles.exercise_id
    ))
  );

CREATE POLICY "Medici gestiscono i propri exercise_profiles"
  ON public.exercise_profiles FOR ALL
  TO authenticated
  USING (
    public.is_medico() AND EXISTS (
      SELECT 1 FROM public.esercizi e
      WHERE e.exercise_id = public.exercise_profiles.exercise_id
        AND (e.creato_da = auth.uid() OR e.creato_da IS NULL)
    )
  )
  WITH CHECK (
    public.is_medico() AND EXISTS (
      SELECT 1 FROM public.esercizi e
      WHERE e.exercise_id = public.exercise_profiles.exercise_id
        AND (e.creato_da = auth.uid() OR e.creato_da IS NULL)
    )
  );

-- 8. POLICIES DEFINITIVE E GRANULARI PER `public.doctor_patients`
CREATE POLICY "Lettura doctor_patients"
  ON public.doctor_patients FOR SELECT
  TO authenticated
  USING (doctor_id = auth.uid() OR patient_id = auth.uid());

CREATE POLICY "Paziente inserisce richiesta collegamento"
  ON public.doctor_patients FOR INSERT
  TO authenticated
  WITH CHECK (
    patient_id = auth.uid()
    AND doctor_id <> auth.uid()
    AND status = 'pending'
    AND public.check_is_medico(doctor_id)
  );

CREATE POLICY "Medico aggiorna stato richiesta"
  ON public.doctor_patients FOR UPDATE
  TO authenticated
  USING (doctor_id = auth.uid())
  WITH CHECK (
    doctor_id = auth.uid()
    AND status IN ('active', 'rejected')
  );

-- 9. POLICIES DEFINITIVE PER `public.assigned_exercises`
-- SELECT: medico vede le proprie assegnazioni; paziente vede solo le proprie
CREATE POLICY "Lettura assigned_exercises"
  ON public.assigned_exercises FOR SELECT
  TO authenticated
  USING (doctor_id = auth.uid() OR patient_id = auth.uid());

-- INSERT: solo medico, solo verso pazienti con collegamento ACTIVE
CREATE POLICY "Medico inserisce assigned_exercises"
  ON public.assigned_exercises FOR INSERT
  TO authenticated
  WITH CHECK (
    doctor_id = auth.uid()
    AND public.is_medico()
    AND EXISTS (
      SELECT 1 FROM public.doctor_patients dp
      WHERE dp.doctor_id = auth.uid()
        AND dp.patient_id = public.assigned_exercises.patient_id
        AND dp.status = 'active'
    )
  );

-- UPDATE: solo il medico proprietario
CREATE POLICY "Medico aggiorna assigned_exercises"
  ON public.assigned_exercises FOR UPDATE
  TO authenticated
  USING (doctor_id = auth.uid() AND public.is_medico())
  WITH CHECK (doctor_id = auth.uid() AND public.is_medico());

-- DELETE: il medico può revocare una propria assegnazione
CREATE POLICY "Medico revoca assigned_exercises"
  ON public.assigned_exercises FOR DELETE
  TO authenticated
  USING (doctor_id = auth.uid() AND public.is_medico());

-- 10. POLICIES DEFINITIVE PER `public.ripetizioni_generate`
CREATE POLICY "Medici gestiscono ripetizioni_generate dei propri esercizi"
  ON public.ripetizioni_generate FOR ALL
  TO authenticated
  USING (
    public.is_medico() AND EXISTS (
      SELECT 1 FROM public.esercizi e
      WHERE e.exercise_id = public.ripetizioni_generate.exercise_id
        AND (e.creato_da = auth.uid() OR e.creato_da IS NULL)
    )
  )
  WITH CHECK (
    public.is_medico() AND EXISTS (
      SELECT 1 FROM public.esercizi e
      WHERE e.exercise_id = public.ripetizioni_generate.exercise_id
        AND (e.creato_da = auth.uid() OR e.creato_da IS NULL)
    )
  );

-- 11. POLICIES DEFINITIVE PER `public.rehab_sessions`
-- SELECT: il medico vede le sessioni dei propri pazienti; il paziente vede le proprie
CREATE POLICY "Lettura rehab_sessions"
  ON public.rehab_sessions FOR SELECT
  TO authenticated
  USING (doctor_id = auth.uid() OR patient_id = auth.uid());

-- INSERT: il paziente inserisce le proprie sessioni riabilitative
CREATE POLICY "Paziente inserisce le proprie sessioni"
  ON public.rehab_sessions FOR INSERT
  TO authenticated
  WITH CHECK (patient_id = auth.uid());

-- =======================================================
-- FASE 5: TRIGGER AUTO-CREAZIONE PROFILO DA AUTH.USERS
-- =======================================================

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profili (id, nome, cognome, ruolo)
  VALUES (
    NEW.id,
    NEW.raw_user_meta_data->>'nome',
    NEW.raw_user_meta_data->>'cognome',
    COALESCE(NEW.raw_user_meta_data->>'ruolo', 'paziente')
  )
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
