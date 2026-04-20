/** Textos parametrizables para `RiskAssessmentCard` (portal cliente / onboarding). */
export type RiskAssessmentCardCopy = {
  headerEyebrow: string;
  title: string;
  scoreLabel: string;
  scoreSuffix: string;
  creditLimitTitle: string;
  collectionTermsTitle: string;
  reasonsTitle: string;
  acceptanceCheckbox: string;
  ctaConfirm: string;
  bands: {
    low: { label: string; tone: string };
    mid: { label: string; tone: string };
    high: { label: string; tone: string };
  };
};

export const RISK_ASSESSMENT_COPY_ES: RiskAssessmentCardCopy = {
  headerEyebrow: "Informe de Riesgo Financiero",
  title: "Evaluación de Alta Comercial",
  scoreLabel: "Score de riesgo:",
  scoreSuffix: "/10",
  creditLimitTitle: "Límite de crédito",
  collectionTermsTitle: "Plazo de cobro",
  reasonsTitle: "Motivos de evaluación",
  acceptanceCheckbox:
    "Acepto mi evaluacion de riesgo y el sistema de cobro automatico SEPA como condicion para operar.",
  ctaConfirm: "Confirmar y continuar",
  bands: {
    low: { label: "Confianza Alta", tone: "Riesgo bajo" },
    mid: { label: "Riesgo Moderado", tone: "Revisión recomendada" },
    high: { label: "Riesgo Alto", tone: "Aplicar cautelas" },
  },
};

export const RISK_ASSESSMENT_COPY_EN: RiskAssessmentCardCopy = {
  headerEyebrow: "Financial risk summary",
  title: "Commercial onboarding assessment",
  scoreLabel: "Risk score:",
  scoreSuffix: "/10",
  creditLimitTitle: "Credit limit",
  collectionTermsTitle: "Collection terms",
  reasonsTitle: "Assessment drivers",
  acceptanceCheckbox:
    "I accept my risk assessment and automatic SEPA Direct Debit collection as a condition to operate.",
  ctaConfirm: "Confirm and continue",
  bands: {
    low: { label: "High confidence", tone: "Low risk" },
    mid: { label: "Moderate risk", tone: "Review recommended" },
    high: { label: "High risk", tone: "Apply safeguards" },
  },
};
