#!/usr/bin/env python3
"""
Explore the contents of the Crawl4AI databases (PostgreSQL and Neo4j).
"""
import asyncio
import json
import os
import logging
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def explore_postgres_db():
    """Explore the PostgreSQL database contents."""
    print("=" * 70)
    print("POSTGRESQL DATABASE EXPLORATION")
    print("=" * 70)
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Try to connect to the PostgreSQL database
        # Check if we can connect via Docker network or localhost
        connection_configs = [
            {
                "host": "localhost",
                "port": "5432",
                "database": "crawl4ai_db",
                "user": "postgres", 
                "password": "password"
            },
            {
                "host": "192.168.50.7",
                "port": "5432", 
                "database": "crawl4ai_db",
                "user": "postgres",
                "password": "password"
            }
        ]
        
        conn = None
        for config in connection_configs:
            try:
                print(f"Trying to connect to PostgreSQL at {config['host']}:{config['port']}...")
                conn = psycopg2.connect(**config)
                print(f"✅ Connected to PostgreSQL at {config['host']}!")
                break
            except Exception as e:
                print(f"❌ Failed to connect to {config['host']}: {e}")
                continue
        
        if not conn:
            print("❌ Could not connect to PostgreSQL database")
            return
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check what tables exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        print(f"\n📊 Found {len(tables)} tables:")
        for table in tables:
            print(f"  • {table['table_name']}")
        
        # Explore each table
        for table in tables:
            table_name = table['table_name']
            print(f"\n📋 Table: {table_name}")
            print("-" * 50)
            
            # Get table structure
            cursor.execute(f"""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position;
            """)
            columns = cursor.fetchall()
            
            print("📝 Schema:")
            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
                print(f"  • {col['column_name']}: {col['data_type']} {nullable}{default}")
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            count = cursor.fetchone()['count']
            print(f"📈 Rows: {count}")
            
            # Show sample data if table has data
            if count > 0:
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
                samples = cursor.fetchall()
                print("📄 Sample data:")
                for i, row in enumerate(samples, 1):
                    print(f"  Row {i}: {dict(row)}")
                    if i >= 2:  # Limit to 2 rows for readability
                        break
        
        cursor.close()
        conn.close()
        
    except ImportError:
        print("❌ psycopg2 not installed. Install with: pip install psycopg2-binary")
    except Exception as e:
        print(f"❌ Error exploring PostgreSQL: {e}")

def explore_neo4j_db():
    """Explore the Neo4j database contents."""
    print("\n" + "=" * 70)
    print("NEO4J GRAPH DATABASE EXPLORATION")
    print("=" * 70)
    
    try:
        from neo4j import GraphDatabase
        
        # Try to connect to Neo4j
        neo4j_configs = [
            {"uri": "bolt://localhost:7688", "user": "neo4j", "password": "password"},
            {"uri": "bolt://192.168.50.7:7688", "user": "neo4j", "password": "password"},
            {"uri": "neo4j://localhost:7687", "user": "neo4j", "password": "password"},
        ]
        
        driver = None
        for config in neo4j_configs:
            try:
                print(f"Trying to connect to Neo4j at {config['uri']}...")
                driver = GraphDatabase.driver(config['uri'], auth=(config['user'], config['password']))
                with driver.session() as session:
                    session.run("RETURN 1")  # Test connection
                print(f"✅ Connected to Neo4j at {config['uri']}!")
                break
            except Exception as e:
                print(f"❌ Failed to connect to {config['uri']}: {e}")
                if driver:
                    driver.close()
                    driver = None
                continue
        
        if not driver:
            print("❌ Could not connect to Neo4j database")
            return
        
        with driver.session() as session:
            # Get database info
            result = session.run("CALL db.labels()")
            labels = [record["label"] for record in result]
            
            result = session.run("CALL db.relationshipTypes()")
            relationships = [record["relationshipType"] for record in result]
            
            print(f"\n🏷️  Node Labels ({len(labels)}):")
            for label in labels:
                print(f"  • {label}")
            
            print(f"\n🔗 Relationship Types ({len(relationships)}):")
            for rel in relationships:
                print(f"  • {rel}")
            
            # Count nodes and relationships
            result = session.run("MATCH (n) RETURN count(n) as count")
            node_count = result.single()["count"]
            
            result = session.run("MATCH ()-[r]-() RETURN count(r) as count")
            rel_count = result.single()["count"]
            
            print(f"\n📊 Database Stats:")
            print(f"  • Total Nodes: {node_count}")
            print(f"  • Total Relationships: {rel_count}")
            
            # Show sample data for each label
            for label in labels[:5]:  # Limit to first 5 labels
                print(f"\n📋 Sample {label} nodes:")
                result = session.run(f"MATCH (n:{label}) RETURN n LIMIT 3")
                for i, record in enumerate(result, 1):
                    node = record["n"]
                    props = dict(node)
                    # Truncate long values for readability
                    truncated_props = {}
                    for key, value in props.items():
                        if isinstance(value, str) and len(value) > 100:
                            truncated_props[key] = value[:100] + "..."
                        else:
                            truncated_props[key] = value
                    print(f"  Node {i}: {truncated_props}")
        
        driver.close()
        
    except ImportError:
        print("❌ neo4j not installed. Install with: pip install neo4j")
    except Exception as e:
        print(f"❌ Error exploring Neo4j: {e}")

