import { useEffect, useMemo, useState } from "react";
import { listModels, type ModelManifest, type ModelTask } from "./modelPlatformApi";

interface ModelSelectorProps {
  task: ModelTask;
  value?: string;
  onChange: (modelId: string) => void;
  disabled?: boolean;
}

export function ModelSelector({ task, value, onChange, disabled }: ModelSelectorProps) {
  const [models, setModels] = useState<ModelManifest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    listModels(task)
      .then((items) => {
        if (!active) return;
        const available = items.filter((item) => item.enabled && !["failed", "archived", "deprecated"].includes(item.stage));
        setModels(available);
        setError(null);
        if (!value && available.length > 0) {
          const preferred = available.find((item) => item.stage === "production") ?? available[0];
          onChange(preferred.model_id);
        }
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Unable to load models");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [task]);

  const selected = useMemo(() => models.find((item) => item.model_id === value), [models, value]);

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium">Inference model</label>
      <select
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled || loading || models.length === 0}
        className="w-full rounded-md border px-3 py-2"
      >
        {loading && <option value="">Loading modelsâ€¦</option>}
        {!loading && models.length === 0 && <option value="">No compatible model</option>}
        {models.map((model) => (
          <option key={model.model_id} value={model.model_id}>
            {model.display_name} Â· {model.version} Â· {model.stage}
          </option>
        ))}
      </select>
      {selected && (
        <p className="text-xs opacity-75">
          {selected.algorithm} Â· {selected.framework} Â· {selected.resource_profile} resource profile
        </p>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}