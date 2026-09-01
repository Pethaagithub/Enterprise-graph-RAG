"""
Generates a synthetic Order-to-Cash knowledge graph that conforms to
ontology/o2c_ontology.ttl, and serializes it as Turtle (RDF).

This simulates what an ETL/harmonization pipeline (from an ERP or CRM system) would produce when
mapping SD (Sales & Distribution) and FI (Finance) tables into a unified
semantic layer.
"""
import random
from datetime import date, timedelta
from faker import Faker
from rdflib import Graph, Namespace, Literal, RDF, XSD

fake = Faker()
random.seed(42)
Faker.seed(42)

O2C = Namespace("http://example.org/o2c#")
DATA = Namespace("http://example.org/o2c/data#")

PRODUCTS = [
    ("Widget-X", "Hardware"), ("Widget-Y", "Hardware"),
    ("CloudSuite-Basic", "Software"), ("CloudSuite-Pro", "Software"),
    ("Support-Contract-Gold", "Service"), ("Support-Contract-Silver", "Service"),
    ("Sensor-Module-A", "IoT"), ("Sensor-Module-B", "IoT"),
]
SEGMENTS = ["Enterprise", "Mid-Market", "SMB"]
COUNTRIES = ["Germany", "USA", "India", "Brazil", "Japan"]
PAYMENT_METHODS = ["Bank Transfer", "Credit Card", "Direct Debit"]


def build_graph(n_customers=12, max_orders_per_customer=4):
    g = Graph()
    g.bind("o2c", O2C)
    g.bind("data", DATA)

    products = []
    for i, (name, category) in enumerate(PRODUCTS):
        prod_uri = DATA[f"product_{i}"]
        g.add((prod_uri, RDF.type, O2C.Product))
        g.add((prod_uri, O2C.productName, Literal(name)))
        g.add((prod_uri, O2C.productCategory, Literal(category)))
        products.append((prod_uri, name))

    order_counter, invoice_counter, payment_counter, delivery_counter = 1, 1, 1, 1

    for c in range(n_customers):
        cust_uri = DATA[f"customer_{c}"]
        g.add((cust_uri, RDF.type, O2C.Customer))
        g.add((cust_uri, O2C.customerName, Literal(fake.company())))
        g.add((cust_uri, O2C.customerSegment, Literal(random.choice(SEGMENTS))))
        g.add((cust_uri, O2C.customerCountry, Literal(random.choice(COUNTRIES))))

        for _ in range(random.randint(1, max_orders_per_customer)):
            order_uri = DATA[f"order_{order_counter}"]
            order_id = f"SO-{1000 + order_counter}"
            order_date = date(2026, 1, 1) + timedelta(days=random.randint(0, 230))
            status = random.choices(
                ["Completed", "In Fulfillment", "Backordered"], weights=[0.7, 0.2, 0.1]
            )[0]

            g.add((cust_uri, O2C.places, order_uri))
            g.add((order_uri, RDF.type, O2C.SalesOrder))
            g.add((order_uri, O2C.orderId, Literal(order_id)))
            g.add((order_uri, O2C.orderDate, Literal(order_date, datatype=XSD.date)))
            g.add((order_uri, O2C.orderStatus, Literal(status)))

            order_total = 0.0
            for _ in range(random.randint(1, 3)):
                line_uri = DATA[f"line_{order_counter}_{random.randint(1000,9999)}"]
                prod_uri, prod_name = random.choice(products)
                qty = random.randint(1, 20)
                unit_price = round(random.uniform(50, 2000), 2)
                order_total += qty * unit_price

                g.add((order_uri, O2C.containsLineItem, line_uri))
                g.add((line_uri, RDF.type, O2C.OrderLineItem))
                g.add((line_uri, O2C.forProduct, prod_uri))
                g.add((line_uri, O2C.quantity, Literal(qty, datatype=XSD.integer)))
                g.add((line_uri, O2C.unitPrice, Literal(unit_price, datatype=XSD.decimal)))

            # Invoice (most, not all, orders have been invoiced)
            if status != "Backordered":
                invoice_uri = DATA[f"invoice_{invoice_counter}"]
                invoice_id = f"INV-{5000 + invoice_counter}"
                due_date = order_date + timedelta(days=30)
                invoice_status = random.choices(
                    ["Paid", "Unpaid", "Overdue"], weights=[0.55, 0.25, 0.20]
                )[0]

                g.add((order_uri, O2C.generatesInvoice, invoice_uri))
                g.add((invoice_uri, RDF.type, O2C.Invoice))
                g.add((invoice_uri, O2C.invoiceId, Literal(invoice_id)))
                g.add((invoice_uri, O2C.invoiceAmount, Literal(round(order_total, 2), datatype=XSD.decimal)))
                g.add((invoice_uri, O2C.invoiceDueDate, Literal(due_date, datatype=XSD.date)))
                g.add((invoice_uri, O2C.invoiceStatus, Literal(invoice_status)))
                invoice_counter += 1

                if invoice_status == "Paid":
                    payment_uri = DATA[f"payment_{payment_counter}"]
                    pay_date = due_date - timedelta(days=random.randint(0, 15))
                    g.add((invoice_uri, O2C.settledByPayment, payment_uri))
                    g.add((payment_uri, RDF.type, O2C.Payment))
                    g.add((payment_uri, O2C.paymentAmount, Literal(round(order_total, 2), datatype=XSD.decimal)))
                    g.add((payment_uri, O2C.paymentDate, Literal(pay_date, datatype=XSD.date)))
                    g.add((payment_uri, O2C.paymentMethod, Literal(random.choice(PAYMENT_METHODS))))
                    payment_counter += 1

            # Delivery
            if status in ("Completed", "In Fulfillment"):
                delivery_uri = DATA[f"delivery_{delivery_counter}"]
                deliv_status = "Delivered" if status == "Completed" else "In Transit"
                g.add((order_uri, O2C.fulfilledByDelivery, delivery_uri))
                g.add((delivery_uri, RDF.type, O2C.Delivery))
                g.add((delivery_uri, O2C.deliveryDate, Literal(order_date + timedelta(days=random.randint(2, 10)), datatype=XSD.date)))
                g.add((delivery_uri, O2C.deliveryStatus, Literal(deliv_status)))
                delivery_counter += 1

            order_counter += 1

    return g


if __name__ == "__main__":
    g = build_graph()
    out_path = "/home/claude/enterprise-graph-rag/data/business_graph.ttl"
    g.serialize(destination=out_path, format="turtle")
    print(f"Generated knowledge graph with {len(g)} triples -> {out_path}")
