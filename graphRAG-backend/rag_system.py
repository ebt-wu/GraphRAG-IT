from openai import OpenAI
from graph_manager import GraphManager


class GraphRAGSystem:
    def __init__(self, graph_manager, openai_api_key):
        """Initialize RAG system"""
        self.graph = graph_manager
        self.client = OpenAI(api_key=openai_api_key)
    
    def format_hybrid_context(self, search_results, refined_query=None):
        """Format hybrid search results for LLM"""
        
        formatted = "=== Knowledge Graph Context ===\n\n"
        
        # Show refined query explanation
        if refined_query:
            formatted += f"Query Understanding: {refined_query}\n\n"
        
        # Most relevant relationships
        formatted += "Most Relevant Relationships:\n"
        for rel in search_results["relevant_relationships"]:
            formatted += f"  {rel['source_name']} ({rel['source_type']}) "
            formatted += f"-[{rel['relationship']}]-> "
            formatted += f"{rel['target_name']} ({rel['target_type']})\n"
        
        # Related entities
        if search_results["expanded_nodes"]:
            formatted += "\nRelated Entities:\n"
            for node in search_results["expanded_nodes"]:
                formatted += f"  {node['type']}: {node['name']}\n"
        
        # All connections found
        if search_results["connections"]:
            formatted += "\nAll Connections:\n"
            for conn in search_results["connections"]:
                formatted += f"  {conn[0]} -[{conn[1]}]-> {conn[2]}\n"
        
        formatted += f"\nTotal entities: {search_results['total_entities']}"
        
        return formatted
    
    def answer_question(self, user_query):
        """Answer question with refined query explanation"""
        
        print(f"\nUser Question: {user_query}")
        
        # Step 1: Refine the query to explain the path
        print("\nStep 1: Refining query...\n")
        refined_query = self.graph.refine_query_for_embedding(user_query) 
        print(refined_query)
        # Step 2: Execute hybrid search
        print("Step 2: Searching knowledge graph...\n")
        search_results = self.graph.hybrid_search(user_query)
        
        # Step 3: Format context
        context_str = self.format_hybrid_context(search_results, refined_query)
        
        # Step 4: Generate answer
        system_prompt = """You are an IT infrastructure expert.
        You have a knowledge graph with servers, applications, operating systems, and locations.

        Use the provided context to answer accurately:
        1. Look at the "Most Relevant Relationships" first
        2. Use "Related Entities" for additional context
        3. Check "All Connections" for complete picture
        4. Answer ONLY what is asked - be concise
        5. Use specific entity names from the results

        Do NOT add information not in the provided context."""
        
        user_prompt = f"""{context_str}

        User Question: {user_query}

        Answer based ONLY on the relationships and entities shown above. Do not provide any form of enumeration for formatting"""
                
        print("Step 3: Generating answer...\n")
        
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        answer = response.choices[0].message.content
        print(f"Answer:\n{answer}\n")
        
        return answer
