import type { AppLocale } from "@/i18n/catalog";

export type ImportWizardStrings = {
  next: string;
  back: string;
  import: string;
  validate: string;
  confirmImport: string;
  chooseFile: string;
  stepPrepare: string;
  stepFile: string;
  stepReview: string;
  stepResult: string;
  newImport: string;
  selectedFile: string;
  dropHint: string;
  templatesHeading: string;
  validating: string;
  committing: string;
  backgroundImport: string;
  jobProgress: string;
};

const es: ImportWizardStrings = {
  next: "Siguiente",
  back: "Atrás",
  import: "Importar",
  validate: "Validar archivo",
  confirmImport: "Confirmar importación",
  chooseFile: "Elegir archivo",
  stepPrepare: "Plantilla",
  stepFile: "Archivo",
  stepReview: "Revisión",
  stepResult: "Resultado",
  newImport: "Nueva importación",
  selectedFile: "Archivo seleccionado",
  dropHint: "Arrastra y suelta aquí, o elige un archivo.",
  templatesHeading: "Plantillas descargables",
  validating: "Validando…",
  committing: "Importando…",
  backgroundImport: "Segundo plano (archivo grande)",
  jobProgress: "Progreso del servidor",
};

const en: ImportWizardStrings = {
  next: "Next",
  back: "Back",
  import: "Import",
  validate: "Validate file",
  confirmImport: "Confirm import",
  chooseFile: "Choose file",
  stepPrepare: "Template",
  stepFile: "File",
  stepReview: "Review",
  stepResult: "Result",
  newImport: "New import",
  selectedFile: "Selected file",
  dropHint: "Drag and drop here, or choose a file.",
  templatesHeading: "Downloadable templates",
  validating: "Validating…",
  committing: "Importing…",
  backgroundImport: "Background (large file)",
  jobProgress: "Server progress",
};

export function importWizardStrings(locale: AppLocale): ImportWizardStrings {
  return locale === "en" ? en : es;
}
