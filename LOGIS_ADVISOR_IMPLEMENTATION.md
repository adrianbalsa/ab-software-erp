# [DONE] LogisAdvisor AI Chatbot Implementation

## Backend

### 1. advisor.py [DONE]
```python
POST /api/v1/advisor/ask
- Context injection: ERP aggregate context (finance, ESG, BI, compliance)
- Modes: SSE streaming (default) or JSON (`stream=false`)
- Multi-provider LLM orchestration (LiteLLM)
- Security: Uses tenant-bound auth + RLS
```

#### Context Functions:
- `gather_advisor_context`: EBITDA, tesorería, CIP, flota, compliance, BI
- `mask_advisor_context_for_rbac`: minimización por rol
- `stream_advisor_response` / `get_advisor_response`: respuesta IA

### 2. Main Router [DONE]
```python
app.include_router(
    advisor_v1.router,
    prefix="/api/v1/advisor",
    tags=["IA y chat"]
)
```

### 3. Rate Limiting [DONE]
```python
expensive_endpoint_bucket("/api/v1/advisor/ask", "POST") == "ai"
```

### 4. Requirements [DONE]
```txt
LiteLLM + provider keys via SecretManager (OpenAI/Anthropic/Gemini/Azure)
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
  "reply": "Tu EBITDA actual es de 45,230.50 EUR...",
  "model": "openai/gpt-4o"
}
```

All checkpoints marked [DONE].
