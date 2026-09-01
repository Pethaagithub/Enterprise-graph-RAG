"""
GraphRAG over the O2C knowledge graph.

This is the core idea behind grounded enterprise AI agents: instead of an LLM
answering from surface-level text patterns (or hallucinating numbers), we
retrieve a grounded, structured subgraph via SPARQL and hand THAT to the LLM
as context. The LLM's job shrinks to "summarize these verified facts in
natural language" instead of "recall or guess an answer."

Retrieval strategy here is intentionally simple (intent -> template SPARQL)
to keep the demo self-contained and auditable. In production this routing
step is typically itself an LLM call (text-to-SPARQL), or a hybrid of
embedding-based entity linking + template retrieval for guardrails on
high-stakes numeric queries -- which is the trade-off worth discussing in
an interview: free-form text-to-SPARQL is more flexible but less reliable
for numeric/financial grounding than constrained templates.
"""
import os
import re
from rdflib import Graph

GRAPH_PATH = "/home/claude/enterprise-graph-rag/data/business_graph.ttl"

TEMPLATES = {
    "overdue": """
        PREFIX o2c: <http://example.org/o2c#>
        SELECT ?customerName ?orderId ?amount ?dueDate
        WHERE {
            ?customer o2c:customerName ?customerName ; o2c:places ?order .
            ?order o2c:orderId ?orderId ; o2c:generatesInvoice ?invoice .
            ?invoice o2c:invoiceStatus "Overdue" ;
                     o2c:invoiceAmount ?amount ;
                     o2c:invoiceDueDate ?dueDate .
        } ORDER BY DESC(?amount)
    """,
    "revenue_by_segment": """
        PREFIX o2c: <http://example.org/o2c#>
        SELECT ?segment (SUM(?amount) AS ?revenue)
        WHERE {
            ?customer o2c:customerSegment ?segment ; o2c:places ?order .
            ?order o2c:generatesInvoice ?invoice .
            ?invoice o2c:invoiceStatus "Paid" ; o2c:invoiceAmount ?amount .
        } GROUP BY ?segment ORDER BY DESC(?revenue)
    """,
    "customer_orders": """
        PREFIX o2c: <http://example.org/o2c#>
        SELECT ?orderId ?orderStatus ?orderDate
        WHERE {
            ?customer o2c:customerName ?name ; o2c:places ?order .
            ?order o2c:orderId ?orderId ; o2c:orderStatus ?orderStatus ; o2c:orderDate ?orderDate .
            FILTER(CONTAINS(LCASE(?name), LCASE("%(customer)s")))
        } ORDER BY DESC(?orderDate)
    """,
}


def classify_intent(question: str) -> str:
    """Tiny keyword-based intent router. Swap for an LLM function-call /
    embedding classifier in production for broader coverage."""
    q = question.lower()
    if "overdue" in q or "owe" in q or "unpaid" in q:
        return "overdue"
    if "revenue" in q or "segment" in q:
        return "revenue_by_segment"
    return "customer_orders"


def extract_customer_name(question: str, graph: Graph) -> str:
    """Entity linking against the graph itself, not free-text NER.

    A naive 'grab capitalized words' regex fails here -- it matches leading
    words like 'What' just as happily as an actual company name. Since every
    valid customer name already lives in the graph as a :customerName
    literal, the graph itself is a far better source of truth than
    regex/NER: extract every known customer name from the graph and keep the
    longest one that appears (case-insensitively) as a substring of the
    question. This is a small-scale version of the entity-linking step a
    real GraphRAG system needs before it can retrieve reliably.
    """
    known_names = [str(row.n) for row in graph.query(
        "PREFIX o2c: <http://example.org/o2c#> SELECT ?n WHERE { ?c o2c:customerName ?n }"
    )]
    ql = question.lower()
    candidates = [n for n in known_names if n.lower() in ql]
    return max(candidates, key=len) if candidates else ""


def retrieve(question: str, graph: Graph):
    intent = classify_intent(question)
    query = TEMPLATES[intent]
    if intent == "customer_orders":
        query = query % {"customer": extract_customer_name(question, graph) or "___no_match___"}
    rows = [dict(r.asdict()) for r in graph.query(query)]
    return intent, rows


def rows_to_context(intent: str, rows: list) -> str:
    """Turn retrieved graph rows into a compact, LLM-readable fact block."""
    if not rows:
        return "No matching records were found in the knowledge graph."
    lines = [f"Retrieved {len(rows)} record(s) from the Order-to-Cash knowledge graph (intent: {intent}):"]
    for r in rows:
        clean = {k: str(v) for k, v in r.items()}
        lines.append(" - " + ", ".join(f"{k}={v}" for k, v in clean.items()))
    return "\n".join(lines)


def answer(question: str, call_llm=True) -> str:
    g = Graph()
    g.parse(GRAPH_PATH, format="turtle")
    intent, rows = retrieve(question, g)
    context = rows_to_context(intent, rows)

    prompt = f"""You are an enterprise assistant answering questions about Order-to-Cash data.
Answer ONLY using the facts below. If the facts don't fully answer the question, say so explicitly.
Never invent numbers that aren't in the facts.

FACTS:
{context}

QUESTION: {question}

ANSWER:"""

    if call_llm and os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text
    else:
        # No API key in this environment -- return the grounded context
        # directly so the retrieval half of the pipeline is still verifiable.
        return f"[LLM call skipped -- no ANTHROPIC_API_KEY set]\n\nGrounding context that WOULD be sent to the LLM:\n{context}"


if __name__ == "__main__":
    demo_questions = [
        "Which customers have overdue invoices and how much do they owe?",
        "What is our revenue by customer segment?",
        "What orders has Doyle Ltd placed?",
    ]
    for q in demo_questions:
        print(f"\nQ: {q}\n{'-'*80}")
        print(answer(q))
