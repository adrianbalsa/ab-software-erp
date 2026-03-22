"use client";

import { useEffect, useRef } from "react";
import { useMapsLibrary } from "@vis.gl/react-google-maps";

export type AddressAutocompleteProps = {
  id: string;
  label: string;
  /** Valor inicial; tras enviar el formulario, incrementa ``formKey`` en el padre para limpiar. */
  defaultValue?: string;
  onChange: (v: string) => void;
  placeholder?: string;
};

/**
 * Places Autocomplete (debe renderizarse bajo ``GoogleMapsProvider`` / ``APIProvider``).
 */
export function AddressAutocomplete({
  id,
  label,
  defaultValue = "",
  onChange,
  placeholder,
}: AddressAutocompleteProps) {
  const places = useMapsLibrary("places");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!places || !inputRef.current) return;

    const ac = new google.maps.places.Autocomplete(inputRef.current, {
      fields: ["formatted_address", "name"],
      types: ["address"],
    });

    const listener = ac.addListener("place_changed", () => {
      const p = ac.getPlace();
      const addr = p.formatted_address || inputRef.current?.value || "";
      onChange(addr);
    });

    return () => {
      google.maps.event.removeListener(listener);
    };
  }, [places, onChange]);

  return (
    <label className="block" htmlFor={id}>
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        ref={inputRef}
        id={id}
        defaultValue={defaultValue}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete="off"
        className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
      />
    </label>
  );
}
