import { motion } from "framer-motion";

interface StepperWizardProps {
  steps: string[];
  activeStep: number;
}

export function StepperWizard({ steps, activeStep }: StepperWizardProps): JSX.Element {
  return (
    <ol className="grid gap-2 rounded-xl border border-border bg-surface p-4 md:grid-cols-3">
      {steps.map((step, index) => {
        const isActive = index === activeStep;
        const isComplete = index < activeStep;
        return (
          <motion.li
            key={step}
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.25, ease: "easeOut", delay: index * 0.03 }}
            className={`rounded-lg border px-3 py-2 text-sm transition-all duration-200 ease-out ${
              isActive
                ? "border-primary bg-primary-subtle text-primary"
                : isComplete
                  ? "border-success bg-success-subtle text-success"
                  : "border-border bg-surface-hover text-foreground-muted"
            }`}
          >
            <span className="font-semibold">{index + 1}.</span> {step}
          </motion.li>
        );
      })}
    </ol>
  );
}
