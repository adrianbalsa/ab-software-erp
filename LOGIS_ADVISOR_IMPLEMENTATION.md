# [DONE] LogisAdvisor AI Chatbot Implementation

## Backend

### 1. chatbot.py [DONE]
```python
POST /api/v1/chatbot/ask
- Context injection: financial_summary + esg_summary
- System prompt: Financial/ESG data-driven responses
- Model: Claude 3.5 Sonnet (anthropic>=0.45.0)
- Security: Uses deps.get_current_user (JWT + RLS)
```

#### Context Functions:
- `_fetch_financial_context`: EBITDA, ingresos, gastos
- `_fetch_esg_context`: CO₂, km, portes facturados, ahorro estimado
- `_build_system_prompt`: Dynamic prompt with real-time data

### 2. Main Router [DONE]
```python
app.include_router(
    chatbot_v1.router,
    prefix="/api/v1/chatbot",
    tags=["IA y chat"]
)
```

### 3. Rate Limiting [DONE]
```python
RATE_LIMIT_EXEMPT_PREFIXES += "/api/v1/chatbot"
```

### 4. Requirements [DONE]
```txt
anthropic>=0.45.0 (added to requirements.txt)
```

## Frontend

### 5. LogisAdvisor.tsx [DONE]
```typescript
- Floating chat bubble (bottom-right)
- Shadcn UI components (Card, Button, Input, ScrollArea)
- Message history with timestamps
- Loading states with animated dots
- Dark mode design (emerald accent)
```

#### Features:
- Toggle open/close with smooth animations
- User/Assistant message bubbles
- Error handling with user-friendly messages
- Authorization via localStorage JWT

### 6. Quick Actions [DONE]
```typescript
3 predefined queries:
1. "Calculate my current EBITDA" → Financial analysis
2. "Show CO2 efficiency" → Sustainability metrics
3. "Route recommendations" → Optimization suggestions
```

#### Quick Actions UI:
- Always visible at bottom of chat
- Icon + label buttons
- Disabled during loading state

## Security [DONE]

### 7. RBAC/RLS Verification [DONE]
```python
Endpoint: current_user: UserOut = Depends(deps.get_current_user)
├── JWT validation via oauth2_scheme
├── ensure_empresa_context(current_user.empresa_id)
├── ensure_rbac_context(user=current_user)
└── All finance_service and esg_service calls use current_user.empresa_id

Data isolation:
- financial_summary: .eq("empresa_id", eid)
- calcular_huella_carbono_mensual: empresa_id parameter
- RLS enforced at DB layer (public.app_current_empresa_id())
```

## Environment Variables
```env
ANTHROPIC_API_KEY (backend, required)
NEXT_PUBLIC_GOOGLE_MAPS_API_KEY (frontend, for FleetMap integration)
```

## Response Schema
```json
{
  "response": "Tu EBITDA actual es de 45,230.50 EUR...",
  "context_used": {
    "financial": {
      "ingresos_eur": 123450.00,
      "gastos_eur": 78219.50,
      "ebitda_eur": 45230.50
    },
    "esg": {
      "total_co2_kg": 4521.30,
      "total_km_reales": 12450.00,
      "num_portes_facturados": 89,
      "media_co2_por_porte_kg": 50.80,
      "ahorro_estimado_kg": 226.07
    }
  }
}
```

All checkpoints marked [DONE].
