# PetroEdge AI Release 2.3: Unified Data, Lineage and Reporting

Built on Release 2.2 Petrophysical Edge without replacing the established dark UI or first-class workspaces.

## Delivered
- Unified typed dataset records with immutable identifiers, checksums, field/well/reservoir context and typed categories.
- Raw and processed LAS versions with parent/root relationships and reproducible processing parameters.
- Dataset lineage endpoints and user interface.
- Fluid, PVT, formation-water, contact, pressure and temperature uploads via CSV/Excel.
- Reporting dependencies installed in the production Docker image so PDF buttons invoke real report generation.
- Persistent storage through existing Docker mounts.
- Release 2.2 direct Plotly runtime repair preserved to avoid react-plotly factory/default-import crashes.

## Compatibility
Existing SQLite dataset rows are migrated in place by the lightweight platform initialiser. Raw data are never overwritten during LAS processing.
