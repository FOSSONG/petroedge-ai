# PetroEdge interface and evidence update 046

## Implemented
- Well Logs: eleven on-demand crossplots. Added sonic-density, sonic-neutron, gamma-sonic, sonic-resistivity, caliper-density and caliper-neutron.
- Interpretations use the currently selected dataset, depth filter and valid pairs. Statistics include medians, ranges and correlation (log coordinates for log axes). Orange open circles identify samples meeting the displayed interest rule. Counts use all valid pairs; rendering is bounded to 5,000 pairs plus at most 100 highlighted samples.
- Low-GR/high-RT interest uses within-interval quartiles. Other plots circle 1.5-IQR outliers. These are review aids, not confirmed lithology, continuous pay zones or fluid classification.
- Saved analyses render readable fields and expandable source/method details instead of raw JSON. Numeric unmapped lithology classes are labelled explicitly. PDF and Excel exports replace JSON/HTML defaults.
- CCUS encoding repaired. Prominent investor wording removed; model validation remains under Evaluation details.
- Agents accept user questions, route team questions by specialty, cite uploaded measurements/PDFs, and can reference an authorized saved analysis. Unsupported property requests are distinguished from measured summaries. PDF answers are cited once.
- These agents use deterministic evidence lookup and document retrieval, not a newly fine-tuned language model.

## Validation
Production frontend build passed. Seven focused frontend checks passed, including readable results, PDF/Excel buttons, on-demand plots, interpretation rules, stale-response handling and replay.
Backend local multi-user acceptance suite: 49 passed, covering upload/mapping/saved reports, isolation, revoked access, owner pause, question routing and backup restore.
PDF/Excel creation, actual parsing and cross-owner download rejection passed; results are recorded in acceptance-046.xml. One additional local-owner recovery test passed. Password recovery requires private user input and has not changed the real account.
These are local automated checks, not public HTTPS or independent customer acceptance.

## Storage and cloud status
Selected project: guilianno-local. Project is active, billing is enabled, Cloud Run API is disabled. No cloud resources were created or paid services enabled.
The application still has separate SQLite stores and local file references. Durable Cloud Run application state is NOT yet implemented. Changing DATABASE_URL or mounting a bucket is insufficient.
Added tested offline state-archive tooling with file hashes, SQLite integrity checks, traversal rejection, non-overwriting restore and generation-precondition GCS uploads. This is backup tooling, not a live distributed database. GCS upload was tested with a client double only; no actual bucket upload occurred.
Run from backend: python -m app.services.state_archive --help.
Stop all writers before create --offline. Keep archives private: they contain user data and password hashes. Credentials/config are excluded; configured stores outside the backend root must be inventoried separately. Restoring to a different runtime path also requires updating absolute dataset/model references before serving.
Optional GCS client dependency: backend cloud-backup extra. Never publish state archives in GitHub.

## Remaining deployment work
1. Migrate all registries, owner controls, saved analyses and feature state into transactional durable storage.
2. Store uploaded files, reports and model artifacts in private object storage with ownership-scoped access.
3. Move long training work into resumable jobs.
4. Select a hosting/storage cost policy. Cloud Run free allowances do not guarantee a zero bill.
5. Deploy, then verify restart/scale-to-zero persistence and an external two-user HTTPS journey.
