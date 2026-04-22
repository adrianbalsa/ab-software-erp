"use client";

import { useOptionalLocaleCatalog } from "@/context/LocaleContext";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { FadeInSection } from "./FadeInSection";

export function LandingFAQ() {
  const { catalog } = useOptionalLocaleCatalog();
  const l = catalog.landing.faq;

  return (
    <FadeInSection id="help" className="scroll-mt-20 px-4 py-24 sm:px-6 sm:py-28">
      <div className="mx-auto max-w-3xl">
        <div className="text-center mb-10">
          <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">{l.title}</h2>
          <p className="mt-2 text-zinc-300 text-sm">{l.subtitle}</p>
        </div>
        <Accordion type="single" collapsible defaultValue="faq-0" className="space-y-3">
          {l.items.map((item, i) => {
            return (
              <AccordionItem key={item.q} value={`faq-${i}`}>
                <AccordionTrigger>{item.q}</AccordionTrigger>
                <AccordionContent>{item.a}</AccordionContent>
              </AccordionItem>
            );
          })}
        </Accordion>
      </div>
    </FadeInSection>
  );
}
