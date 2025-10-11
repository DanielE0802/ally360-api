"""
Seed script: Populate a demo supermarket tenant with realistic data.

What it creates:
- Company (tenant) + owner user (active + verified) with credentials.
- PDVs (2): Principal and Sucursal Norte.
- Sellers (3): para POS/reportes.
- Brands/Categories typical for supermarkets.
- Taxes: IVA 19%, IVA 5% (global), y exentos por categoría.
- Products: >= N (default 1200) con SKU únicos, precios y stock inicial en ambos PDVs.
- Contacts: clientes (~150) y proveedores (~40).
- Bills (compras): aumentan stock con movimientos IN.
- Invoices (ventas): afectan inventario con movimientos OUT; mezcla de DRAFT/OPEN/PAID/VOID.

Run inside the API container to use 'postgres' host and project PYTHONPATH:
    docker compose exec api python scripts/seed_supermarket_data.py \
        --company-name "Super Demo Market" \
        --email admin@superdemo.com \
        --password SuperDemo!2025 \
        --products 1200 --invoices 900 --bills 450

Note: This is intended for development environments only.
"""

# Add project root (/code) to sys.path so `app.*` imports work even if CWD changes
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import random
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal
 

from app.database.database import SessionLocal
from app.modules.auth.models import User, Profile, UserCompany
from app.modules.auth.utils import hash_password
from app.modules.company.models import Company
from app.modules.pdv.models import PDV
from app.modules.pos.models import Seller
from app.modules.brands.models import Brand
from app.modules.categories.models import Category
from app.modules.products.models import Product, Stock, ProductTax, Tax, TaxType
from app.modules.contacts.models import Contact
from app.modules.locations.models import Department, City  # Added locations models
from app.modules.invoices.service import InvoiceService
from app.modules.invoices.schemas import InvoiceCreate, InvoiceLineItemCreate, InvoiceStatus as InvoiceStatusSchema
from app.modules.invoices.models import PaymentMethod as InvoicePaymentMethod
from app.modules.bills.service import BillService
from app.modules.bills.schemas import BillCreate, BillLineItemCreate, BillStatus as BillStatusSchema


def pick(seq):
    return random.choice(seq)


