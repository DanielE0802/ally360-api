"""
Script para poblar la base de datos con departamentos y ciudades de Colombia.
"""
import json
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.modules.locations.models import Department, City


# Datos de departamentos y ciudades de Colombia (muestra representativa)
COLOMBIA_LOCATIONS = {
    "departments": [
        {"id": 1, "name": "Amazonas", "code": "91"},
        {"id": 2, "name": "Antioquia", "code": "05"},
        {"id": 3, "name": "Arauca", "code": "81"},
        {"id": 4, "name": "Atlántico", "code": "08"},
        {"id": 5, "name": "Bolívar", "code": "13"},
        {"id": 6, "name": "Boyacá", "code": "15"},
        {"id": 7, "name": "Caldas", "code": "17"},
        {"id": 8, "name": "Caquetá", "code": "18"},
        {"id": 9, "name": "Casanare", "code": "85"},
        {"id": 10, "name": "Cauca", "code": "19"},
        {"id": 11, "name": "Cesar", "code": "20"},
        {"id": 12, "name": "Chocó", "code": "27"},
        {"id": 13, "name": "Córdoba", "code": "23"},
        {"id": 14, "name": "Cundinamarca", "code": "25"},
        {"id": 15, "name": "Guainía", "code": "94"},
        {"id": 16, "name": "Guaviare", "code": "95"},
        {"id": 17, "name": "Huila", "code": "41"},
        {"id": 18, "name": "La Guajira", "code": "44"},
        {"id": 19, "name": "Magdalena", "code": "47"},
        {"id": 20, "name": "Meta", "code": "50"},
        {"id": 21, "name": "Nariño", "code": "52"},
        {"id": 22, "name": "Norte de Santander", "code": "54"},
        {"id": 23, "name": "Putumayo", "code": "86"},
        {"id": 24, "name": "Quindío", "code": "63"},
        {"id": 25, "name": "Risaralda", "code": "66"},
        {"id": 26, "name": "San Andrés y Providencia", "code": "88"},
        {"id": 27, "name": "Santander", "code": "68"},
        {"id": 28, "name": "Sucre", "code": "70"},
        {"id": 29, "name": "Tolima", "code": "73"},
        {"id": 30, "name": "Valle del Cauca", "code": "76"},
        {"id": 31, "name": "Vaupés", "code": "97"},
        {"id": 32, "name": "Vichada", "code": "99"},
        {"id": 33, "name": "Bogotá D.C.", "code": "11"}
    ],
    "cities": [
        # Bogotá D.C.
        {"id": 1, "name": "Bogotá D.C.", "code": "11001", "department_id": 33},
        
        # Antioquia (principales)
        {"id": 2, "name": "Medellín", "code": "05001", "department_id": 2},
        {"id": 3, "name": "Bello", "code": "05088", "department_id": 2},
        {"id": 4, "name": "Envigado", "code": "05266", "department_id": 2},
        {"id": 5, "name": "Itagüí", "code": "05360", "department_id": 2},
        {"id": 6, "name": "Sabaneta", "code": "05631", "department_id": 2},
        {"id": 7, "name": "La Estrella", "code": "05380", "department_id": 2},
        {"id": 8, "name": "Copacabana", "code": "05212", "department_id": 2},
        {"id": 9, "name": "Girardota", "code": "05308", "department_id": 2},
        {"id": 10, "name": "Barbosa", "code": "05079", "department_id": 2},
        
        # Valle del Cauca (principales)
        {"id": 11, "name": "Cali", "code": "76001", "department_id": 30},
        {"id": 12, "name": "Palmira", "code": "76520", "department_id": 30},
        {"id": 13, "name": "Buenaventura", "code": "76109", "department_id": 30},
        {"id": 14, "name": "Tulua", "code": "76834", "department_id": 30},
        {"id": 15, "name": "Cartago", "code": "76147", "department_id": 30},
        {"id": 16, "name": "Buga", "code": "76111", "department_id": 30},
        {"id": 17, "name": "Jamundí", "code": "76364", "department_id": 30},
        {"id": 18, "name": "Yumbo", "code": "76892", "department_id": 30},
        
        # Atlántico (principales)
        {"id": 19, "name": "Barranquilla", "code": "08001", "department_id": 4},
        {"id": 20, "name": "Soledad", "code": "08758", "department_id": 4},
        {"id": 21, "name": "Malambo", "code": "08433", "department_id": 4},
        {"id": 22, "name": "Sabanagrande", "code": "08634", "department_id": 4},
        {"id": 23, "name": "Puerto Colombia", "code": "08573", "department_id": 4},
        
        # Santander (principales)
        {"id": 24, "name": "Bucaramanga", "code": "68001", "department_id": 27},
        {"id": 25, "name": "Floridablanca", "code": "68276", "department_id": 27},
        {"id": 26, "name": "Girón", "code": "68307", "department_id": 27},
        {"id": 27, "name": "Piedecuesta", "code": "68547", "department_id": 27},
        
        # Cundinamarca (principales)
        {"id": 28, "name": "Soacha", "code": "25754", "department_id": 14},
        {"id": 29, "name": "Chía", "code": "25175", "department_id": 14},
        {"id": 30, "name": "Zipaquirá", "code": "25899", "department_id": 14},
        {"id": 31, "name": "Facatativá", "code": "25269", "department_id": 14},
        {"id": 32, "name": "Mosquera", "code": "25473", "department_id": 14},
        {"id": 33, "name": "Madrid", "code": "25426", "department_id": 14},
        {"id": 34, "name": "Funza", "code": "25286", "department_id": 14},
        {"id": 35, "name": "Cajicá", "code": "25126", "department_id": 14},
        
        # Bolívar (principales)
        {"id": 36, "name": "Cartagena", "code": "13001", "department_id": 5},
        {"id": 37, "name": "Magangué", "code": "13430", "department_id": 5},
        {"id": 38, "name": "Turbaco", "code": "13836", "department_id": 5},
        
        # Norte de Santander (principales)
        {"id": 39, "name": "Cúcuta", "code": "54001", "department_id": 22},
        {"id": 40, "name": "Villa del Rosario", "code": "54874", "department_id": 22},
        {"id": 41, "name": "Los Patios", "code": "54405", "department_id": 22},
        
        # Tolima (principales)
        {"id": 42, "name": "Ibagué", "code": "73001", "department_id": 29},
        {"id": 43, "name": "Espinal", "code": "73268", "department_id": 29},
        {"id": 44, "name": "Melgar", "code": "73449", "department_id": 29},
        
        # Risaralda (principales)
        {"id": 45, "name": "Pereira", "code": "66001", "department_id": 25},
        {"id": 46, "name": "Dosquebradas", "code": "66170", "department_id": 25},
        {"id": 47, "name": "Santa Rosa de Cabal", "code": "66682", "department_id": 25},
        
        # Quindío (principales)
        {"id": 48, "name": "Armenia", "code": "63001", "department_id": 24},
        {"id": 49, "name": "Calarcá", "code": "63130", "department_id": 24},
        {"id": 50, "name": "La Tebaida", "code": "63401", "department_id": 24},
        
        # Caldas (principales)
        {"id": 51, "name": "Manizales", "code": "17001", "department_id": 7},
        {"id": 52, "name": "Villamaría", "code": "17873", "department_id": 7},
        {"id": 53, "name": "Chinchiná", "code": "17174", "department_id": 7},
        
        # Huila (principales)
        {"id": 54, "name": "Neiva", "code": "41001", "department_id": 17},
        {"id": 55, "name": "Pitalito", "code": "41551", "department_id": 17},
        {"id": 56, "name": "Garzón", "code": "41298", "department_id": 17},
        
        # Meta (principales)
        {"id": 57, "name": "Villavicencio", "code": "50001", "department_id": 20},
        {"id": 58, "name": "Acacías", "code": "50006", "department_id": 20},
        {"id": 59, "name": "Granada", "code": "50313", "department_id": 20},
        
        # Córdoba (principales)
        {"id": 60, "name": "Montería", "code": "23001", "department_id": 13},
        {"id": 61, "name": "Cereté", "code": "23162", "department_id": 13},
        {"id": 62, "name": "Lorica", "code": "23417", "department_id": 13},
        
        # Magdalena (principales)
        {"id": 63, "name": "Santa Marta", "code": "47001", "department_id": 19},
        {"id": 64, "name": "Ciénaga", "code": "47189", "department_id": 19},
        {"id": 65, "name": "Fundación", "code": "47288", "department_id": 19},
        
        # Cesar (principales)
        {"id": 66, "name": "Valledupar", "code": "20001", "department_id": 11},
        {"id": 67, "name": "Aguachica", "code": "20011", "department_id": 11},
        {"id": 68, "name": "Codazzi", "code": "20178", "department_id": 11},
        
        # La Guajira (principales)
        {"id": 69, "name": "Riohacha", "code": "44001", "department_id": 18},
        {"id": 70, "name": "Maicao", "code": "44430", "department_id": 18},
        {"id": 71, "name": "San Juan del Cesar", "code": "44650", "department_id": 18},
        
        # Sucre (principales)
        {"id": 72, "name": "Sincelejo", "code": "70001", "department_id": 28},
        {"id": 73, "name": "Corozal", "code": "70215", "department_id": 28},
        {"id": 74, "name": "Sampués", "code": "70678", "department_id": 28},
        
        # Nariño (principales)
        {"id": 75, "name": "Pasto", "code": "52001", "department_id": 21},
        {"id": 76, "name": "Tumaco", "code": "52835", "department_id": 21},
        {"id": 77, "name": "Ipiales", "code": "52356", "department_id": 21},
        
        # Cauca (principales)
        {"id": 78, "name": "Popayán", "code": "19001", "department_id": 10},
        {"id": 79, "name": "Santander de Quilichao", "code": "19698", "department_id": 10},
        {"id": 80, "name": "Puerto Tejada", "code": "19573", "department_id": 10},
        
        # Boyacá (principales)
        {"id": 81, "name": "Tunja", "code": "15001", "department_id": 6},
        {"id": 82, "name": "Duitama", "code": "15238", "department_id": 6},
        {"id": 83, "name": "Sogamoso", "code": "15759", "department_id": 6},
        {"id": 84, "name": "Chiquinquirá", "code": "15176", "department_id": 6},
        
        # Casanare (principales)
        {"id": 85, "name": "Yopal", "code": "85001", "department_id": 9},
        {"id": 86, "name": "Aguazul", "code": "85010", "department_id": 9},
        {"id": 87, "name": "Tauramena", "code": "85410", "department_id": 9},
        
        # Arauca (principales)
        {"id": 88, "name": "Arauca", "code": "81001", "department_id": 3},
        {"id": 89, "name": "Tame", "code": "81794", "department_id": 3},
        {"id": 90, "name": "Saravena", "code": "81736", "department_id": 3},
        
        # Putumayo (principales)
        {"id": 91, "name": "Mocoa", "code": "86001", "department_id": 23},
        {"id": 92, "name": "Puerto Asís", "code": "86568", "department_id": 23},
        {"id": 93, "name": "Orito", "code": "86320", "department_id": 23},
        
        # Caquetá (principales)
        {"id": 94, "name": "Florencia", "code": "18001", "department_id": 8},
        {"id": 95, "name": "San Vicente del Caguán", "code": "18753", "department_id": 8},
        {"id": 96, "name": "Puerto Rico", "code": "18592", "department_id": 8},
        
        # Chocó (principales)
        {"id": 97, "name": "Quibdó", "code": "27001", "department_id": 12},
        {"id": 98, "name": "Istmina", "code": "27361", "department_id": 12},
        {"id": 99, "name": "Condoto", "code": "27205", "department_id": 12},
        
        # San Andrés y Providencia
        {"id": 100, "name": "San Andrés", "code": "88001", "department_id": 26},
        {"id": 101, "name": "Providencia", "code": "88564", "department_id": 26},
        
        # Amazonas (principales)
        {"id": 102, "name": "Leticia", "code": "91001", "department_id": 1},
        {"id": 103, "name": "Puerto Nariño", "code": "91540", "department_id": 1},
        
        # Guainía
        {"id": 104, "name": "Puerto Inírida", "code": "94001", "department_id": 15},
        
        # Guaviare (principales)
        {"id": 105, "name": "San José del Guaviare", "code": "95001", "department_id": 16},
        {"id": 106, "name": "Calamar", "code": "95015", "department_id": 16},
        
        # Vaupés
        {"id": 107, "name": "Mitú", "code": "97001", "department_id": 31},
        
        # Vichada (principales)
        {"id": 108, "name": "Puerto Carreño", "code": "99001", "department_id": 32},
        {"id": 109, "name": "La Primavera", "code": "99524", "department_id": 32}
    ]
}


def populate_locations(db: Session):
    """Poblar la base de datos con departamentos y ciudades de Colombia."""
    
    # Verificar si ya existen datos
    existing_departments = db.query(Department).count()
    if existing_departments > 0:
        print(f"Ya existen {existing_departments} departamentos en la base de datos")
        return
    
    print("Poblando base de datos con departamentos y ciudades de Colombia...")
    
    # Insertar departamentos
    departments_created = 0
    for dept_data in COLOMBIA_LOCATIONS["departments"]:
        department = Department(**dept_data)
        db.add(department)
        departments_created += 1
    
    # Hacer commit de departamentos primero
    db.commit()
    print(f"✅ {departments_created} departamentos creados")
    
    # Insertar ciudades
    cities_created = 0
    for city_data in COLOMBIA_LOCATIONS["cities"]:
        city = City(**city_data)
        db.add(city)
        cities_created += 1
    
    # Hacer commit de ciudades
    db.commit()
    print(f"✅ {cities_created} ciudades creadas")
    
    print("🎉 Base de datos poblada exitosamente con ubicaciones de Colombia")


if __name__ == "__main__":
    # Ejecutar el script directamente
    db = next(get_db())
    try:
        populate_locations(db)
    finally:
        db.close()