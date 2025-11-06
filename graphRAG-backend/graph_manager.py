from neo4j import GraphDatabase
import os
from dotenv import load_dotenv
from openai import OpenAI
import csv
import time
import json

load_dotenv()


class GraphManager:
    def __init__(self, uri, user, password):
        """Initialize Neo4j driver and OpenAI client"""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def close(self):
        """Close database connection"""
        self.driver.close()
    
    def clear_database(self):
        """Clear all nodes and relationships"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        print("Database cleared")
    
    def create_constraints(self):
        """Create unique constraints on node IDs"""
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Server) REQUIRE s.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Application) REQUIRE a.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (o:OS) REQUIRE o.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (l:Location) REQUIRE l.id IS UNIQUE")
        print("Constraints created")
    
    def import_nodes(self, file_path, label, id_field="id", name_field="name"):
        """Import nodes from CSV file"""
        with self.driver.session() as session:
            with open(file_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    node_id = row[id_field]
                    node_name = row[name_field]
                    query = f"""
                    MERGE (n:{label} {{id: $id}})
                    SET n.name = $name
                    """
                    session.run(query, id=node_id, name=node_name)
        print(f"Imported {label} nodes from {file_path}")
    
    def import_relationships(self, file_path, rel_type):
        """Import relationships from CSV file"""
        with self.driver.session() as session:
            with open(file_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    start_id = row['start']
                    end_id = row['end']
                    query = f"""
                    MATCH (a {{id: $start_id}})
                    MATCH (b {{id: $end_id}})
                    MERGE (a)-[:{rel_type}]->(b)
                    """
                    session.run(query, start_id=start_id, end_id=end_id)
        print(f"Imported {rel_type} relationships from {file_path}")
    
    def create_bidirectional_relationships(self):
        """
        Create reverse relationships for all edges
        Improves multi-hop query traversal
        """
        
        print("\nCreating bidirectional relationships...")
        
        with self.driver.session() as session:
            # LOCATED_IN ↔ CONTAINS_SERVER
            print("  Creating CONTAINS_SERVER (reverse of LOCATED_IN)...")
            session.run("""
            MATCH (s:Server)-[:LOCATED_IN]->(l:Location)
            MERGE (l)-[:CONTAINS_SERVER]->(s)
            """)
            
            # RUNS_ON ↔ RUNS_ON_SERVER
            print("  Creating RUNS_ON_SERVER (reverse of RUNS_ON)...")
            session.run("""
            MATCH (s:Server)-[:RUNS_ON]->(o:OS)
            MERGE (o)-[:RUNS_ON_SERVER]->(s)
            """)
            
            # HOSTS ↔ HOSTED_ON
            print("  Creating HOSTED_ON (reverse of HOSTS)...")
            session.run("""
            MATCH (s:Server)-[:HOSTS]->(a:Application)
            MERGE (a)-[:HOSTED_ON]->(s)
            """)
        
        print("Bidirectional relationships created\n")

    def create_enhanced_relationships(self):
        """Create inferred relationships for better query performance"""
        
        with self.driver.session() as session:
            
            # 1. Application → OS (via Server)
            print("Creating APPLICATION_RUNS_ON_OS...")
            session.run("""
            MATCH (app:Application)-[:HOSTED_ON]->(s:Server)-[:RUNS_ON]->(os:OS)
            MERGE (app)-[:RUNS_ON_OS]->(os)
            """)
            
            # 2. Application → Location (via Server)
            print("Creating APPLICATION_IN_LOCATION...")
            session.run("""
            MATCH (app:Application)-[:HOSTED_ON]->(s:Server)-[:LOCATED_IN]->(loc:Location)
            MERGE (app)-[:IN_LOCATION]->(loc)
            """)
            
            # 3. OS → Location (via Server)
            print("Creating OS_IN_LOCATION...")
            session.run("""
            MATCH (os:OS)<-[:RUNS_ON]-(s:Server)-[:LOCATED_IN]->(loc:Location)
            MERGE (os)-[:AVAILABLE_IN]->(loc)
            """)
            
            # 4. Application → Application (co-location)
            print("Creating CO_HOSTED relationships...")
            session.run("""
            MATCH (app1:Application)-[:HOSTED_ON]->(s:Server)<-[:HOSTED_ON]-(app2:Application)
            WHERE app1.id < app2.id
            MERGE (app1)-[:CO_HOSTED_WITH]->(app2)
            """)
            
            # 5. Server → Server (same location)
            print("Creating SAME_LOCATION relationships...")
            session.run("""
            MATCH (s1:Server)-[:LOCATED_IN]->(loc:Location)<-[:LOCATED_IN]-(s2:Server)
            WHERE s1.id < s2.id
            MERGE (s1)-[:SAME_LOCATION_AS]->(s2)
            """)
        
        print("Enhanced relationships created!\n")



    def load_all_data(self, csv_directory): # Bidirectional
        """
        Load all data AND create bidirectional relationships
        One-time setup
        """
        
        print("\nLoading CSV data with bidirectional relationships...")
        self.create_constraints()
        
        # Import base data
        self.import_nodes(f"{csv_directory}/applications.csv", "Application")
        self.import_nodes(f"{csv_directory}/servers.csv", "Server")
        self.import_nodes(f"{csv_directory}/oses.csv", "OS")
        self.import_nodes(f"{csv_directory}/locations.csv", "Location")
        
        self.import_relationships(f"{csv_directory}/hosts.csv", "HOSTS")
        self.import_relationships(f"{csv_directory}/runs_on.csv", "RUNS_ON")
        self.import_relationships(f"{csv_directory}/located_in.csv", "LOCATED_IN")
        
        print("Base data loaded successfully")
        
        # Create reverse relationships
        self.create_bidirectional_relationships()
        
        self.create_enhanced_relationships()
        print("All data with bidirectional relationships loaded\n")


    def visualize_relationships(self):
        """
        Show all relationships in the graph (for verification)
        """
        
        query = """
        MATCH (a)-[r]->(b)
        RETURN 
            labels(a)[0] as from_type,
            a.name as from_name,
            type(r) as relationship,
            labels(b)[0] as to_type,
            b.name as to_name
        ORDER BY type(r), from_name
        """
        
        results = self.query_graph(query)
        
        print("\nAll Relationships in Graph:")
        print("="*80)
        
        relationships_by_type = {}
        for record in results:
            rel_type = record['relationship']
            if rel_type not in relationships_by_type:
                relationships_by_type[rel_type] = []
            relationships_by_type[rel_type].append(record)
        
        for rel_type in sorted(relationships_by_type.keys()):
            rels = relationships_by_type[rel_type]
            print(f"\n{rel_type} ({len(rels)} total):")
            print("-" * 80)
            for rel in rels:
                print(f"  {rel['from_type']:15} {rel['from_name']:20} -> {rel['to_type']:15} {rel['to_name']:20}")
        
        print("="*80 + "\n")

    def load_all_data_DEFFERED(self, csv_directory): # Original
        """Load all CSV files into the graph"""
        print("\nLoading CSV data...")
        self.create_constraints()
        
        self.import_nodes(f"{csv_directory}/applications.csv", "Application")
        self.import_nodes(f"{csv_directory}/servers.csv", "Server")
        self.import_nodes(f"{csv_directory}/oses.csv", "OS")
        self.import_nodes(f"{csv_directory}/locations.csv", "Location")
        
        self.import_relationships(f"{csv_directory}/hosts.csv", "HOSTS")
        self.import_relationships(f"{csv_directory}/runs_on.csv", "RUNS_ON")
        self.import_relationships(f"{csv_directory}/located_in.csv", "LOCATED_IN")
        
        print("All data loaded successfully\n")
    
    def query_graph(self, cypher_query, params=None):
        """Execute a Cypher query and return results"""
        with self.driver.session() as session:
            result = session.run(cypher_query, params or {})
            return [record for record in result]
    
    def create_relationship_embeddings(self):
        """Create embeddings for RELATIONSHIPS based on their context"""
        print("\nCreating relationship context embeddings...")
        
        with self.driver.session() as session:
            relationship_contexts = session.run("""
                MATCH (a)-[r]->(b)
                RETURN 
                    a.name as source_name,
                    labels(a)[0] as source_type,
                    type(r) as relationship_type,
                    b.name as target_name,
                    labels(b)[0] as target_type,
                    a.id as source_id,
                    b.id as target_id
            """)
            
            embeddings_to_store = []
            
            for idx, rel in enumerate(relationship_contexts, 1):
                source_type = rel['source_type']
                source_name = rel['source_name']
                rel_type = rel['relationship_type']
                target_type = rel['target_type']
                target_name = rel['target_name']
                
                context_text = f"{source_type} '{source_name}' {rel_type.lower()} {target_type} '{target_name}'"
                
                embedding_response = self.openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=context_text
                )
                embedding = embedding_response.data[0].embedding
                
                embeddings_to_store.append({
                    'source_id': rel['source_id'],
                    'target_id': rel['target_id'],
                    'rel_type': rel['relationship_type'],
                    'context': context_text,
                    'embedding': embedding
                })
                
                if idx % 10 == 0:
                    print(f"  [{idx}] Embedded: {context_text}")
                
                time.sleep(0.05)
            
            for item in embeddings_to_store:
                session.run("""
                    MATCH (a {id: $source_id})-[r]->(b {id: $target_id})
                    WHERE type(r) = $rel_type
                    SET r.context_embedding = $embedding,
                        r.context_text = $context
                """, 
                source_id=item['source_id'],
                target_id=item['target_id'],
                rel_type=item['rel_type'],
                embedding=item['embedding'],
                context=item['context']
                )
            
        print(f"Created {len(embeddings_to_store)} relationship embeddings\n")
    
    def semantic_relationship_search(self, query_text, top_k=10):
        """Search for semantically relevant RELATIONSHIPS"""
        
        query_embedding = self.openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=query_text
        ).data[0].embedding
        
        cypher_query = """
        MATCH (a)-[r]->(b)
        WHERE r.context_embedding IS NOT NULL
        WITH a, r, b, 
             reduce(sum=0, i IN range(0, size(r.context_embedding)-1) | 
                sum + r.context_embedding[i] * $query_embedding[i]) as similarity
        ORDER BY similarity DESC
        LIMIT $top_k
        RETURN 
            a.name as source_name,
            labels(a)[0] as source_type,
            type(r) as relationship,
            b.name as target_name,
            labels(b)[0] as target_type,
            r.context_text as relationship_context,
            similarity
        """
        
        results = self.query_graph(cypher_query, {
            "query_embedding": query_embedding,
            "top_k": top_k
        })
        
        return results
    
    def hybrid_search(self, query_text):
        """Combine semantic relationship search + smart traversal"""
        
        print(f"\n{'='*60}")
        print(f"HYBRID SEARCH: {query_text}")
        print(f"{'='*60}")
        
        print("\nStep 1: Finding semantically relevant relationships...")
        relevant_rels = self.semantic_relationship_search(query_text, top_k=10)
        
        involved_nodes = set()
        for rel in relevant_rels:
            involved_nodes.add(rel['source_name'])
            involved_nodes.add(rel['target_name'])
        
        print(f"Found {len(relevant_rels)} relevant relationships")
        print(f"Involving {len(involved_nodes)} nodes")
        
        print("\nStep 2: Expanding context from involved nodes...")
        if involved_nodes:
            cypher_query = """
            MATCH (seed)-[*0..2]-(neighbor)
            WHERE seed.name IN $node_names
            RETURN DISTINCT neighbor.name as name, labels(neighbor)[0] as type
            LIMIT 30
            """
            
            neighbors = self.query_graph(cypher_query, {"node_names": list(involved_nodes)})
            print(f"Found {len(neighbors)} related nodes")
        else:
            neighbors = []
        
        print("\nStep 3: Finding connections between retrieved entities...")
        all_nodes = list(involved_nodes) + [n['name'] for n in neighbors]
        
        cypher_query = """
        MATCH (a)-[r]->(b)
        WHERE a.name IN $names AND b.name IN $names
        RETURN a.name, type(r) as relationship, b.name
        """
        
        connections = self.query_graph(cypher_query, {"names": all_nodes})
        print(f"Found {len(connections)} connections")
        
        return {
            "query": query_text,
            "relevant_relationships": relevant_rels,
            "expanded_nodes": neighbors,
            "connections": connections,
            "total_entities": len(set(all_nodes))
        }

    def refine_query_for_hybrid_search(self, user_query): # Used for testing
        """
        Refine query to describe the multi-hop path
        Example: "what applications run on London"
        Becomes: "what applications run on servers that are located in London"
        """
        
        refine_prompt = f"""You are a query refinement expert for a knowledge graph.

        The knowledge graph has these relationships:
        - LOCATED_IN: Server -> Location (servers are located in locations)
        - HOSTS: Server -> Application (servers host applications)
        - RUNS_ON: Server -> OS (servers run operating systems)
        - CONTAINS_SERVER: Location -> Server (reverse of LOCATED_IN)
        - HOSTED_ON: Application -> Server (reverse of HOSTS)
        - RUNS_ON_SERVER: OS -> Server (reverse of RUNS_ON)

        User Query: "{user_query}"

        Refine this query to make the multi-hop path EXPLICIT.
        Explain which intermediate entities to get first.

        Examples:
        - Input: "what applications run on London"
        Output: "what applications run on servers in London, we need to get servers located in London first, then get applications hosted on those servers"

        - Input: "which servers are in New York"
        Output: "which servers are located in New York"

        - Input: "what OS runs on applications in Singapore"
        Output: "what OS runs on servers that host applications in Singapore"

        Return ONLY the refined query description, no explanation."""
        
        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a query refinement expert."},
                {"role": "user", "content": refine_prompt}
            ],
            temperature=0.3
        )
        
        refined_query = response.choices[0].message.content.strip()
        print(f"Refined Query: {refined_query}\n")
        
        return refined_query


    def refine_query_for_embedding(self, user_query):
        """
        Refine query into keyword-dense format optimized for vector embeddings
        Focus: Entity names + relationship types + minimal connecting words
        """
        
        refine_prompt = f"""You are a query refinement expert for knowledge graph embeddings.

            The knowledge graph has:
            - Entities: Server, Application, OS, Location
            The knowledge graph has these 11 relationships:

            Direct Relationships (3):
            - HOSTS: Server → Application (servers host applications)
            - RUNS_ON: Server → OS (servers run operating systems)
            - LOCATED_IN: Server → Location (servers are located in locations)

            Reverse Relationships (3):
            - HOSTED_ON: Application → Server (applications are hosted on servers)
            - RUNS_ON_SERVER: OS → Server (operating systems run on servers)
            - CONTAINS_SERVER: Location → Server (locations contain servers)

            Inferred Relationships (5):
            - RUNS_ON_OS: Application → OS (applications run on operating systems)
            - IN_LOCATION: Application → Location (applications are in locations)
            - AVAILABLE_IN: OS → Location (operating systems available in locations)
            - CO_HOSTED_WITH: Application → Application (applications co-hosted together)
            - SAME_LOCATION_AS: Server → Server (servers in same location)
            User Query: "{user_query}"

            Refine this into a SHORT, KEYWORD-RICH query for semantic search.

            Rules:
            1. Use entity types explicitly (Server, Application, OS, Location)
            2. Use relationship keywords (hosts, runs, located,etc)
            3. Maximum 10 words
            4. Remove filler words
            5. Keep only essential keywords

            Examples:
            Input: "what applications run on London"
            Output: "applications hosted servers located London"

            Input: "which servers are in New York"
            Output: "servers located New York"

            Input: "what OS runs on server5"
            Output: "operating system runs server5"

            Input: "applications in Singapore running Ubuntu"
            Output: "applications Singapore servers Ubuntu"

            Return ONLY the refined query (no explanation, no quotes)."""
        
        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You refine queries for vector embeddings."},
                {"role": "user", "content": refine_prompt}
            ],
            temperature=0.2,  # Low temperature for consistency
            max_tokens=30     # Force brevity
        )
        
        refined_query = response.choices[0].message.content.strip().strip('"\'')
        print(f"Refined for Embedding: {refined_query}\n")
        
        return refined_query
