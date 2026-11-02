export type Arc42ViewType = 'context' | 'building_block' | 'deployment';

export interface Arc42ViewMetadata {
  id: Arc42ViewType;
  title: string;
  section: string;
  description: string;
  mermaidSource: string;
}

export interface ArchitectureStateSummary {
  currentStep: string;
  totalComponents: number;
  migratedCount: number;
  remainingLegacyCount: number;
  coupledTablesCount: number;
}
