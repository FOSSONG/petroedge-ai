export type PlatformSelection = { wellId?: string; datasetId?: string };

export function navigateTo(label: string, selection: PlatformSelection = {}) {
  if (selection.wellId) sessionStorage.setItem("petroedge_selected_well_id", selection.wellId);
  if (selection.datasetId) {
    sessionStorage.setItem("petroedge_selected_dataset_id", selection.datasetId);
    sessionStorage.setItem("petroedge_open_dataset_id", selection.datasetId);
  }
  window.dispatchEvent(new CustomEvent("petroedge:navigate", { detail: label }));
  window.dispatchEvent(new CustomEvent("petroedge:selection", { detail: selection }));
}
