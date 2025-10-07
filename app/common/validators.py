"""
Validadores específicos para Colombia
"""
import re
from typing import Optional


def validate_colombia_phone(phone: str) -> bool:
    """
    Valida número de teléfono colombiano.
    Formatos válidos:
    - +57XXXXXXXXXX (10 dígitos después del +57)
    - 57XXXXXXXXXX (10 dígitos después del 57)
    - 3XXXXXXXXX (móvil, 10 dígitos empezando por 3)
    - XXXXXXXXXX (10 dígitos)
    """
    # Limpiar espacios y caracteres especiales
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Patrones válidos para Colombia
    patterns = [
        r'^\+57[3][0-9]{9}$',      # +573XXXXXXXXX (móvil)
        r'^\+57[1-8][0-9]{7}$',    # +571XXXXXXX (fijo Bogotá) o +575XXXXXXX (fijo Barranquilla), etc
        r'^57[3][0-9]{9}$',        # 573XXXXXXXXX (móvil sin +)
        r'^57[1-8][0-9]{7}$',      # 571XXXXXXX (fijo sin +)
        r'^[3][0-9]{9}$',          # 3XXXXXXXXX (móvil local)
        r'^[1-8][0-9]{7}$',        # 1XXXXXXX (fijo local)
    ]
    
    return any(re.match(pattern, cleaned) for pattern in patterns)


def validate_colombia_cedula(cedula: str) -> bool:
    """
    Valida cédula colombiana.
    - Entre 7 y 10 dígitos
    - Solo números
    - No puede empezar con 0
    """
    # Limpiar puntos y espacios
    cleaned = re.sub(r'[\.\s]', '', cedula)
    
    # Verificar que sea solo números
    if not cleaned.isdigit():
        return False
    
    # Verificar longitud (7-10 dígitos)
    if not 7 <= len(cleaned) <= 10:
        return False
    
    # No puede empezar con 0
    if cleaned.startswith('0'):
        return False
    
    return True


def validate_colombia_nit(nit: str) -> bool:
    """
    Valida NIT colombiano.
    - Entre 8 y 10 dígitos base + dígito de verificación
    - Formato: XXXXXXXXX-X
    - Calcula dígito de verificación
    """
    # Limpiar puntos, espacios y guiones
    cleaned = re.sub(r'[\.\s\-]', '', nit)
    
    # Verificar que sea solo números
    if not cleaned.isdigit():
        return False
    
    # Verificar longitud (9-11 dígitos total)
    if not 9 <= len(cleaned) <= 11:
        return False
    
    # Separar número base y dígito de verificación
    if len(cleaned) < 9:
        return False
    
    numero_base = cleaned[:-1]
    digito_verificacion = int(cleaned[-1])
    
    # Calcular dígito de verificación
    multiplicadores = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
    suma = 0
    
    for i, digito in enumerate(reversed(numero_base)):
        if i < len(multiplicadores):
            suma += int(digito) * multiplicadores[i]
    
    resto = suma % 11
    
    if resto < 2:
        digito_calculado = resto
    else:
        digito_calculado = 11 - resto
    
    return digito_verificacion == digito_calculado


def validate_colombia_nit_base(nit: str) -> bool:
    """
    Valida NIT colombiano base (sin dígito de verificación).
    - Entre 8 y 10 dígitos
    - Solo números
    - No puede empezar con 0
    Ejemplo: 901886184
    """
    # Limpiar puntos y espacios
    cleaned = re.sub(r'[\.\s]', '', nit)
    
    # Verificar que sea solo números
    if not cleaned.isdigit():
        return False
    
    # Verificar longitud (8-10 dígitos)
    if not 8 <= len(cleaned) <= 10:
        return False
    
    # No puede empezar con 0
    if cleaned.startswith('0'):
        return False
    
    return True


def format_colombia_phone(phone: str) -> str:
    """
    Formatea número de teléfono colombiano al formato estándar +57XXXXXXXXXX
    """
    if not validate_colombia_phone(phone):
        return phone  # Retorna sin cambios si no es válido
    
    # Limpiar
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Normalizar a formato +57XXXXXXXXXX
    if cleaned.startswith('+57'):
        return cleaned
    elif cleaned.startswith('57') and len(cleaned) >= 10:
        return '+' + cleaned
    elif cleaned.startswith('3') and len(cleaned) == 10:
        return '+57' + cleaned
    elif len(cleaned) in [8, 10]:
        return '+57' + cleaned
    
    return phone


def format_colombia_nit(nit: str) -> str:
    """
    Formatea NIT colombiano al formato estándar XXXXXXXXX-X
    """
    if not validate_colombia_nit(nit):
        return nit  # Retorna sin cambios si no es válido
    
    # Limpiar
    cleaned = re.sub(r'[\.\s\-]', '', nit)
    
    # Formatear con guión antes del último dígito
    return f"{cleaned[:-1]}-{cleaned[-1]}"


def format_colombia_nit_base(nit: str) -> str:
    """
    Formatea NIT colombiano base (sin dígito de verificación) removiendo puntos y espacios
    """
    if not validate_colombia_nit_base(nit):
        return nit  # Retorna sin cambios si no es válido
    
    # Limpiar puntos y espacios
    cleaned = re.sub(r'[\.\s]', '', nit)
    
    return cleaned


def format_colombia_cedula(cedula: str) -> str:
    """
    Formatea cédula colombiana con puntos de miles
    """
    if not validate_colombia_cedula(cedula):
        return cedula  # Retorna sin cambios si no es válido
    
    # Limpiar
    cleaned = re.sub(r'[\.\s]', '', cedula)
    
    # Agregar puntos de miles
    if len(cleaned) <= 3:
        return cleaned
    elif len(cleaned) <= 6:
        return f"{cleaned[:-3]}.{cleaned[-3:]}"
    elif len(cleaned) <= 9:
        return f"{cleaned[:-6]}.{cleaned[-6:-3]}.{cleaned[-3:]}"
    else:
        return f"{cleaned[:-9]}.{cleaned[-9:-6]}.{cleaned[-6:-3]}.{cleaned[-3:]}"