def check_docker_containers():
    """Check if database containers are running."""
    print("=" * 70)
    print("DOCKER CONTAINER STATUS")
    print("=" * 70)
    
    import subprocess
    
    try:
        result = subprocess.run(['docker', 'ps'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            db_containers = []
            for line in lines[1:]:  # Skip header
                if 'postgres' in line.lower() or 'neo4j' in line.lower():
                    db_containers.append(line)
            
            if db_containers:
                print("🐳 Database containers running:")
                for container in db_containers:
                    print(f"  {container}")
            else:
                print("❌ No database containers found running")
        else:
            print("❌ Could not check Docker containers")
    except Exception as e:
        print(f"❌ Error checking containers: {e}")

def check_crawl_results():
    """Check local crawl result files."""
    print("\n" + "=" * 70)
    print("LOCAL CRAWL RESULT FILES")
    print("=" * 70)
    
    # Check for JSON result files
    json_files = ['crawl_result.json', 'crawl_results.json']
    
    for filename in json_files:
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    data = json.load(f)
                
                print(f"📄 {filename}:")
                if isinstance(data, dict):
                    print(f"  • Type: Dictionary with {len(data)} keys")
                    print(f"  • Keys: {list(data.keys())}")
                elif isinstance(data, list):
                    print(f"  • Type: List with {len(data)} items")
                    if data and isinstance(data[0], dict):
                        print(f"  • First item keys: {list(data[0].keys())}")
                else:
                    print(f"  • Type: {type(data)}")
                    print(f"  • Content: {str(data)[:200]}...")
                
                # Show file size
                size = os.path.getsize(filename)
                print(f"  • Size: {size:,} bytes")
                
            except Exception as e:
                print(f"❌ Error reading {filename}: {e}")
        else:
            print(f"❌ {filename} not found")

async def main():
    """Main exploration function."""
    print("🔍 CRAWL4AI DATABASE EXPLORATION")
    print("Analyzing all data sources in the Crawl4AI project...")
    
    # Check Docker containers first
    check_docker_containers()
    
    # Explore PostgreSQL database
    explore_postgres_db()
    
    # Explore Neo4j database
    explore_neo4j_db()
    
    # Check local files
    check_crawl_results()
    
    print("\n" + "=" * 70)
    print("📋 SUMMARY")
    print("=" * 70)
    print("This Crawl4AI project uses multiple data storage systems:")
    print("1. 🐘 PostgreSQL - Stores crawled web content with vector embeddings")
    print("2. 🌐 Neo4j - Stores knowledge graph of code repositories") 
    print("3. 📄 JSON files - Local crawl results and cached data")
    print("4. 🗃️  SQLite - May be used for crawler cache (check Docker logs)")
    print("\nDatabase schemas are defined in:")
    print("  • crawled_pages.sql - PostgreSQL schema")
    print("  • knowledge_graphs/ - Neo4j graph structure")

if __name__ == "__main__":
    asyncio.run(main())
