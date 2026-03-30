import { useEffect, useState } from "react";

/**
 * Devuelve una copia del valor que solo se actualiza tras `delay` ms sin cambios.
 * Útil para inputs frecuentes (sliders) donde el efecto costoso debe ir diferido.
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);

  return debounced;
}
