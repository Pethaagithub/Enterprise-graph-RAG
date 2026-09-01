"""
Runs a set of SPARQL queries against the O2C knowledge graph to answer
real business questions -- the kind any enterprise AI agent would need to ground
correctly rather than hallucinate.
"""
from rdflib import Graph

g = Graph()
g.parse("/home/claude/enterprise-graph-rag/data/business_graph.ttl", format="turtle")

QUERIES = {
    "Q1: Which customers have overdue invoices, and how much do they owe?": """
        PREFIX o2c: <http://example.org/o2c#>
        SELECT ?customerName (SUM(?amount) AS ?totalOverdue)
        WHERE {
            ?customer o2c:customerName ?customerName ;
                      o2c:places ?order .
            ?order o2c:generatesInvoice ?invoice .
            ?invoice o2c:invoiceStatus "Overdue" ;
                     o2c:invoiceAmount ?amount .
        }
        GROUP BY ?customerName
        ORDER BY DESC(?totalOverdue)
    """,

    "Q2: What is total revenue (paid invoices only) by customer segment?": """
        PREFIX o2c: <http://example.org/o2c#>
        SELECT ?segment (SUM(?amount) AS ?revenue)
        WHERE {
            ?customer o2c:customerSegment ?segment ;
                      o2c:places ?order .
            ?order o2c:generatesInvoice ?invoice .
            ?invoice o2c:invoiceStatus "Paid" ;
                     o2c:invoiceAmount ?amount .
        }
        GROUP BY ?segment
        ORDER BY DESC(?revenue)
    """,

    "Q3: Which products appear most often in Enterprise-segment orders?": """
        PREFIX o2c: <http://example.org/o2c#>
        SELECT ?productName (COUNT(?line) AS ?timesOrdered)
        WHERE {
            ?customer o2c:customerSegment "Enterprise" ;
                      o2c:places ?order .
            ?order o2c:containsLineItem ?line .
            ?line o2c:forProduct ?product .
            ?product o2c:productName ?productName .
        }
        GROUP BY ?productName
        ORDER BY DESC(?timesOrdered)
    """,

    "Q4: Orders that are Completed but whose invoice is still Unpaid or Overdue "
    "(a real O2C risk pattern -- delivered goods, no cash collected)": """
        PREFIX o2c: <http://example.org/o2c#>
        SELECT ?orderId ?customerName ?invoiceStatus ?amount
        WHERE {
            ?customer o2c:customerName ?customerName ;
                      o2c:places ?order .
            ?order o2c:orderId ?orderId ;
                   o2c:orderStatus "Completed" ;
                   o2c:generatesInvoice ?invoice .
            ?invoice o2c:invoiceStatus ?invoiceStatus ;
                     o2c:invoiceAmount ?amount .
            FILTER(?invoiceStatus IN ("Unpaid", "Overdue"))
        }
        ORDER BY DESC(?amount)
    """,
}

if __name__ == "__main__":
    for label, q in QUERIES.items():
        print(f"\n{'='*90}\n{label}\n{'='*90}")
        for row in g.query(q):
            print(row.asdict())
