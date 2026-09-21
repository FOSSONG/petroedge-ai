# PetroEdge investor pilot release 044

This is a staged investor pilot, NOT evidence of industrial model qualification.
No public deployment has occurred. A working owner cloud account, DNS and Duo enrollment are required.

## Recommended resource envelope
Use an owner-controlled Linux ARM64 or AMD64 machine with at least 2 CPUs, 8 GB RAM and 20 GB free disk for images/state/backups. This is a conservative deployment target, not a measured minimum. Oracle currently documents 2 OCPUs/12 GB for Always Free A1 and 200 GB shared boot/block storage; check your own tenancy quota and actual available capacity. Do not use the 1 GB micro VM for this full stack. No automatic paid upgrade or billable resource creation is included.
Render Free lacks persistent local disks and is incompatible with the present SQLite/file-backed design. A frontend-only free host does not solve backend compute/storage.

## Phone approval and owner control
Create an owner-controlled Duo Free Web SDK application (official documentation lists up to 10 free users). Pre-enroll ONLY your own phone under the exact owner email. Deny unknown users; do not allow self-enrollment by someone who merely knows your PetroEdge password. Activate Universal Prompt. Register redirect URI https://YOUR_HOST/api/v1/auth/duo/callback. Set the three Duo values in pilot.env; verify phone enrollment before permitting public traffic.
Every owner/admin password login requires a fresh successful Duo Push with user_approved evidence. Remembered-device, bypass, passcode and missing context responses are rejected. No fail-open path. The app rechecks active accounts and the pilot pause switch. Operations can pause customer access immediately. Do not share the owner password; provision viewers for investors.
The local development instance remains password-only until Duo is configured; do not publish it directly. Provider enrollment and a physical phone end-to-end test are pending.

## Deployment
1. Unpack the release on your owner VM; point a DNS name at it, allow inbound 80/443, restrict SSH to yourself.
2. Copy deploy/pilot.env.example to deploy/pilot.env, fill it privately and chmod 600 it.
3. From deploy run: docker compose --env-file pilot.env -f compose.yaml config --quiet
4. Run: docker compose --env-file pilot.env -f compose.yaml up -d --build
5. Check health, deny/cancel phone approval, approve phone sign-in, test owner/customer isolation and pause, upload the private example CSV and verify plots/export.
The initial administrator is created only for an empty database; existing accounts/passwords are never overwritten. Linux images are CPU-only. The UI is prebuilt locally using /api/v1, so no Node build runs on the small VM. Actual ARM image build and resource stress testing still required if not recorded in the assessment.

## Demonstration scope
Research porosity/permeability remains experimental. Edge replay shows real-source labels and held-out experimental predictions with failure metrics. The failed edge detector binary is excluded. Digital twin displays real GA-18/4 oil history and a chronological backtest; its candidate lost to persistence and is excluded from serving. Measured evidence agents and assistant use authorized curve statistics/checksums; no new trained language model. Existing saved-analysis answers remain available. No seismic interpretation or validated CCUS forecast is claimed.
Twin state/history persists in SQLite when PETROEDGE_TWIN_STORE is enabled. Use exactly one API worker; two concurrent writers to the in-memory twin objects are unsupported.

## Updates and shutdown
Keep training offline. You do not need to delete a deployed site to retrain; version/test new models and explicitly promote them later. The owner can pause customer access, retain persistent volumes, deploy a new release and roll back if needed. Never use docker compose down --volumes unless deliberately erasing pilot data.
Before upgrades, pause customer access and stop API writes; back up ALL named state volumes to owner storage. Test restoration on a separate instance before relying on a backup. This package does not contain credentials or existing user databases.
