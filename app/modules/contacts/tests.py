"""
Tests para el módulo de Contactos

Tests comprehensivos que cubren:
- CRUD completo con validaciones multi-tenant
- Soft delete y restore
- Validaciones de documentos colombianos (NIT)
- Búsquedas y filtros
- Integración con otros módulos
- Casos edge y manejo de errores

Todos los tests validan que los datos estén correctamente scoped por company_id.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from decimal import Decimal

from app.main import app
from app.modules.contacts.models import Contact, ContactType, PersonType, IdType
from app.modules.contacts.schemas import ContactCreate, ContactUpdate
from app.modules.contacts.service import ContactService
from app.modules.contacts.models import calculate_nit_dv, validate_nit_with_dv


client = TestClient(app)


# ===== FIXTURES =====

@pytest.fixture
def sample_contact_data():
    """Datos de ejemplo para crear contactos"""
    return {
        "name": "Empresa de Prueba S.A.S.",
        "type": [ContactType.CLIENT.value, ContactType.PROVIDER.value],
        "email": "contacto@empresaprueba.com",
        "phone_primary": "601-234-5678",
        "mobile": "310-123-4567",
        "id_type": IdType.NIT,
        "id_number": "900123456",
        "dv": 1,  # Dígito de verificación calculado
        "person_type": PersonType.JURIDICA,
        "fiscal_responsibilities": ["O-13", "O-15"],
        "payment_terms_days": 30,
        "credit_limit": Decimal("5000000.00"),
        "billing_address": {
            "street": "Carrera 7 # 32-16",
            "city": "Bogotá",
            "state": "Cundinamarca",
            "country": "Colombia",
            "postal_code": "110111"
        },
        "notes": "Cliente empresarial importante"
    }


@pytest.fixture
def sample_person_contact():
    """Datos de ejemplo para contacto persona natural"""
    return {
        "name": "Juan Pérez",
        "type": [ContactType.CLIENT.value],
        "email": "juan.perez@email.com",
        "mobile": "320-555-1234",
        "id_type": IdType.CEDULA,
        "id_number": "12345678",
        "person_type": PersonType.NATURAL,
        "fiscal_responsibilities": ["R-99-PN"],
        "payment_terms_days": 15
    }


# ===== TESTS DE VALIDACIONES NIT =====

class TestNitValidation:
    """Tests para validación de NIT colombiano"""
    
    def test_calculate_nit_dv_valid(self):
        """Test cálculo correcto de dígito de verificación"""
        assert calculate_nit_dv("900123456") == 1
        assert calculate_nit_dv("830063999") == 5
        assert calculate_nit_dv("900373115") == 0
        assert calculate_nit_dv("11111111") == 1
    
    def test_calculate_nit_dv_invalid_input(self):
        """Test manejo de entradas inválidas"""
        assert calculate_nit_dv("") is None
        assert calculate_nit_dv("abc") is None
        assert calculate_nit_dv("12") is None  # Muy corto
    
    def test_validate_nit_with_dv_valid(self):
        """Test validación completa de NIT con DV"""
        assert validate_nit_with_dv("900123456", 1) == True
        assert validate_nit_with_dv("830063999", 5) == True
        assert validate_nit_with_dv("900373115", 0) == True
    
    def test_validate_nit_with_dv_invalid(self):
        """Test validación con DV incorrecto"""
        assert validate_nit_with_dv("900123456", 2) == False
        assert validate_nit_with_dv("830063999", 1) == False
        assert validate_nit_with_dv("", 1) == False


# ===== TESTS DE MODELOS =====

class TestContactModel:
    """Tests para el modelo Contact"""
    
    def test_contact_creation(self, db_session: Session, sample_company, sample_user):
        """Test creación básica de contacto"""
        contact = Contact(
            name="Test Contact",
            type=[ContactType.CLIENT.value],
            email="test@example.com",
            company_id=sample_company.id,
            created_by=sample_user.id,
            updated_by=sample_user.id
        )
        
        db_session.add(contact)
        db_session.commit()
        db_session.refresh(contact)
        
        assert contact.id is not None
        assert contact.name == "Test Contact"
        assert contact.type == [ContactType.CLIENT.value]
        assert contact.is_active == True
        assert contact.deleted_at is None
        assert contact.created_at is not None
    
    def test_contact_soft_delete(self, db_session: Session, sample_company, sample_user):
        """Test soft delete de contacto"""
        contact = Contact(
            name="Test Contact",
            type=[ContactType.CLIENT.value],
            company_id=sample_company.id,
            created_by=sample_user.id,
            updated_by=sample_user.id
        )
        
        db_session.add(contact)
        db_session.commit()
        
        # Soft delete
        contact.deleted_at = datetime.utcnow()
        contact.is_active = False
        db_session.commit()
        
        assert contact.deleted_at is not None
        assert contact.is_active == False
    
    def test_unique_constraint_document(self, db_session: Session, sample_company, sample_user):
        """Test constraint único por documento en empresa"""
        # Primer contacto
        contact1 = Contact(
            name="Contact 1",
            type=[ContactType.CLIENT.value],
            id_number="123456789",
            company_id=sample_company.id,
            created_by=sample_user.id,
            updated_by=sample_user.id
        )
        db_session.add(contact1)
        db_session.commit()
        
        # Segundo contacto con mismo documento (debe fallar)
        contact2 = Contact(
            name="Contact 2",
            type=[ContactType.PROVIDER.value],
            id_number="123456789",
            company_id=sample_company.id,
            created_by=sample_user.id,
            updated_by=sample_user.id
        )
        
        db_session.add(contact2)
        
        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()


# ===== TESTS DE SERVICIOS =====

class TestContactService:
    """Tests para ContactService"""
    
    def test_create_contact_success(self, db_session: Session, sample_company, sample_user, sample_contact_data):
        """Test creación exitosa de contacto"""
        contact_service = ContactService(db_session)
        contact_create = ContactCreate(**sample_contact_data)
        
        contact = contact_service.create_contact(contact_create, sample_company.id, sample_user.id)
        
        assert contact.id is not None
        assert contact.name == sample_contact_data["name"]
        assert contact.email == sample_contact_data["email"]
        assert contact.company_id == sample_company.id
        assert contact.created_by == sample_user.id
        assert ContactType.CLIENT.value in contact.type
        assert ContactType.PROVIDER.value in contact.type
    
    def test_create_contact_duplicate_document(self, db_session: Session, sample_company, sample_user, sample_contact_data):
        """Test error al crear contacto con documento duplicado"""
        contact_service = ContactService(db_session)
        
        # Crear primer contacto
        contact_create1 = ContactCreate(**sample_contact_data)
        contact_service.create_contact(contact_create1, sample_company.id, sample_user.id)
        
        # Intentar crear segundo contacto con mismo documento
        contact_create2 = ContactCreate(**{
            **sample_contact_data,
            "name": "Otro nombre"
        })
        
        with pytest.raises(HTTPException) as exc_info:
            contact_service.create_contact(contact_create2, sample_company.id, sample_user.id)
        
        assert exc_info.value.status_code == 409
        assert "documento" in str(exc_info.value.detail).lower()
    
    def test_get_contacts_with_filters(self, db_session: Session, sample_company, sample_user):
        """Test listado de contactos con filtros"""
        contact_service = ContactService(db_session)
        
        # Crear contactos de prueba
        clients = []
        for i in range(3):
            client = Contact(
                name=f"Cliente {i}",
                type=[ContactType.CLIENT.value],
                email=f"cliente{i}@test.com",
                company_id=sample_company.id,
                created_by=sample_user.id,
                updated_by=sample_user.id
            )
            clients.append(client)
            db_session.add(client)
        
        providers = []
        for i in range(2):
            provider = Contact(
                name=f"Proveedor {i}",
                type=[ContactType.PROVIDER.value],
                email=f"proveedor{i}@test.com",
                company_id=sample_company.id,
                created_by=sample_user.id,
                updated_by=sample_user.id
            )
            providers.append(provider)
            db_session.add(provider)
        
        db_session.commit()
        
        # Test sin filtros
        result = contact_service.get_contacts(sample_company.id)
        assert result.total == 5
        assert len(result.items) == 5
        
        # Test filtro por tipo cliente
        from app.modules.contacts.schemas import ContactSearchFilters
        client_filter = ContactSearchFilters(type=ContactType.CLIENT)
        result = contact_service.get_contacts(sample_company.id, filters=client_filter)
        assert result.total == 3
        
        # Test filtro por tipo proveedor
        provider_filter = ContactSearchFilters(type=ContactType.PROVIDER)
        result = contact_service.get_contacts(sample_company.id, filters=provider_filter)
        assert result.total == 2
        
        # Test búsqueda por texto
        search_filter = ContactSearchFilters(search="Cliente 1")
        result = contact_service.get_contacts(sample_company.id, filters=search_filter)
        assert result.total == 1
        assert "Cliente 1" in result.items[0].name
    
    def test_soft_delete_and_restore(self, db_session: Session, sample_company, sample_user, sample_contact_data):
        """Test soft delete y restore de contacto"""
        contact_service = ContactService(db_session)
        
        # Crear contacto
        contact_create = ContactCreate(**sample_contact_data)
        contact = contact_service.create_contact(contact_create, sample_company.id, sample_user.id)
        contact_id = contact.id
        
        # Verificar que existe y está activo
        found_contact = contact_service.get_contact_by_id(contact_id, sample_company.id)
        assert found_contact.is_active == True
        assert found_contact.deleted_at is None
        
        # Soft delete
        result = contact_service.delete_contact(contact_id, sample_company.id, sample_user.id)
        assert "eliminado" in result["message"].lower()
        
        # Verificar que no aparece en búsquedas normales
        with pytest.raises(HTTPException) as exc_info:
            contact_service.get_contact_by_id(contact_id, sample_company.id)
        assert exc_info.value.status_code == 404
        
        # Pero sí aparece incluyendo eliminados
        deleted_contact = contact_service.get_contact_by_id(contact_id, sample_company.id, include_deleted=True)
        assert deleted_contact.deleted_at is not None
        assert deleted_contact.is_active == False
        
        # Restore
        from app.modules.contacts.schemas import ContactRestore
        restore_data = ContactRestore(reason="Restaurado para testing")
        restored_contact = contact_service.restore_contact(contact_id, sample_company.id, sample_user.id, restore_data)
        
        assert restored_contact.deleted_at is None
        assert restored_contact.is_active == True
        assert "RESTAURADO" in restored_contact.notes
    
    def test_multi_tenant_isolation(self, db_session: Session, sample_user):
        """Test aislamiento multi-tenant"""
        # Crear dos empresas
        from app.modules.company.models import Company
        company1 = Company(name="Company 1", created_by=sample_user.id, updated_by=sample_user.id)
        company2 = Company(name="Company 2", created_by=sample_user.id, updated_by=sample_user.id)
        db_session.add_all([company1, company2])
        db_session.commit()
        
        contact_service = ContactService(db_session)
        
        # Crear contacto en empresa 1
        contact1 = Contact(
            name="Contact Company 1",
            type=[ContactType.CLIENT.value],
            company_id=company1.id,
            created_by=sample_user.id,
            updated_by=sample_user.id
        )
        db_session.add(contact1)
        db_session.commit()
        
        # Crear contacto en empresa 2
        contact2 = Contact(
            name="Contact Company 2", 
            type=[ContactType.CLIENT.value],
            company_id=company2.id,
            created_by=sample_user.id,
            updated_by=sample_user.id
        )
        db_session.add(contact2)
        db_session.commit()
        
        # Verificar aislamiento
        company1_contacts = contact_service.get_contacts(company1.id)
        company2_contacts = contact_service.get_contacts(company2.id)
        
        assert company1_contacts.total == 1
        assert company2_contacts.total == 1
        assert company1_contacts.items[0].name == "Contact Company 1"
        assert company2_contacts.items[0].name == "Contact Company 2"
        
        # Intentar acceder contacto de otra empresa debe fallar
        with pytest.raises(HTTPException) as exc_info:
            contact_service.get_contact_by_id(contact1.id, company2.id)
        assert exc_info.value.status_code == 404


# ===== TESTS DE INTEGRACIÓN =====

class TestContactIntegration:
    """Tests de integración con otros módulos"""
    
    def test_get_clients_for_invoices(self, db_session: Session, sample_company, sample_user):
        """Test obtener clientes para facturas"""
        contact_service = ContactService(db_session)
        
        # Crear contactos mixtos
        mixed_contact = Contact(
            name="Cliente y Proveedor",
            type=[ContactType.CLIENT.value, ContactType.PROVIDER.value],
            email="mixed@test.com",
            company_id=sample_company.id,
            created_by=sample_user.id,
            updated_by=sample_user.id
        )
        
        # Crear solo cliente
        client_only = Contact(
            name="Solo Cliente",
            type=[ContactType.CLIENT.value],
            email="client@test.com", 
            company_id=sample_company.id,
            created_by=sample_user.id,
            updated_by=sample_user.id
        )
        
        # Crear solo proveedor
        provider_only = Contact(
            name="Solo Proveedor",
            type=[ContactType.PROVIDER.value],
            email="provider@test.com",
            company_id=sample_company.id,
            created_by=sample_user.id,
            updated_by=sample_user.id
        )
        
        db_session.add_all([mixed_contact, client_only, provider_only])
        db_session.commit()
        
        # Obtener clientes para facturas
        clients = contact_service.get_clients_for_invoices(sample_company.id)
        
        # Debe retornar solo los que tienen tipo CLIENT
        assert len(clients) == 2
        client_names = [c.name for c in clients]
        assert "Cliente y Proveedor" in client_names
        assert "Solo Cliente" in client_names
        assert "Solo Proveedor" not in client_names
    
    def test_get_providers_for_bills(self, db_session: Session, sample_company, sample_user):
        """Test obtener proveedores para compras"""
        contact_service = ContactService(db_session)
        
        # Usar los mismos contactos del test anterior
        mixed_contact = Contact(
            name="Cliente y Proveedor",
            type=[ContactType.CLIENT.value, ContactType.PROVIDER.value],
            company_id=sample_company.id,
            created_by=sample_user.id,
            updated_by=sample_user.id
        )
        
        provider_only = Contact(
            name="Solo Proveedor",
            type=[ContactType.PROVIDER.value],
            company_id=sample_company.id,
            created_by=sample_user.id,
            updated_by=sample_user.id
        )
        
        client_only = Contact(
            name="Solo Cliente",
            type=[ContactType.CLIENT.value],
            company_id=sample_company.id,
            created_by=sample_user.id,
            updated_by=sample_user.id
        )
        
        db_session.add_all([mixed_contact, provider_only, client_only])
        db_session.commit()
        
        # Obtener proveedores para compras
        providers = contact_service.get_providers_for_bills(sample_company.id)
        
        # Debe retornar solo los que tienen tipo PROVIDER
        assert len(providers) == 2
        provider_names = [p.name for p in providers]
        assert "Cliente y Proveedor" in provider_names
        assert "Solo Proveedor" in provider_names
        assert "Solo Cliente" not in provider_names


# ===== TESTS DE API ENDPOINTS =====

class TestContactAPI:
    """Tests de endpoints API"""
    
    def test_create_contact_endpoint(self, auth_headers, sample_contact_data):
        """Test endpoint de creación de contacto"""
        response = client.post(
            "/contacts/",
            json=sample_contact_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_contact_data["name"]
        assert data["email"] == sample_contact_data["email"]
        assert ContactType.CLIENT.value in data["type"]
    
    def test_get_contacts_endpoint(self, auth_headers):
        """Test endpoint de listado de contactos"""
        response = client.get(
            "/contacts/",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
    
    def test_get_contact_by_id_endpoint(self, auth_headers, sample_contact_id):
        """Test endpoint de obtener contacto por ID"""
        response = client.get(
            f"/contacts/{sample_contact_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_contact_id)
    
    def test_update_contact_endpoint(self, auth_headers, sample_contact_id):
        """Test endpoint de actualización de contacto"""
        update_data = {
            "name": "Nombre Actualizado",
            "notes": "Nota actualizada"
        }
        
        response = client.put(
            f"/contacts/{sample_contact_id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Nombre Actualizado"
        assert data["notes"] == "Nota actualizada"
    
    def test_delete_contact_endpoint(self, auth_headers, sample_contact_id):
        """Test endpoint de eliminación de contacto"""
        response = client.delete(
            f"/contacts/{sample_contact_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert "eliminado" in response.json()["message"].lower()
    
    def test_get_clients_for_invoices_endpoint(self, auth_headers):
        """Test endpoint de clientes para facturas"""
        response = client.get(
            "/contacts/clients/for-invoices",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_providers_for_bills_endpoint(self, auth_headers):
        """Test endpoint de proveedores para compras"""
        response = client.get(
            "/contacts/providers/for-bills", 
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_contact_stats_endpoint(self, auth_headers):
        """Test endpoint de estadísticas"""
        response = client.get(
            "/contacts/stats/summary",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "total_contacts" in data
        assert "active_contacts" in data
        assert "clients" in data
        assert "providers" in data


# ===== TESTS DE PERFORMANCE =====

class TestContactPerformance:
    """Tests de rendimiento y escalabilidad"""
    
    def test_bulk_create_contacts(self, db_session: Session, sample_company, sample_user):
        """Test creación masiva de contactos"""
        contact_service = ContactService(db_session)
        
        # Crear 100 contactos
        contacts_created = 0
        for i in range(100):
            try:
                contact_data = ContactCreate(
                    name=f"Contacto Masivo {i}",
                    type=[ContactType.CLIENT.value],
                    email=f"masivo{i}@test.com",
                    id_number=f"DOC{i:06d}"
                )
                contact_service.create_contact(contact_data, sample_company.id, sample_user.id)
                contacts_created += 1
            except Exception as e:
                print(f"Error creando contacto {i}: {e}")
        
        # Verificar que se crearon la mayoría
        assert contacts_created > 95
        
        # Verificar paginación funciona bien
        result = contact_service.get_contacts(sample_company.id, limit=50, offset=0)
        assert len(result.items) == 50
        assert result.total >= 100
        
        result_page2 = contact_service.get_contacts(sample_company.id, limit=50, offset=50)
        assert len(result_page2.items) <= 50
    
    def test_search_performance(self, db_session: Session, sample_company, sample_user):
        """Test rendimiento de búsquedas"""
        contact_service = ContactService(db_session)
        
        # Crear contactos con patrones de búsqueda
        search_terms = ["ACME", "Global", "Tech", "Solutions", "Corp"]
        for i, term in enumerate(search_terms):
            for j in range(10):
                contact_data = ContactCreate(
                    name=f"{term} Company {j}",
                    type=[ContactType.CLIENT.value],
                    email=f"{term.lower()}{j}@test.com"
                )
                contact_service.create_contact(contact_data, sample_company.id, sample_user.id)
        
        # Test búsquedas
        from app.modules.contacts.schemas import ContactSearchFilters
        
        # Búsqueda exacta
        search_filter = ContactSearchFilters(search="ACME")
        result = contact_service.get_contacts(sample_company.id, filters=search_filter)
        assert result.total == 10
        
        # Búsqueda parcial
        search_filter = ContactSearchFilters(search="Global Company 5")
        result = contact_service.get_contacts(sample_company.id, filters=search_filter)
        assert result.total == 1