def create_company(db, name: str):
    existing = db.query(Company).filter(Company.name == name).first()
    if existing:
        return existing
    company = Company(
        name=name,
        description="Empresa demo de supermercado",
        address="Cra 1 # 2-34, Bogotá",
        phone_number=f"300{random.randint(1000000, 9999999)}",
        nit=str(random.randint(900000000, 999999999)),
        social_reason=name,
        is_active=True,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def create_owner_user(db, email: str, password: str, first_name="Admin", last_name="Demo"):
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user
    profile = Profile(first_name=first_name, last_name=last_name)
    db.add(profile)
    db.flush()
    user = User(
        email=email,
        password=hash_password(password),
        is_active=True,
        email_verified=True,
        email_verified_at=datetime.now(timezone.utc),
        profile_id=profile.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def link_user_company(db, user_id, company_id, role="owner"):
    rel = db.query(UserCompany).filter(
        UserCompany.user_id == user_id,
        UserCompany.company_id == company_id,
    ).first()
    if rel:
        return rel
    rel = UserCompany(user_id=user_id, company_id=company_id, role=role, is_active=True)
    db.add(rel)
    db.commit()
    return rel


def create_pdvs(db, tenant_id):
    pdvs = []
    names = [("Principal", True), ("Sucursal Norte", False)]
    for name, is_main in names:
        existing = db.query(PDV).filter(PDV.tenant_id == tenant_id, PDV.name == name).first()
        if existing:
            pdvs.append(existing)
            continue
        pdv = PDV(name=name, address=f"{name} - Dirección", phone_number="6011234567", is_main=is_main, tenant_id=tenant_id)
        db.add(pdv)
        db.flush()
        pdvs.append(pdv)
    db.commit()
    return pdvs


def create_sellers(db, tenant_id):
    seller_names = ["Juan Pérez", "María López", "Carlos Gómez"]
    sellers = []
    for n in seller_names:
        existing = db.query(Seller).filter(Seller.tenant_id == tenant_id, Seller.name == n).first()
        if existing:
            sellers.append(existing)
            continue
        s = Seller(name=n, email=None, tenant_id=tenant_id, is_active=True)
        db.add(s)
        db.flush()
        sellers.append(s)
    db.commit()
    return sellers


def create_brands_categories(db, tenant_id):
    brands = [
        "Alpina", "Coca-Cola", "Colanta", "Bimbo", "Postobón", "Ramo", "Zenú", "Nutresa", "Doria", "Noel",
    ]
    categories = [
        "Bebidas", "Lácteos", "Abarrotes", "Aseo", "Panadería", "Snacks", "Frutas", "Verduras", "Carnes", "Congelados",
    ]
    brand_objs = []
    for b in brands:
        obj = db.query(Brand).filter(Brand.tenant_id == tenant_id, Brand.name == b).first()
        if not obj:
            obj = Brand(name=b, tenant_id=tenant_id)
            db.add(obj)
            db.flush()
        brand_objs.append(obj)
    cat_objs = []
    for c in categories:
        obj = db.query(Category).filter(Category.tenant_id == tenant_id, Category.name == c).first()
        if not obj:
            obj = Category(name=c, tenant_id=tenant_id)
            db.add(obj)
            db.flush()
        cat_objs.append(obj)
    db.commit()
    return brand_objs, cat_objs


def create_taxes(db):
    # Global taxes (company_id = NULL) as DIAN defaults
    iva19 = db.query(Tax).filter(Tax.name == "IVA 19%", Tax.company_id.is_(None)).first()
    if not iva19:
        iva19 = Tax(name="IVA 19%", code="01", rate=Decimal("0.19"), type=TaxType.VAT, company_id=None, is_editable=False)
        db.add(iva19)
    iva5 = db.query(Tax).filter(Tax.name == "IVA 5%", Tax.company_id.is_(None)).first()
    if not iva5:
        iva5 = Tax(name="IVA 5%", code="01", rate=Decimal("0.05"), type=TaxType.VAT, company_id=None, is_editable=False)
        db.add(iva5)
    db.commit()
    return iva19, iva5


def generate_sku(category: str, brand: str, idx: int) -> str:
    c = ''.join([ch for ch in category.upper() if ch.isalpha()])[:3]
    b = ''.join([ch for ch in brand.upper() if ch.isalpha()])[:3]
    return f"{c}-{b}-{idx:04d}"


def create_products(db, tenant_id, brands, categories, product_count=1200, pdvs=None, taxes=None):
    iva19, iva5 = taxes
    products = []
    for i in range(product_count):
        brand = pick(brands)
        category = pick(categories)
        base_price = Decimal(random.randint(1000, 50000)) / Decimal(100)  # 10.00 - 500.00
        margin = Decimal(random.randint(10, 35)) / Decimal(100)  # 10% - 35%
        sale_price = (base_price * (Decimal(1) + margin)).quantize(Decimal('0.01'))
        sku = generate_sku(category.name, brand.name, i)
        name = f"{category.name} {brand.name} {random.randint(1, 999)}g"
        # Skip if SKU already exists for this tenant (idempotent re-run)
        existing = db.query(Product).filter(Product.tenant_id == tenant_id, Product.sku == sku).first()
        if existing:
            products.append(existing)
            if (i + 1) % 200 == 0:
                db.commit()
            continue

        p = Product(
            name=name,
            sku=sku,
            description=f"{category.name} de marca {brand.name}",
            bar_code=str(random.randint(7700000000000, 7799999999999)),
            is_configurable=False,
            is_active=True,
            price_sale=sale_price,
            price_base=base_price,
            sell_in_negative=False,
            brand_id=brand.id,
            category_id=category.id,
            tenant_id=tenant_id
        )
        db.add(p)
        db.flush()

        # Assign taxes: fruits/vegetables often 0% or 5%; others 19%
        if category.name in ("Frutas", "Verduras"):
            # 5% for some, else no tax
            if random.random() < 0.5:
                db.add(ProductTax(product_id=p.id, tax_id=iva5.id, tenant_id=tenant_id))
        else:
            db.add(ProductTax(product_id=p.id, tax_id=iva19.id, tenant_id=tenant_id))

        # Initial stock per PDV
        for pdv in (pdvs or []):
            qty = random.randint(10, 200)
            db.add(Stock(product_id=p.id, pdv_id=pdv.id, tenant_id=tenant_id, quantity=qty, min_quantity=random.randint(2, 15)))

        products.append(p)

        if (i + 1) % 200 == 0:
            db.commit()
    db.commit()
    return products


def create_contacts(db, tenant_id, created_by_user_id, clients_count=150, providers_count=40):
    clients = []
    providers = []
    # Simple name pools
    first_names = ["Juan", "María", "Carlos", "Ana", "Luis", "Laura", "Diego", "Paula", "Andrés", "Sofía"]
    last_names = ["Pérez", "García", "López", "Gómez", "Rodríguez", "Martínez", "Hernández", "Torres", "Ramírez", "Sánchez"]

    for i in range(clients_count):
        name = f"{pick(first_names)} {pick(last_names)}"
        email = f"cliente{i}@mail.com"
        c = Contact(
            name=name,
            type=["client"],
            email=email,
            id_type="CC",
            id_number=str(10000000 + i),
            payment_terms_days=random.choice([0, 15, 30]),
            is_active=True,
            tenant_id=tenant_id,
            created_by=created_by_user_id,
        )
        db.add(c)
        clients.append(c)
        if (i + 1) % 100 == 0:
            db.commit()
    db.commit()

    for i in range(providers_count):
        name = f"Proveedor {i+1}"
        email = f"proveedor{i}@mail.com"
        p = Contact(
            name=name,
            type=["provider"],
            email=email,
            id_type="NIT",
            id_number=str(900000000 + i),
            dv="1",
            is_active=True,
            tenant_id=tenant_id,
            created_by=created_by_user_id,
        )
        db.add(p)
        providers.append(p)
    db.commit()
    return clients, providers


def create_bills(db, tenant_id, pdvs, providers, products, bills_count, user_id):
    service = BillService(db)
    created = 0
    for i in range(bills_count):
        supplier = pick(providers)
        pdv = pick(pdvs)
        items = []
        for _ in range(random.randint(3, 7)):
            prod = pick(products)
            qty = Decimal(random.randint(5, 50))
            price = prod.price_base
            items.append(BillLineItemCreate(product_id=prod.id, quantity=qty, unit_price=price))
        status = BillStatusSchema.OPEN if random.random() < 0.85 else BillStatusSchema.DRAFT
        bill_in = BillCreate(
            supplier_id=supplier.id,
            pdv_id=pdv.id,
            number=f"BILL-{date.today().strftime('%Y%m%d')}-{i:04d}",
            issue_date=date.today() - timedelta(days=random.randint(1, 60)),
            due_date=date.today() + timedelta(days=random.randint(0, 30)),
            currency="COP",
            notes=None,
            status=status,
            line_items=items
        )
        # created_by: pass via service param user_id; use owner later; for seed, use random UUID
        try:
            service.create_bill(bill_in, tenant_id, user_id=user_id)
            created += 1
        except Exception:
            db.rollback()
            continue
        if created % 100 == 0:
            print(f"  Bills created: {created}")
    return created


def create_invoices(db, tenant_id, pdvs, sellers, clients, products, invoices_count, user_id):
    service = InvoiceService(db)
    created = 0
    for i in range(invoices_count):
        customer = pick(clients)
        pdv = pick(pdvs)
        items = []
        for _ in range(random.randint(1, 6)):
            prod = pick(products)
            qty = Decimal(random.randint(1, 5))
            price = prod.price_sale
            items.append(InvoiceLineItemCreate(product_id=prod.id, quantity=qty, unit_price=price))
        # Status mix: OPEN, DRAFT, later we can add payments to mark as PAID
        status = InvoiceStatusSchema.OPEN if random.random() < 0.7 else InvoiceStatusSchema.DRAFT
        inv_in = InvoiceCreate(
            pdv_id=pdv.id,
            customer_id=customer.id,
            status=status,
            issue_date=date.today() - timedelta(days=random.randint(0, 30)),
            due_date=date.today() + timedelta(days=random.randint(0, 15)),
            notes=None,
            items=items
        )
        try:
            invoice = service.create_invoice(inv_in, tenant_id, user_id=user_id)
            # Mark some as PAID by adding a payment covering total
            if status == InvoiceStatusSchema.OPEN and random.random() < 0.4:
                from app.modules.invoices.schemas import PaymentCreate
                payment = PaymentCreate(
                    amount=invoice.total_amount,
                    method=InvoicePaymentMethod.CASH.value,
                    reference=f"PAY-{i:04d}",
                    payment_date=date.today(),
                    notes=None
                )
                service.add_payment(invoice.id, payment, tenant_id, user_id=user_id)
            created += 1
        except Exception:
            db.rollback()
            continue
        if created % 150 == 0:
            print(f"  Invoices created: {created}")
    return created


def main():
    parser = argparse.ArgumentParser(description="Seed supermarket demo data")
    parser.add_argument("--company-name", default="Super Demo Market")
    parser.add_argument("--email", default="admin@superdemo.com")
    parser.add_argument("--password", default="SuperDemo!2025")
    parser.add_argument("--products", type=int, default=1200)
    parser.add_argument("--invoices", type=int, default=900)
    parser.add_argument("--bills", type=int, default=450)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        company = create_company(db, args.company_name)
        user = create_owner_user(db, args.email, args.password)
        link_user_company(db, user.id, company.id, role="owner")

        pdvs = create_pdvs(db, company.id)
        sellers = create_sellers(db, company.id)
        brands, categories = create_brands_categories(db, company.id)
        taxes = create_taxes(db)

        print("Creating products...")
        products = create_products(db, company.id, brands, categories, product_count=args.products, pdvs=pdvs, taxes=taxes)
        print(f"Products created: {len(products)}")

        print("Creating contacts (clients/providers)...")
        clients, providers = create_contacts(db, company.id, user.id)
        print(f"Clients: {len(clients)}, Providers: {len(providers)}")

        print("Creating purchase bills (increase stock)...")
        bills_created = create_bills(db, company.id, pdvs, providers, products, args.bills, user.id)
        print(f"Bills created: {bills_created}")

        print("Creating sales invoices (affect inventory)...")
        invoices_created = create_invoices(db, company.id, pdvs, sellers, clients, products, args.invoices, user.id)
        print(f"Invoices created: {invoices_created}")

        print("\nSeed completed.")
        print("Login credentials:")
        print(f"  Email:    {args.email}")
        print(f"  Password: {args.password}")
        print("Company:")
        print(f"  Name:     {company.name}")
        print(f"  Company ID (tenant_id): {company.id}")
        print("Headers for API requests:")
        print(f"  X-Company-ID: {company.id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
