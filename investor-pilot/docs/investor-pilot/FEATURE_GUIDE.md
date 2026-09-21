# PetroEdge AI investor pilot: feature guide
Date: 2026-09-21. Release 045 extends the 044 research pilot.
Deployment is not scientific model qualification.

## Dataset registry / Data Preparation Studio
The list shows dataset type, field/well, version, rows and size. A record shows its checksum, headers and lineage. The grid previews rows, supports edits and saves derived copies rather than changing raw measurements.
Upload now accepts LAS, CSV, Excel, Parquet, headered ASCII (TXT/ASC/ASCII/DAT/TSV), single-frame scalar DLIS and searchable PDF. PDF rows mean text-bearing pages, not depth samples.
Download dataset preserves its source format. Headerless numeric tables, duplicate headers and ambiguous DLIS frames are rejected.
Not supported as direct model inputs: LIS, SEG-Y/ZGY volumes, Petrel projects, simulator decks, scanned images and proprietary formats. Multi-frame DLIS currently requires selecting/exporting an acquisition as LAS. PDF OCR is not implemented.

## LAS Wizard
Select a table to inspect matched aliases, units, duplicate candidates and missing curves. Manual mapping with declared units creates an interpretation-ready copy. Automatic processing follows its configured QC options.
Case/punctuation and explicitly delimited units are recognized, including Unicode cubic centimetres, microseconds and ohms. Feet, kg/m3 and percentages convert only when declared.
Measured depth cannot be replaced by Well_id. TVD/TVDSS require trajectory conversion. Unknown company-specific mnemonics still require manual mapping; guessing would silently change scientific meaning.

## Reservoir Intelligence
Tracks show measured inputs and empirical screening outputs against depth. Cards and shaded intervals summarize lithology, porosity, permeability, saturation and candidate pay.
Oil/gas/water outputs are uncalibrated response scores, not trained probabilities or reserve estimates. Density/neutron porosity, empirical permeability and Archie Sw require formation-specific calibration.
Complete screening needs valid depth, GR, RT, RHOB and NPHI; optional sonic/caliper gaps remain missing. QC explains exclusions and blocks ambiguous units.
Research predictions are separate: current porosity/permeability artifacts have applicability checks and Excel exports. Positive permeability values can use a log scale; withheld/nonpositive values remain in exports.
PDF reports have visible errors and a browser-open fallback.

## Well Log Analysis / Interactive Logs
Five interpretation crossplots include RHOB/NPHI, Pickett, GR/RHOB, GR/NPHI and GR/RT. Pairwise QC lets available pairs display without every measurement being present.
Pickett settings expose Rw and matrix/fluid density. Its reference lines are scenarios, not fluid confirmation.
Measured tracks display GR, resistivity, density, neutron, sonic and caliper where available. Nulls remain gaps; resistivity uses a logarithmic axis. Zoom, hover and pan aid inspection.

## Training
Users select uploaded data, target, features, installed algorithm and split settings. Saved models include preprocessing and provenance; evaluation/promotion gates constrain leakage and unsupported deployment.
Neural network options depend on installing their actual runtimes and suitable training data. A selector alone does not mean a model is trained.
Existing porosity/permeability models are research only. Lithology development is conditional; saturation and oil/gas classification are not independently qualified.
The current collection has not supplied a new qualified independent parent well. Reusing the same test set is not independent validation.

## AI Assistant
The interface distinguishes saved-analysis evidence, measured-data evidence and empirical interpretation questions.
Measured questions return curve statistics/QC with dataset ID and checksum, even if complete reservoir interpretation fails.
New: select a searchable PDF to fit a local TF-IDF retrieval index. Responses return matching passages with page citations; weak matches abstain. This uses no paid LLM API.
It is extractive retrieval, not fine-tuned petroleum reasoning. Source passages are not automatically true. No OCR, image understanding, seismic interpretation or autonomous actions are claimed.

## AI Agents
Select geology, petrophysics, reservoir, drilling or QA and run one specialist or the panel.
Log results contain specialty-relevant statistics and checksums. Panel execution reads the source once rather than five times.
PDF objectives retrieve cited passages. The agents share that evidence; they do not independently validate each other. No fabricated confidence/agreement is reported.
Expert-reviewed task/answer/evidence labels and a held-out benchmark are still required for trained specialist language models.

## Edge Computing
Real 3W event history appears in the benchmark card. Play/pause advances recorded held-out samples; labels and experimental detector outputs can be compared and exported to CSV.
Device/replay/connector panels demonstrate software workflows, not successful connection to a real rig.
The 044 classifier failed: test macro-F1 0.1291 versus majority baseline 0.2721. Its binary was not promoted. Historical replay and source inspection are useful now; reliable early warning remains unqualified.
Next: more independent wells/events, sensor-unit alignment and a locked operational evaluation.

## Digital Well Twin
The measured-history panel displays GA-18/4 oil-rate history, persistence baseline and rejected research backtest. Separate scenario controls create/select a twin and inspect state/history.
The forecast candidate failed: test MAE 95.78 STB/d versus persistence 79.46. No trained forecast was promoted.
Local SQLite persistence works when its configured storage survives restart. One API worker is required. This is not a history-matched reservoir simulator.
Next: pressure/rate/injection histories, PVT, completions and physical constraints.

## CCUS
Forms expose area, thickness, porosity, CO2 density, efficiency and evidence flags. Outputs are volumetric capacity screening and injectivity/containment diagnostics.
Refresh reloads active data and clears stale last-created output.
Available logs/core/pressure can inform assumptions; no qualified injection/leakage training set or plume/containment model is established.

## Ownership / investor access
Owner controls create restricted accounts, disable users and pause access. Ownership checks protect datasets and analysis artifacts.
Duo is optional/off as requested. Use separate investor accounts.
Cloud storage must preserve accounts, datasets, models, experiments, predictions, analyses and twins. Local persistence does not automatically become Cloud Run persistence.

## Demonstration sequence
1. Upload a unit-declared log and show field/well identity, checksum and lineage.
2. Inspect mappings/QC; show an unresolved unit being caught.
3. Compare measured tracks and crossplots.
4. Explain empirical screening versus research prediction status.
5. Ask a measured-data question and a searchable-PDF question; show evidence citations.
6. Run the agent panel and replay real edge/production history.
7. Show model promotion gates and the data/funding required for scientific qualification.

## Dashboard, field/well assets, operations and model governance
The dashboard summarizes registered data, jobs and platform activity; it is not a live national production feed.
Field/well management links asset identities to datasets and analysis. Dataset binding/mapping remains explicit to prevent confusing an asset label with measured depth.
Operations and realtime panels show configured job/connector state; hardware connectivity must be tested against actual devices.
Readiness and independent-evaluation panels expose evidence gaps and model promotion gates. A research label remains visible rather than being hidden for the investor demonstration.
