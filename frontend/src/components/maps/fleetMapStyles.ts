/**
 * Estilo Bunker / zinc-950 para Google Maps JS (alineado con `bg-zinc-950`).
 */
export const BUNKER_MAP_STYLES: google.maps.MapTypeStyle[] = [
  { elementType: "geometry", stylers: [{ color: "#09090b" }] },
  { elementType: "labels.text.stroke", stylers: [{ color: "#09090b" }] },
  { elementType: "labels.text.fill", stylers: [{ color: "#a1a1aa" }] },
  { featureType: "administrative", elementType: "geometry", stylers: [{ color: "#18181b" }] },
  { featureType: "poi", elementType: "labels.text.fill", stylers: [{ color: "#71717a" }] },
  { featureType: "road", elementType: "geometry", stylers: [{ color: "#27272a" }] },
  { featureType: "road.highway", elementType: "geometry", stylers: [{ color: "#3f3f46" }] },
  { featureType: "road.highway", elementType: "geometry.stroke", stylers: [{ color: "#18181b" }] },
  { featureType: "transit", elementType: "geometry", stylers: [{ color: "#27272a" }] },
  { featureType: "water", elementType: "geometry", stylers: [{ color: "#020617" }] },
];
