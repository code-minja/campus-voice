# STT Fine-Tuning Workflow

This project serves STT with `faster-whisper`, which is an inference runtime. For
fine-tuning, train a Hugging Face Whisper model first, convert it to
CTranslate2, then point the API at the converted model directory.

## 1. Prepare the Dataset Manifest

Your current recordings live in `stt-training-data/` and use the intended
transcript as the filename. Generate a CSV manifest:

```bash
python scripts/prepare_stt_manifest.py
```

This writes:

```text
stt-training-data/metadata.csv
```

Columns:

```text
audio_path,transcript,split,condition
```

Review the generated `transcript` values before training. Fix names like `Etf`,
`30cq`, `tet650`, or abbreviations if the final assistant should prefer a
specific spelling.

## 2. Start With Baseline Evaluation

Before training, test the current Whisper model against the `test` rows. This
tells you whether fine-tuning is actually needed or whether a phrase correction
layer is enough.

For campus navigation, a post-processing layer is often more effective than
training when the dataset is tiny. For example, if Whisper hears "old RC" as
"old are see", map likely variants to canonical location names after
transcription.

## 3. Collect Enough Audio

The current dataset is useful, but small. It is enough for a smoke test and
baseline evaluation, not a strong fine-tune.

Practical targets:

```text
Minimum experiment: 30-60 minutes of clean labeled audio
Better first model: 2-5 hours
Production-quality accent/domain tuning: 10+ hours across many speakers
```

Collect multiple speakers, phones, rooms, distances, and noisy environments.
Keep a held-out test set that never appears in training.

## 4. Fine-Tune Whisper Outside `faster-whisper`

Install training-only dependencies in a separate environment:

```bash
pip install torch transformers datasets evaluate jiwer accelerate soundfile librosa
```

Recommended starting model:

```text
openai/whisper-small
```

Use `openai/whisper-base` if you need faster experiments on a weak machine. Use
`small` or `medium` if accuracy matters and you have GPU access.

High-level training loop:

```text
1. Load stt-training-data/metadata.csv with Hugging Face Datasets.
2. Decode audio and resample to 16 kHz.
3. Use WhisperProcessor to create input features and labels.
4. Fine-tune WhisperForConditionalGeneration.
5. Track WER/CER with jiwer on the held-out split.
6. Save the best checkpoint.
```

## 5. Convert the Fine-Tuned Model for This API

After training, convert the Hugging Face checkpoint to CTranslate2:

```bash
ct2-transformers-converter \
  --model /path/to/fine-tuned-whisper \
  --output_dir models/whisper-campus-ct2 \
  --copy_files tokenizer.json preprocessor_config.json \
  --quantization int8
```

Then set:

```bash
WHISPER_MODEL_SIZE=/absolute/path/to/models/whisper-campus-ct2
```

The existing `STTService` already accepts a model path through
`whisper_model_size`, so no service rewrite is needed.

## 6. What To Do Next In This Repo

Recommended order:

```text
1. Generate and review metadata.csv.
2. Add a baseline evaluation script.
3. Add a campus phrase correction layer for location names.
4. Collect more labeled recordings.
5. Fine-tune only after the baseline shows correction is not enough.
```

