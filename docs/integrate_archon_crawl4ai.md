# Integrating Archon with Crawl4AI Supabase Database

## Overview

Both Archon and Crawl4AI can share the same Supabase database instance. This integration allows you to:

- Use Archon's project management alongside Crawl4AI's web crawling
- Have crawled content available in both systems
- Manage everything from a single database instance
- Reduce infrastructure costs and complexity

## Database Schema Integration

### 1. **Set Up Shared Supabase Database**

Use your existing Supabase project or create a new one that both systems will share.

### 2. **Run Both SQL Schemas**

In your Supabase SQL Editor, run both schema files in this order:

1. **First, run Archon's schema:**
   ```sql
   -- Contents of Archon's migration/complete_setup.sql
   -- This creates all the archon_* tables
   ```

2. **Then, run Crawl4AI's schema:**
   ```sql
   -- Contents of crawl4ai's crawled_pages.sql  
   -- This creates crawled_pages, code_examples, and sources tables
   ```

The schemas are compatible since they use different table names and don't conflict.

### 3. **Environment Configuration**

#### For Archon (.env in Archon directory):
```bash
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key-here
SUPABASE_ANON_KEY=your-anon-key-here

# Use the same database for both systems
```

#### For Crawl4AI (.env in mcp_crawl4ai_rag directory):  
```bash
# MCP Server Configuration
HOST=0.0.0.0
PORT=8054
TRANSPORT=sse

# OpenAI API Configuration
OPENAI_API_KEY=your_openai_api_key

# Supabase Configuration - SAME AS ARCHON
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key-here

# RAG Strategies
USE_CONTEXTUAL_EMBEDDINGS=true
USE_HYBRID_SEARCH=true
USE_AGENTIC_RAG=true
USE_RERANKING=true
USE_KNOWLEDGE_GRAPH=false
```

## Integration Benefits

### 1. **Unified Knowledge Base**
- Crawl4AI stores web content in `crawled_pages` table
- Archon can reference this content for project documentation
- Both systems can perform RAG queries on the same data

### 2. **Project-Source Linking**
You can link crawled sources to Archon projects by:

```sql
-- Example: Link a crawled source to an Archon project
INSERT INTO archon_project_sources (project_id, source_id, source_type, metadata)
VALUES (
  'your-project-uuid',
  'example.com', 
  'crawled_website',
  '{"crawl_date": "2024-01-01", "page_count": 50}'::jsonb
);
```

### 3. **Shared MCP Integration**
- Both systems can be MCP servers
- AI assistants can access both project management AND web crawling
- Unified workflow: Create project → Crawl docs → Manage tasks

## Docker Compose Integration

You can run both systems together by combining their docker-compose files:

```yaml
version: '3.8'

services:
  # Archon Services
  archon-ui:
    # ... Archon UI config
    
  archon-server:
    # ... Archon server config
    
  archon-mcp:
    # ... Archon MCP config
    
  # Crawl4AI Service  
  mcp-crawl4ai-rag:
    build:
      context: ./mcp_crawl4ai_rag
      dockerfile: Dockerfile
    container_name: mcp-crawl4ai-rag
    ports:
      - "8052:8054"  # Different port to avoid conflict
    environment:
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
```

## MCP Client Configuration

Configure your AI assistant to use both MCP servers:

```json
{
  "mcpServers": {
    "archon": {
      "transport": "sse",
      "url": "http://localhost:8054/sse"
    },
    "crawl4ai-rag": {
      "transport": "sse", 
      "url": "http://localhost:8052/sse"
    }
  }
}
```

## Advanced Integration Ideas

### 1. **Automatic Project Documentation**
- When creating a new project in Archon, automatically crawl relevant documentation
- Store crawled content and link it to the project

### 2. **Task-Driven Crawling**
- Create tasks in Archon that trigger specific crawling operations
- Use crawled content to auto-populate task descriptions

### 3. **Unified Search**
- Create custom queries that search across both Archon projects and crawled content
- Provide context-aware suggestions based on current project

### 4. **Knowledge Graph Integration**
- Link Archon projects to code repositories in the knowledge graph
- Validate project requirements against actual code implementations

## Migration Strategy

If you already have data in separate databases:

1. **Export existing data** from both systems
2. **Set up the shared database** with both schemas
3. **Import Archon data** first (projects, tasks, etc.)
4. **Import Crawl4AI data** (crawled pages, sources)
5. **Update environment variables** in both systems
6. **Test the integration** with a small project

## Security Considerations

- Use the same Supabase service key for both systems
- Set up Row Level Security (RLS) policies if needed
- Consider creating separate service accounts if you need different access levels
- Monitor database usage since both systems will be writing to the same instance

## Monitoring and Maintenance

- Monitor Supabase usage across both systems
- Set up database backups that include both schemas
- Use Supabase's built-in monitoring for performance insights
- Consider setting up alerts for storage usage

This integration creates a powerful combination where Archon provides project management and task coordination while Crawl4AI provides advanced web crawling and RAG capabilities, all backed by a shared knowledge base in Supabase.
