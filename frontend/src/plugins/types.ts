import type { ComponentType, LazyExoticComponent, ReactNode } from "react";

export type ResourceClass = "light" | "medium" | "heavy";

export interface ModuleDefinition {
  key: string;
  name: string;
  description: string;
  resourceClass: ResourceClass;
  icon: ReactNode;
  capabilities: string[];
  component: LazyExoticComponent<ComponentType>;
}
