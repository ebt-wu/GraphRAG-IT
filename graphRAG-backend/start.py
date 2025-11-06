from graph_manager import GraphManager
from rag_system import GraphRAGSystem
import os
from dotenv import load_dotenv

load_dotenv()

print("\n" + "="*60)
print("GRAPHRAG INIT DATABASE POPULATION")
print("="*60)

graph = GraphManager(
    uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    user=os.getenv("NEO4J_USER", "neo4j"),
    password=os.getenv("NEO4J_PASSWORD", "password")
)

print("\nLoading data...")
graph.load_all_data("./csv_data")

print("Creating embeddings...")
graph.create_relationship_embeddings()

rag = GraphRAGSystem(graph, os.getenv("OPENAI_API_KEY"))

test_queries = [
    # Simple queries
    "Which servers run Ubuntu?",
    
    # Vague/complex queries (will be refined)
    "Which country runs on which OS?",
    "What does London have?",
    "What OS is in each location?",
    
    # Multi-hop queries
    "What OS runs in New York?",
    "Which apps are in London?",
]

print("\n" + "="*60)
print("TESTING GRAPHRAG")
print("="*60)

for query in test_queries:
    print(f"\n{'='*60}")
    rag.answer_question(query)

graph.close()
print("Done")
