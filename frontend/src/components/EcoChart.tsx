"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

// Datos de demostración (luego los conectaremos a tu backend en tiempo real)
const ecoData = [
  { motor: 'Diésel Tradicional', emisiones: 2112, ahorro: 0 },
  { motor: 'Flota Híbrida', emisiones: 1267, ahorro: 845 },
  { motor: '100% Eléctrico', emisiones: 0, ahorro: 2112 },
];

export default function EcoChart() {
  return (
    <div className="bg-[#0f172a] p-6 rounded-2xl border border-slate-800 shadow-xl">
      <div className="mb-6">
        <h3 className="text-xl font-bold text-white">Impacto Sostenible (ESG)</h3>
        <p className="text-sm text-slate-400">Comparativa de emisiones y ahorro en ruta de 800km</p>
      </div>

      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={ecoData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
            <XAxis 
              dataKey="motor" 
              stroke="#94a3b8" 
              fontSize={12} 
              tickLine={false} 
              axisLine={false} 
            />
            <YAxis 
              stroke="#94a3b8" 
              fontSize={12} 
              tickLine={false} 
              axisLine={false} 
            />
            <Tooltip 
              cursor={{ fill: '#1e293b', opacity: 0.4 }}
              contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#f8fafc', borderRadius: '8px' }}
            />
            <Legend wrapperStyle={{ paddingTop: '20px' }} />
            
            <Bar dataKey="emisiones" name="Emisiones (kg CO2)" fill="#ef4444" radius={[4, 4, 0, 0]} barSize={40} />
            <Bar dataKey="ahorro" name="Ahorro ESG (kg CO2)" fill="#10b981" radius={[4, 4, 0, 0]} barSize={40} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}