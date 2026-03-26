"use client";

import { forwardRef } from "react";
import SignatureCanvas from "react-signature-canvas";

type Props = {
  canvasW: number;
};

/** Canvas de firma para POD; solo cliente (importar vía `next/dynamic` con `ssr: false`). */
export const SignatureEntregaPad = forwardRef<SignatureCanvas | null, Props>(
  function SignatureEntregaPad({ canvasW }, ref) {
    return (
      <SignatureCanvas
        ref={ref}
        penColor="#34d399"
        backgroundColor="rgba(9, 9, 11, 1)"
        canvasProps={{
          width: canvasW,
          height: 220,
          className: "w-full touch-none rounded-xl border-2 border-emerald-600/40",
        }}
      />
    );
  },
);
