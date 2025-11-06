from flask import Flask, request, jsonify
from flask_cors import CORS
from graph_manager import GraphManager
from rag_system import GraphRAGSystem
import os
from dotenv import load_dotenv
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize graph manager
graph_manager = GraphManager(
    uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    user=os.getenv("NEO4J_USER", "neo4j"),
    password=os.getenv("NEO4J_PASSWORD", "password")
)

# Initialize RAG system
rag_system = GraphRAGSystem(
    graph_manager,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

@app.route("/api/initialize", methods=["POST"])
def initialize_graph():
    """Initialize graph with CSV data"""
    try:
        csv_dir = request.json.get("csv_directory", "./csv_data")
        graph_manager.load_all_data(csv_dir)
        return jsonify({"status": "success", "message": "Graph initialized with data"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/chat", methods=["POST"])
def chat():
    """Chat endpoint for asking questions"""
    try:
        
        user_query = request.json.get("message")
        logger.info(f"User Query: {user_query}")
        print(f"Received query: {user_query}")
        answer = rag_system.answer_question(user_query)
        return jsonify({"status": "success", "answer": answer})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
