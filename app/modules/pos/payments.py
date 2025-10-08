"""
Servicios avanzados de métodos de pago para el módulo POS

Implementa funcionalidades avanzadas de pago:
- Mixed Payments: Efectivo + tarjeta en una sola venta
- QR Code Payments: Integración con billeteras digitales
- Payment Validation: Validaciones avanzadas de pagos
- Payment Processing: Procesamiento inteligente de pagos

Todas las funcionalidades mantienen compatibilidad con el sistema existente.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from enum import Enum
import json
import secrets
import string

from app.modules.pos.models import CashRegister, CashMovement, MovementType
from app.modules.invoices.models import Invoice, Payment, InvoiceStatus
from app.modules.invoices.schemas import PaymentMethod


class QRPaymentProvider(str, Enum):
    """Proveedores de pago QR soportados"""
    NEQUI = "nequi"
    DAVIPLATA = "daviplata"
    BANCOLOMBIA_QR = "bancolombia_qr"
    PSE = "pse"
    GENERIC_QR = "generic_qr"


class PaymentStatus(str, Enum):
    """Estados de procesamiento de pagos"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class AdvancedPaymentService:
    """Servicio para métodos de pago avanzados"""

    def __init__(self, db: Session):
        self.db = db

    # ===== PAGOS MIXTOS =====

    def process_mixed_payment(
        self,
        invoice_id: UUID,
        mixed_payments: List[Dict[str, Any]],
        tenant_id: UUID,
        user_id: UUID,
        cash_register_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Procesar pago mixto (efectivo + tarjeta + otros métodos).
        
        Args:
            invoice_id: ID de la factura
            mixed_payments: Lista de pagos con diferentes métodos
            tenant_id: ID del tenant
            user_id: ID del usuario
            cash_register_id: ID de caja registradora (para efectivo)
            
        Returns:
            Dict con resultado del procesamiento
        """
        try:
            # Obtener factura
            invoice = self.db.query(Invoice).filter(
                Invoice.id == invoice_id,
                Invoice.tenant_id == tenant_id
            ).first()

            if not invoice:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Factura no encontrada"
                )

            # Validar que no esté ya pagada
            if invoice.status == InvoiceStatus.PAID:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="La factura ya está pagada"
                )

            # Validar total de pagos
            total_payments = sum(Decimal(str(payment['amount'])) for payment in mixed_payments)
            
            if total_payments < invoice.total_amount:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Total de pagos ({total_payments}) es menor al total de la factura ({invoice.total_amount})"
                )

            # Procesar cada método de pago
            processed_payments = []
            cash_movements = []
            change_amount = Decimal('0')

            for payment_data in mixed_payments:
                payment_result = self._process_single_payment(
                    invoice=invoice,
                    payment_data=payment_data,
                    user_id=user_id,
                    cash_register_id=cash_register_id
                )
                
                processed_payments.append(payment_result['payment'])
                
                if payment_result.get('cash_movement'):
                    cash_movements.append(payment_result['cash_movement'])

            # Calcular vuelto si hay sobrepago en efectivo
            if total_payments > invoice.total_amount:
                change_amount = total_payments - invoice.total_amount
                
                # Registrar vuelto como movimiento de caja (solo si hay pago en efectivo)
                cash_payments = [p for p in mixed_payments if p['method'] == PaymentMethod.CASH]
                if cash_payments and cash_register_id:
                    change_movement = self._create_change_movement(
                        cash_register_id=cash_register_id,
                        amount=change_amount,
                        invoice_id=invoice_id,
                        user_id=user_id,
                        tenant_id=tenant_id
                    )
                    cash_movements.append(change_movement)

            # Actualizar estado de factura
            invoice.status = InvoiceStatus.PAID
            invoice.paid_amount = invoice.total_amount
            invoice.balance_due = Decimal('0')
            invoice.updated_at = datetime.utcnow()

            self.db.commit()

            return {
                'invoice_id': str(invoice_id),
                'total_amount': float(invoice.total_amount),
                'total_paid': float(total_payments),
                'change_amount': float(change_amount),
                'payments': [
                    {
                        'id': str(p.id),
                        'method': p.method,
                        'amount': float(p.amount),
                        'status': 'completed',
                        'reference': p.reference
                    } for p in processed_payments
                ],
                'cash_movements': [
                    {
                        'id': str(m.id),
                        'type': m.type.value,
                        'amount': float(m.amount),
                        'notes': m.notes
                    } for m in cash_movements
                ],
                'payment_summary': self._generate_payment_summary(mixed_payments, change_amount)
            }

        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error procesando pago mixto: {str(e)}"
            )

    def _process_single_payment(
        self,
        invoice: Invoice,
        payment_data: Dict[str, Any],
        user_id: UUID,
        cash_register_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Procesar un método de pago individual"""
        
        method = PaymentMethod(payment_data['method'])
        amount = Decimal(str(payment_data['amount']))
        reference = payment_data.get('reference', '')
        notes = payment_data.get('notes', '')

        # Crear registro de pago
        payment = Payment(
            tenant_id=invoice.tenant_id,
            invoice_id=invoice.id,
            amount=amount,
            method=method,
            reference=reference,
            payment_date=datetime.utcnow().date(),
            notes=notes,
            created_by=user_id
        )
        self.db.add(payment)
        self.db.flush()

        result = {'payment': payment}

        # Si es efectivo, crear movimiento de caja
        if method == PaymentMethod.CASH and cash_register_id:
            cash_movement = CashMovement(
                tenant_id=invoice.tenant_id,
                cash_register_id=cash_register_id,
                type=MovementType.SALE,
                amount=amount,
                reference=f"POS-{invoice.number}",
                notes=f"Pago en efectivo - Factura {invoice.number}",
                invoice_id=invoice.id,
                created_by=user_id
            )
            self.db.add(cash_movement)
            self.db.flush()
            result['cash_movement'] = cash_movement

        return result

    def _create_change_movement(
        self,
        cash_register_id: UUID,
        amount: Decimal,
        invoice_id: UUID,
        user_id: UUID,
        tenant_id: UUID
    ) -> CashMovement:
        """Crear movimiento de caja para vuelto"""
        
        movement = CashMovement(
            tenant_id=tenant_id,
            cash_register_id=cash_register_id,
            type=MovementType.WITHDRAWAL,
            amount=amount,
            reference=f"VUELTO-{invoice_id}",
            notes=f"Vuelto de venta POS",
            invoice_id=invoice_id,
            created_by=user_id
        )
        self.db.add(movement)
        self.db.flush()
        return movement

    def _generate_payment_summary(
        self,
        payments: List[Dict[str, Any]],
        change_amount: Decimal
    ) -> Dict[str, Any]:
        """Generar resumen de pagos por método"""
        
        summary = {}
        for payment in payments:
            method = payment['method']
            amount = Decimal(str(payment['amount']))
            
            if method not in summary:
                summary[method] = {
                    'method': method,
                    'total_amount': 0,
                    'count': 0
                }
            
            summary[method]['total_amount'] += float(amount)
            summary[method]['count'] += 1

        return {
            'by_method': list(summary.values()),
            'change_given': float(change_amount),
            'total_methods': len(summary)
        }

    # ===== CÓDIGOS QR =====

    def generate_qr_payment(
        self,
        invoice_id: UUID,
        amount: Decimal,
        provider: QRPaymentProvider,
        tenant_id: UUID,
        expires_in_minutes: int = 30
    ) -> Dict[str, Any]:
        """
        Generar código QR para pago con billetera digital.
        
        Args:
            invoice_id: ID de la factura
            amount: Monto a pagar
            provider: Proveedor de pago QR
            tenant_id: ID del tenant
            expires_in_minutes: Tiempo de expiración en minutos
            
        Returns:
            Dict con información del QR generado
        """
        try:
            # Validar factura
            invoice = self.db.query(Invoice).filter(
                Invoice.id == invoice_id,
                Invoice.tenant_id == tenant_id
            ).first()

            if not invoice:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Factura no encontrada"
                )

            # Generar código único para el QR
            qr_code = self._generate_qr_code()
            
            # Calcular tiempo de expiración
            expires_at = datetime.utcnow() + timedelta(minutes=expires_in_minutes)

            # Generar datos del QR según el proveedor
            qr_data = self._generate_qr_data(
                provider=provider,
                amount=amount,
                reference=f"POS-{invoice.number}",
                qr_code=qr_code
            )

            # En un sistema real, aquí se guardaría en Redis o base de datos
            # el estado del pago QR para tracking
            qr_payment_info = {
                'qr_code': qr_code,
                'qr_data': qr_data,
                'amount': float(amount),
                'provider': provider.value,
                'invoice_id': str(invoice_id),
                'expires_at': expires_at.isoformat(),
                'status': PaymentStatus.PENDING.value,
                'created_at': datetime.utcnow().isoformat(),
                'instructions': self._get_qr_instructions(provider)
            }

            return qr_payment_info

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generando QR de pago: {str(e)}"
            )

    def _generate_qr_code(self) -> str:
        """Generar código único para QR"""
        return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(12))

    def _generate_qr_data(
        self,
        provider: QRPaymentProvider,
        amount: Decimal,
        reference: str,
        qr_code: str
    ) -> str:
        """Generar datos específicos del QR según el proveedor"""
        
        base_data = {
            'amount': float(amount),
            'reference': reference,
            'code': qr_code,
            'currency': 'COP'
        }

        if provider == QRPaymentProvider.NEQUI:
            # Formato específico de Nequi
            qr_data = f"nequi://pay?amount={amount}&ref={reference}&code={qr_code}"
        
        elif provider == QRPaymentProvider.DAVIPLATA:
            # Formato específico de DaviPlata
            qr_data = f"daviplata://payment?monto={amount}&referencia={reference}&codigo={qr_code}"
        
        elif provider == QRPaymentProvider.BANCOLOMBIA_QR:
            # Formato QR de Bancolombia
            qr_data = json.dumps({
                'banco': 'bancolombia',
                'monto': float(amount),
                'referencia': reference,
                'codigo': qr_code
            })
        
        else:  # GENERIC_QR
            # Formato genérico JSON
            qr_data = json.dumps(base_data)

        return qr_data

    def _get_qr_instructions(self, provider: QRPaymentProvider) -> Dict[str, Any]:
        """Obtener instrucciones específicas por proveedor"""
        
        instructions = {
            QRPaymentProvider.NEQUI: {
                'title': 'Pago con Nequi',
                'steps': [
                    'Abre la app de Nequi',
                    'Selecciona "Pagar con QR"',
                    'Escanea el código QR',
                    'Confirma el monto y la transacción'
                ],
                'support_url': 'https://www.nequi.com.co/ayuda'
            },
            QRPaymentProvider.DAVIPLATA: {
                'title': 'Pago con DaviPlata',
                'steps': [
                    'Abre la app DaviPlata',
                    'Ve a "Pagar y transferir"',
                    'Selecciona "Pagar con QR"',
                    'Escanea el código y confirma'
                ],
                'support_url': 'https://www.daviplata.com/ayuda'
            },
            QRPaymentProvider.BANCOLOMBIA_QR: {
                'title': 'Pago con Bancolombia QR',
                'steps': [
                    'Abre la app Bancolombia',
                    'Selecciona "Pagar con QR"',
                    'Escanea el código QR',
                    'Verifica y confirma el pago'
                ],
                'support_url': 'https://www.bancolombia.com/ayuda'
            }
        }

        return instructions.get(provider, {
            'title': 'Pago con QR',
            'steps': [
                'Abre tu app de pagos favorita',
                'Escanea el código QR',
                'Confirma el monto y paga'
            ]
        })

    def verify_qr_payment_status(
        self,
        qr_code: str,
        tenant_id: UUID
    ) -> Dict[str, Any]:
        """
        Verificar estado de pago QR.
        
        En implementación real, esto consultaría APIs de los proveedores
        o base de datos de estados de pago.
        """
        try:
            # Simulación de verificación de estado
            # En producción, aquí se consultarían las APIs de los proveedores
            
            # Por ahora retornamos estado simulado
            return {
                'qr_code': qr_code,
                'status': PaymentStatus.PENDING.value,
                'last_check': datetime.utcnow().isoformat(),
                'message': 'Esperando confirmación del proveedor'
            }

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error verificando estado de pago QR: {str(e)}"
            )

    # ===== VALIDACIONES AVANZADAS =====

    def validate_payment_limits(
        self,
        tenant_id: UUID,
        payment_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validar límites de pagos por método y tenant"""
        
        validation_result = {
            'valid': True,
            'warnings': [],
            'errors': []
        }

        # Límites por defecto (en producción vendrían de configuración)
        limits = {
            PaymentMethod.CASH: Decimal('5000000'),  # 5M COP
            PaymentMethod.CARD: Decimal('50000000'),  # 50M COP
            PaymentMethod.TRANSFER: Decimal('100000000'),  # 100M COP
            'qr_daily_limit': Decimal('2000000')  # 2M COP por día
        }

        for payment in payment_data:
            method = PaymentMethod(payment['method'])
            amount = Decimal(str(payment['amount']))

            # Validar límites individuales
            if method in limits and amount > limits[method]:
                validation_result['errors'].append(
                    f"Monto {amount} excede límite para {method.value}: {limits[method]}"
                )
                validation_result['valid'] = False

            # Warnings para montos altos
            if amount > Decimal('1000000'):  # 1M COP
                validation_result['warnings'].append(
                    f"Monto alto detectado: {amount} en {method.value}"
                )

        return validation_result