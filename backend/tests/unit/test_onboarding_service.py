import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from starlette.background import BackgroundTasks

from app.services.clientes_service import ClientesService

@pytest.mark.asyncio
async def test_resend_invite_success():
    """Caso de éxito: Cliente pendiente recibe nuevo email."""
    mock_db = MagicMock()
    service = ClientesService(db=mock_db)

    # Mock del cliente
    cliente_mock = MagicMock(id="123", email="test@logistics.com", riesgo_aceptado=False, mandato_activo=False)
    
    # Parcheamos el método de envío de email y el de obtención de cliente
    with patch.object(service, 'get_cliente_by_id', return_value=cliente_mock, create=True), \
         patch('app.services.email_service.send_onboarding_invite') as mock_send_email, \
         patch('app.db.supabase.auth_admin_generate_link', return_value="https://bunker.com/invite?token=xyz"):
        bg = BackgroundTasks()
        response = await service.resend_onboarding_invite(
            cliente_id="123",
            empresa_id="001",
            background_tasks=bg,
        )
        await bg()

        assert response["message"] == "Invitación reenviada correctamente"
        mock_send_email.assert_called_once()

@pytest.mark.asyncio
async def test_resend_invite_already_active():
    """Error 400: No se reenvía si el cliente ya está operativo."""
    mock_db = MagicMock()
    service = ClientesService(db=mock_db)

    # Cliente ya tiene el riesgo aceptado
    cliente_mock = MagicMock(id="123", riesgo_aceptado=True)
    
    with patch.object(service, 'get_cliente_by_id', return_value=cliente_mock, create=True):
        with pytest.raises(HTTPException) as exc:
            await service.resend_onboarding_invite(
                cliente_id="123",
                empresa_id="emp_001",
                background_tasks=BackgroundTasks(),
            )
        
        assert exc.value.status_code == 400
        assert "ya completó el onboarding" in exc.value.detail
